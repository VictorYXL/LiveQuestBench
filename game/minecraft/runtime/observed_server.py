"""Opt-in prototype server; never changes the default vanilla runtime."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re

from game.minecraft.runtime.server import MinecraftServer


class ObservedServer(MinecraftServer):
    @staticmethod
    def normalize_console_line(text):
        return re.sub(r"(\[Server thread/(?:INFO|WARN|ERROR)\]) \(Minecraft\) ", r"\1: ", text)

    async def _read(self):
        assert self.process is not None and self.process.stdout is not None
        try:
            while line := await self.process.stdout.readline():
                text = self.normalize_console_line(line.decode("utf-8", errors="replace").rstrip())
                self._tail.append(text)
                if re.search(r'\[Server thread/INFO\]: Done \([^)]+\)! For help, type "help"$', text):
                    self._started = True
                    self._ready.set()
                if self._pending is not None:
                    self._pending.put_nowait(text)
        finally:
            self._ready.set()
            if self._pending is not None:
                self._pending.put_nowait(None)

    async def start(self):
        launch_path = Path(os.environ.get(
            "LIVEQUEST_BREAK_SERVER_LAUNCH",
            str(Path(__file__).resolve().parents[1] / "server_observer/launch.json"),
        )).resolve()
        launch = json.loads(launch_path.read_text())
        observer_classes = [
            Path(entry) / "org/livequestbench/observer/SuccessfulBreakMixin.class"
            for entry in launch["classpath"]
            if (Path(entry) / "org/livequestbench/observer/SuccessfulBreakMixin.class").is_file()
        ]
        if len(observer_classes) != 1:
            raise RuntimeError("Expected exactly one compiled passive break observer")
        (self.directory / "observer-runtime.json").write_text(json.dumps({
            "launch_sha256": hashlib.sha256(launch_path.read_bytes()).hexdigest(),
            "observer_class_sha256": hashlib.sha256(observer_classes[0].read_bytes()).hexdigest(),
            "events": "successful-breaks.jsonl",
            "gameplay_mutations": False,
        }, indent=2) + "\n")
        self._ready.clear()
        self._started = False
        args = [self.java, "-Xms256M", f"-Xmx{self.memory_mb}M",
                "-Dlivequest.break.events=" + str(self.directory / "successful-breaks.jsonl"),
                *launch["jvm_args"], "-cp", os.pathsep.join(launch["classpath"]),
                launch["main_class"], *launch["program_args"]]
        self.process = await asyncio.create_subprocess_exec(
            *args, cwd=self.directory, env={**os.environ, **launch["environment"]},
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, limit=1024 * 1024,
        )
        self._reader = asyncio.create_task(self._read())
        await asyncio.wait_for(self._ready.wait(), self.startup_timeout)
        self.check_ready()
        if not self._started:
            raise RuntimeError("Observed native server did not become ready: " + "\n".join(self._tail))
