"""Owned local server process and private console administration, never Agent tools."""

import asyncio
from collections import deque
from pathlib import Path
import re
from uuid import uuid4

import nbtlib


class MinecraftServer:
    def __init__(self, directory: Path, jar: Path, java: str, memory_mb: int,
                 port: int, startup_timeout: float, stop_timeout: float):
        self.directory, self.jar, self.java = directory, jar, java
        self.memory_mb, self.port = memory_mb, port
        self.startup_timeout, self.stop_timeout = startup_timeout, stop_timeout
        self.process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._started = False
        self._pending: asyncio.Queue[str | None] | None = None
        self._command_lock = asyncio.Lock()
        self._tail: deque[str] = deque(maxlen=12)

    async def start(self) -> None:
        self._ready.clear()
        self._started = False
        self.process = await asyncio.create_subprocess_exec(
            self.java, "-Xms256M", f"-Xmx{self.memory_mb}M", "-jar", str(self.jar), "nogui",
            cwd=self.directory, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, limit=1024 * 1024,
        )
        self._reader = asyncio.create_task(self._read())
        await asyncio.wait_for(self._ready.wait(), self.startup_timeout)
        self.check_ready()
        if not self._started:
            raise RuntimeError("Minecraft server did not become ready: " + "\n".join(self._tail))

    async def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            while line := await self.process.stdout.readline():
                text = line.decode("utf-8", errors="replace").rstrip()
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

    def check_ready(self) -> None:
        if self._reader is not None and self._reader.done():
            self._reader.result()
            raise RuntimeError("Minecraft server console closed: " + "\n".join(self._tail))
        if self.process is None or self.process.returncode is not None:
            raise RuntimeError("Minecraft server exited: " + "\n".join(self._tail))

    async def command(self, command: str) -> list[str]:
        """Return console feedback through a private storage barrier, not player chat."""
        if not command or "\n" in command or "\r" in command:
            raise ValueError("Console command must be one non-empty line")
        async with self._command_lock:
            self.check_ready()
            assert self.process is not None and self.process.stdin is not None
            marker = uuid4().hex
            self._pending = asyncio.Queue()
            try:
                self.process.stdin.write((
                    command + "\n"
                    f'data modify storage gameagent:runner marker set value "{marker}"\n'
                    "data get storage gameagent:runner marker\n"
                ).encode())
                await self.process.stdin.drain()
                result = []
                async with asyncio.timeout(15):
                    while True:
                        line = await self._pending.get()
                        if line is None:
                            raise RuntimeError("Minecraft server exited during administration")
                        if re.search(
                            r'\[Server thread/INFO\]: Storage gameagent:runner has the following contents: "'
                            + marker + r'"$', line,
                        ):
                            return result
                        result.append(line)
                        if len(result) > 4096:
                            raise RuntimeError("Excessive server output during administration")
            finally:
                self._pending = None

    async def player_data(self, name: str):
        lines = await self.command(f"data get entity {name}")
        prefix = f"[Server thread/INFO]: {name} has the following entity data: "
        matches = [line.split(prefix, 1)[1] for line in lines if prefix in line]
        if not matches:
            return None
        if len(matches) != 1:
            raise RuntimeError("Ambiguous player initialization response")
        return nbtlib.parse_nbt(matches[0])

    async def stop(self) -> None:
        process = self.process
        try:
            if process is not None and process.returncode is None:
                if process.stdin is not None:
                    try:
                        process.stdin.write(b"stop\n")
                        await process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        # The exit status below determines whether shutdown succeeded.
                        pass
                try:
                    await asyncio.wait_for(process.wait(), self.stop_timeout)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    raise RuntimeError("Minecraft server shutdown timed out; forced termination")
                if process.returncode != 0:
                    raise RuntimeError(f"Minecraft server exited with code {process.returncode}")
        finally:
            if self._reader is not None:
                await self._reader
            self.process = None
