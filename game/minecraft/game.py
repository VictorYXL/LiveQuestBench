"""Shared Minecraft lifecycle for VM and ST; the caller owns Episode orchestration."""

import asyncio
from contextlib import AsyncExitStack
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from uuid import UUID

from core.backends.x11.display import VirtualDisplay
from game.base_game import BaseGame
from game.minecraft.runtime.account import offline_identity, resolve_account
from game.minecraft.runtime.install import check_installation
from game.minecraft.init_player_state import PlayerState
from game.minecraft.runtime.session import MinecraftSession, SessionConfig, copy_world
from game.minecraft.visual_motor.capture import CapturedFrame
from game.minecraft.visual_motor.interface import MotorInterface, execute_actions
from game.minecraft.visual_motor.recording import WindowRecording
from core.backends.x11.actions import ActionResult
from game.minecraft.structured_tools.interface import (
    PROFILE_ID, StructuredInterface, execute_tool, observe, tool_schemas, validate_tool,
)


class MinecraftGame(BaseGame[MotorInterface | StructuredInterface]):
    def __init__(
        self, *, output_dir: Path, fixture: Path | None = None, player_state: PlayerState | None = None,
        account: str | None = None, instance: str = "1.20.4",
        display: str | None = None, memory_mb: int = 2048,
        difficulty: str = "normal", recording: bool = False, recording_fps: int = 10,
        startup_timeout: float = 120, track: str = "visual_motor",
        authentication: str = "offline", player_name: str = "LiveQuestBot",
        headless: bool = True,
    ) -> None:
        if track not in ("visual_motor", "structured_tool"):
            raise ValueError("track must be visual_motor or structured_tool")
        if track == "structured_tool" and authentication != "offline":
            raise ValueError("ST supports local offline connections only")
        self.track = track
        self.fixture = Path(fixture) if fixture is not None else None
        if authentication not in ("offline", "online"):
            raise ValueError("authentication must be offline or online")
        self.authentication, self.player_name = authentication, player_name
        self.output_dir = Path(output_dir).resolve()
        self.player_state = player_state or PlayerState(position=(0.5, 72, 0.5), yaw=180)
        self.account, self.instance, self.display = account, instance, display
        if type(headless) is not bool:
            raise ValueError("headless must be a boolean")
        self.headless = headless
        self.memory_mb, self.difficulty, self.startup_timeout = memory_mb, difficulty, startup_timeout
        if type(recording_fps) is not int or not 1 <= recording_fps <= 60:
            raise ValueError("recording_fps must be an integer in [1, 60]")
        self.recording, self.recording_fps = recording, recording_fps
        self.phase = "new"
        self.player_uuid: UUID | None = None
        self._session: MinecraftSession | None = None
        self._recorder: WindowRecording | None = None
        self._stack = AsyncExitStack()
        self._lifecycle = asyncio.Lock()
        self._io = asyncio.Lock()
        self._stopped = asyncio.Event()
        self._boundary: dict[str, int] = {}
        self._interface: MotorInterface | StructuredInterface = (
            MotorInterface(self._observe, self._act) if track == "visual_motor"
            else StructuredInterface(self._observe_structured, self._call_tool, tool_schemas)
        )
        self._active_tool: asyncio.Task | None = None

    async def start(self) -> None:
        async with self._lifecycle:
            if self.phase != "new":
                raise RuntimeError("Use a fresh MinecraftGame instance for each Episode")
            self.phase = "starting"
            try:
                if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
                    raise PermissionError("Review https://aka.ms/MinecraftEULA and set MINECRAFT_EULA_ACCEPTED=true")
                installation = check_installation(
                    self.instance, track=self.track,
                    authentication=self.authentication,
                )
                account = resolve_account(self.account) if self.authentication == "online" else None
                identity = offline_identity(self.player_name) if self.authentication == "offline" else account
                assert identity is not None
                self.player_uuid = UUID(identity["player_uuid"])
                display_name = self.display or (":pending" if self.headless else os.environ.get("DISPLAY", ""))
                if not display_name:
                    raise RuntimeError("Desktop mode needs DISPLAY; use --headless or run in an existing X11 desktop")
                config = SessionConfig.from_dict({
                    **identity, "display": display_name,
                    "instance": self.instance, "memory_mb": self.memory_mb,
                    "difficulty": self.difficulty, "startup_timeout": self.startup_timeout,
                    "authentication": self.authentication, "account": account["player_name"] if account else None,
                    "track": self.track, "generated_world": self.fixture is None,
                })
                self.output_dir.mkdir(parents=True, exist_ok=False)
                self._write_json("environment.json", {
                    **installation, "track": self.track, "player": identity,
                    "authentication": self.authentication,
                    "tool_profile": PROFILE_ID if self.track == "structured_tool" else None,
                    "player_state": asdict(self.player_state),
                    "headless": self.headless,
                    "recording": {
                        "enabled": self.recording, "fps": self.recording_fps,
                        "view": "native-player",
                    },
                })
                world = self.output_dir / "world"
                if self.fixture is not None:
                    copy_world(self.fixture, world, self.player_state, self.player_uuid)
                    self._write_json("fixture.json", {
                        "source": str(self.fixture.resolve()),
                        "sha256": {
                            str(path.relative_to(self.fixture)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted(self.fixture.rglob("*"))
                            if path.is_file() and path.name != "session.lock"
                        },
                    })
                else:
                    world.mkdir()
                    self.player_state.write(world, self.player_uuid)
                    self._write_json("fixture.json", {"preset": "flat-smoke-v1", "seed": 0,
                                                     "purpose": "installation and interface checks, not a benchmark task"})
                if self.display is None and self.headless:
                    virtual = VirtualDisplay()
                    self._stack.push_async_callback(virtual.close)
                    config.display = await virtual.start(self.output_dir / "xvfb.log")
                self._session = MinecraftSession(
                    self.output_dir, config, self.player_state, world=world,
                )
                self._stack.push_async_callback(self._session.close)
                self._session.preflight()
                await self._session.start()
                self.phase = "ready"
                self._boundary["ready_at_ns"] = time.monotonic_ns()
                self._write_json("boundaries.json", self._boundary)
            except BaseException as error:
                self.phase = "failed"
                try:
                    await self._stack.aclose()
                except BaseException as cleanup_error:
                    raise BaseExceptionGroup("Minecraft startup and cleanup failed", [error, cleanup_error])
                raise

    def get_agent_interface(self) -> MotorInterface | StructuredInterface:
        if self.phase not in ("ready", "running"):
            raise RuntimeError("Game is not ready")
        return self._interface

    def _check_running(self) -> MinecraftSession:
        if self.phase != "running" or self._stopped.is_set() or self._session is None:
            raise RuntimeError("Agent access is only available during running play")
        if self._recorder is not None and self._recorder.task is not None and self._recorder.task.done():
            self._recorder.task.result()
            raise RuntimeError("Recording stopped during play")
        assert self._session.server is not None
        self._session.server.check_ready()
        return self._session

    async def _observe(self) -> CapturedFrame:
        async with self._io:
            session = self._check_running()
            assert session.actions is not None and session.capture is not None
            session.actions.check_ready()
            return session.capture.capture(session.window_id)

    async def _act(self, commands: list[dict[str, object]]) -> list[ActionResult]:
        async with self._io:
            session = self._check_running()
            assert session.actions is not None
            return await execute_actions(session.actions, commands, self._stopped)

    async def _observe_structured(self) -> dict:
        session = self._check_running()
        assert session.bridge is not None
        return await observe(session.bridge)

    async def _call_tool(self, name: str, arguments: dict) -> dict:
        if name == "GetObservationTool":
            validate_tool(name, arguments)
            return await self._observe_structured()
        async with self._io:
            session = self._check_running()
            assert session.bridge is not None
            task = asyncio.create_task(execute_tool(session.bridge, name, arguments))
            self._active_tool = task
            try:
                return await task
            finally:
                self._active_tool = None

    async def _cancel_tool(self) -> None:
        task = self._active_tool
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def begin(self) -> None:
        async with self._lifecycle:
            if self.phase != "ready" or self._session is None:
                raise RuntimeError("begin requires an initialized, not-yet-started game")
            self.phase = "beginning"
            if self.recording:
                assert self._session.window_id is not None
                self._recorder = WindowRecording(
                    self._session.window_id, self._session.config.display,
                    self.output_dir / "video.mp4", self.recording_fps,
                )
                self._stack.push_async_callback(self._recorder.stop)
                await self._recorder.start()
            self._boundary["begin_requested_at_ns"] = time.monotonic_ns()
            await self._session.begin_task()
            self._boundary["begin_acknowledged_at_ns"] = time.monotonic_ns()
            self.phase = "running"
            self._write_json("boundaries.json", self._boundary)

    async def end(self) -> None:
        async with self._lifecycle:
            if self.phase == "ended":
                return
            if self.phase != "running" or self._session is None:
                raise RuntimeError("end requires a running game")
            self._stopped.set()
            self.phase = "ending"
            self._boundary["end_requested_at_ns"] = time.monotonic_ns()
            await self._cancel_tool()
            async with self._io:
                assert self._session.server is not None
                await self._session.stop_participant()
                feedback = await self._session.server.command("tick freeze")
                if not any("The game is frozen" in line for line in feedback):
                    raise RuntimeError("Could not confirm final world freeze")
            self._boundary["end_acknowledged_at_ns"] = time.monotonic_ns()
            self.phase = "ended"
            self._write_json("boundaries.json", self._boundary)

    async def save_snapshot(self, destination: Path) -> Path:
        async with self._lifecycle:
            if self.phase not in ("ready", "ended") or self._session is None:
                raise RuntimeError("Snapshots require the initial or terminal frozen boundary")
            destination = Path(destination).absolute()
            world = self._session.world.resolve()
            resolved = destination.resolve()
            if destination.is_symlink() or resolved == world or world in resolved.parents or resolved in world.parents:
                raise ValueError("Snapshot destination must be separate from the live world")
            if destination.exists():
                raise FileExistsError(f"Snapshot already exists: {destination}")
            server = self._session.server
            assert server is not None
            started = time.monotonic_ns()
            feedback = await server.command("save-off")
            if not any("Automatic saving is now disabled" in line for line in feedback):
                raise RuntimeError("Could not confirm disabling automatic saves")
            try:
                feedback = await server.command("save-all flush")
                if not any("Saved the game" in line for line in feedback):
                    raise RuntimeError("Server did not confirm save-all flush")
                saved = time.monotonic_ns()
                if any(path.is_symlink() for path in world.rglob("*")):
                    raise ValueError("Live world contains symlinks; refusing an unsafe snapshot")
                shutil.copytree(world, destination, ignore=shutil.ignore_patterns("session.lock"))
                hashes = {
                    str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(destination.rglob("*")) if path.is_file()
                }
                metadata = {
                    "phase": self.phase, "player_uuid": str(self.player_uuid),
                    "capture_started_at_ns": started, "save_acknowledged_at_ns": saved,
                    "copied_at_ns": time.monotonic_ns(), "boundaries": dict(self._boundary),
                    "sha256": hashes,
                    "semantics": "Server save after acknowledged tick freeze; player packets are not engine-frozen.",
                }
                with (destination / "_livequest_snapshot.json").open("x") as stream:
                    json.dump(metadata, stream, indent=2)
            finally:
                feedback = await server.command("save-on")
                if not any("Automatic saving is now enabled" in line for line in feedback):
                    raise RuntimeError("Could not confirm restoring automatic saves")
            return destination

    async def close(self) -> None:
        self._stopped.set()
        async with self._lifecycle:
            if self.phase == "closed":
                return
            await self._cancel_tool()
            async with self._io:
                try:
                    await self._stack.aclose()
                finally:
                    self.phase = "closed"

    def _write_json(self, name: str, value: dict) -> None:
        path = self.output_dir / name
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
