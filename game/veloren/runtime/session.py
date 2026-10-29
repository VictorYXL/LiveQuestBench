"""Own an isolated Python/native runtime through correlated private JSONL RPC."""

import asyncio
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from game.veloren.fixture import solid_voxels


def runtime_configuration(fixture: dict) -> tuple[Path, dict]:
    protocol = fixture.get("message_contract", {}).get("initialization_protocol")
    override = {
        "initial-message-v2": "LIVEQUEST_VELOREN_INITIAL_MESSAGE_V2_RUNTIME",
        "initial-message-v3": "LIVEQUEST_VELOREN_INITIAL_MESSAGE_V3_RUNTIME",
    }.get(protocol)
    if "market" in fixture:
        override = "LIVEQUEST_VELOREN_MARKET_RUNTIME"
    selected = (os.environ.get(override) if override else None) or os.environ.get("LIVEQUEST_VELOREN_RUNTIME")
    if not selected:
        setting = override or "LIVEQUEST_VELOREN_RUNTIME"
        raise RuntimeError(f"Set {setting} to the prepared runtime.json; see game/veloren/README.md")
    path = Path(selected).resolve()
    runtime = json.loads(path.read_text())
    if protocol is not None and runtime.get("initial_message_protocol") != protocol:
        raise ValueError(f"{protocol} requires its matching native runtime; configure {override}")
    return path, runtime


class VelorenSession:
    def __init__(self, output: Path, display: str, track: str, fixture: dict):
        self.output, self.display, self.track, self.fixture = output, display, track, fixture
        self.process: asyncio.subprocess.Process | None = None
        self.reader: asyncio.Task | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.log = None
        self.team_role: str | None = None
        self.attachment: dict | None = None

    async def start(self) -> dict:
        runtime_path, runtime = runtime_configuration(self.fixture)
        environment = {key: os.environ[key] for key in (
            "PATH", "LANG", "LC_ALL", "XAUTHORITY", "VK_ICD_FILENAMES", "VK_DRIVER_FILES",
            "LD_LIBRARY_PATH", "NVIDIA_VISIBLE_DEVICES", "NVIDIA_DRIVER_CAPABILITIES",
        ) if key in os.environ}
        environment.update(PYTHONUNBUFFERED="1", DISPLAY=self.display)
        self.log = (self.output / "worker.log").open("xb")
        fixture_path = self.output / "fixture-input.json"
        fixture_path.write_text(json.dumps(
            {"fixture": self.fixture, "team_role": self.team_role, "attachment": self.attachment}
            if self.team_role is not None else self.fixture, indent=2, allow_nan=False,
        ) + "\n")
        self.process = await asyncio.create_subprocess_exec(
            runtime["python"], str(Path(__file__).with_name("worker.py")),
            str(runtime_path), str(self.output), self.track, str(fixture_path),
            env=environment, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=self.log, limit=16 * 1024 * 1024,
        )
        self.reader = asyncio.create_task(self._read())
        return await self.request("start", timeout=240 + 2 * len(solid_voxels(self.fixture)))

    async def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        error: BaseException = RuntimeError("Veloren worker closed unexpectedly; inspect worker.log")
        try:
            while line := await self.process.stdout.readline():
                response = json.loads(line)
                future = self.pending.get(response["id"])
                if future is not None and not future.done():
                    if response["ok"]:
                        future.set_result(response["result"])
                    else:
                        future.set_exception(RuntimeError(f"Veloren native failure: {response['error']}"))
        except BaseException as caught:
            error = caught
            raise
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(error)

    def check_ready(self) -> None:
        if self.process is None or self.process.returncode is not None or self.reader is None or self.reader.done():
            raise RuntimeError("Veloren runtime is not running; inspect worker.log")

    async def request(self, method: str, *, timeout: float | None = 60, **arguments) -> dict:
        self.check_ready()
        assert self.process is not None and self.process.stdin is not None
        identifier = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            self.process.stdin.write((json.dumps({"id": identifier, "op": method, "arguments": arguments}) + "\n").encode())
            await self.process.stdin.drain()
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(identifier, None)

    async def close(self) -> None:
        try:
            if self.process is not None and self.process.returncode is None:
                try:
                    await self.request("close", timeout=90)
                    await asyncio.wait_for(self.process.wait(), 10)
                except BaseException:
                    if self.process.returncode is None:
                        self.process.terminate()
                        try:
                            await asyncio.wait_for(self.process.wait(), 30)
                        except TimeoutError:
                            self.process.kill()
                            await self.process.wait()
                    raise
        finally:
            try:
                if self.reader is not None:
                    await self.reader
            finally:
                if self.log is not None:
                    self.log.close()
                (self.output / "cleanup.json").write_text(json.dumps({
                    "worker_returncode": self.process.returncode if self.process else None,
                    "closed_at_ns": time.monotonic_ns(),
                }, indent=2) + "\n")
