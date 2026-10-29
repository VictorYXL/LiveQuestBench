"""Veloren lifecycle: shared real client, distinct public VM/ST permissions."""

import asyncio
from contextlib import AsyncExitStack
import hashlib
import json
import os
from pathlib import Path
import time

from Xlib import X, display

from game.backends.x11.actions import ActionResult, WindowActions
from game.backends.x11.capture import CapturedFrame, WindowCapture
from game.backends.x11.display import VirtualDisplay
from game.backends.x11.interface import MotorInterface, execute_actions
from game.backends.x11.recording import WindowRecording
from game.base_game import AgentAccessClosed, BaseGame
from game.veloren.runtime.session import VelorenSession
from game.veloren.fixture import validate_fixture
from game.veloren.structured_tools.interface import StructuredInterface, project, validate_tool


class VelorenGame(BaseGame[MotorInterface | StructuredInterface]):
    def __init__(
        self, *, output_dir: Path, fixture: dict, track: str = "visual_motor",
        headless: bool = True, display_name: str | None = None,
        recording: bool = False, recording_fps: int = 10, recording_path: Path | None = None,
    ) -> None:
        if track not in ("visual_motor", "structured_tool"):
            raise ValueError("track must be visual_motor or structured_tool")
        fixture = validate_fixture(fixture)
        if type(headless) is not bool or type(recording) is not bool:
            raise ValueError("headless and recording must be booleans")
        if type(recording_fps) is not int or not 1 <= recording_fps <= 60:
            raise ValueError("recording_fps must be an integer in [1, 60]")
        self.output_dir = Path(output_dir).resolve()
        self.recording_path = Path(recording_path).resolve() if recording_path is not None else self.output_dir / "video.mp4"
        self.track, self.fixture, self.headless = track, fixture, headless
        self.display_name, self.recording, self.recording_fps = display_name, recording, recording_fps
        self.phase = "new"
        self._stack = AsyncExitStack()
        self._lifecycle = asyncio.Lock()
        self._io = asyncio.Lock()
        self._stopped = asyncio.Event()
        self._session: VelorenSession | None = None
        self._capture: WindowCapture | None = None
        self._actions: WindowActions | None = None
        self._recorder: WindowRecording | None = None
        self._active_tool: asyncio.Task | None = None
        self._boundary: dict[str, int] = {}
        self._window_id: int | None = None
        self._interface = (MotorInterface(self._observe, self._act) if track == "visual_motor"
                           else StructuredInterface(self._observe_structured, self._call_tool))
        self.team_role: str | None = None
        self.shared_owner: VelorenGame | None = None
        self.shared_world: dict | None = None

    def _write(self, name: str, value: dict) -> None:
        (self.output_dir / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")

    async def start(self) -> None:
        async with self._lifecycle:
            if self.phase != "new":
                raise RuntimeError("Use a fresh VelorenGame for each episode")
            self.phase = "starting"
            try:
                self.output_dir.mkdir(parents=True, exist_ok=False)
                if self.headless and self.display_name is None:
                    virtual = VirtualDisplay()
                    self._stack.push_async_callback(virtual.close)
                    self.display_name = await virtual.start(self.output_dir / "xvfb.log")
                else:
                    self.display_name = self.display_name or os.environ.get("DISPLAY")
                if not self.display_name:
                    raise RuntimeError("Desktop mode requires an authorized DISPLAY")
                self._session = VelorenSession(self.output_dir, self.display_name, self.track, self.fixture)
                self._session.team_role = self.team_role
                self._session.attachment = self.shared_owner.shared_world if self.shared_owner else None
                self._stack.push_async_callback(self._session.close)
                ready = await self._session.start()
                self.shared_world = ready["shared_world"]
                self._capture = WindowCapture(self.display_name, title_prefix="Veloren")
                self._stack.callback(self._capture.close)
                connection = display.Display(self.display_name)
                try:
                    windows = self._capture.list_windows()
                    owned = []
                    for info in windows:
                        window = connection.create_resource_object("window", info.window_id)
                        pid = window.get_full_property(connection.intern_atom("_NET_WM_PID"), X.AnyPropertyType)
                        if pid is not None and list(pid.value) == [ready["renderer_pid"]]:
                            owned.append(window)
                    if len(owned) != 1:
                        raise RuntimeError("Could not identify exactly one owned Veloren window")
                    window = owned[0]
                    self._window_id = window.id
                    window.set_input_focus(X.RevertToParent, X.CurrentTime)
                    geometry = window.get_geometry()
                    window.warp_pointer(geometry.width // 2, geometry.height // 2)
                    connection.sync()
                finally:
                    connection.close()
                self._actions = WindowActions(self._window_id, self.display_name)
                self._stack.callback(self._actions.close)
                self._write("environment.json", {**ready, "track": self.track, "fixture": self.fixture,
                                                "headless": self.headless, "recording": self.recording})
                self.phase = "ready"
                self._boundary["ready_at_ns"] = time.monotonic_ns()
                self._write("boundaries.json", self._boundary)
            except BaseException as error:
                self.phase = "failed"
                try:
                    await self._stack.aclose()
                except BaseException as cleanup_error:
                    raise BaseExceptionGroup("Veloren startup and cleanup failed", [error, cleanup_error])
                raise

    def get_agent_interface(self) -> MotorInterface | StructuredInterface:
        if self.phase not in ("ready", "running"):
            raise RuntimeError("Game interface requires initialized play")
        return self._interface

    def get_instructions(self) -> str:
        prompts = Path(__file__).parent / "prompts"
        return "\n".join((prompts / name).read_text().strip()
                         for name in ("introduction.txt", f"{self.track}.txt"))

    def _check_running(self) -> VelorenSession:
        if self.phase != "running" or self._stopped.is_set() or self._session is None:
            raise AgentAccessClosed("Agent access is only available during running play")
        self._session.check_ready()
        if self._recorder is not None and self._recorder.task is not None and self._recorder.task.done():
            self._recorder.task.result()
            raise RuntimeError("Recording stopped during play")
        return self._session

    async def _observe(self) -> CapturedFrame:
        async with self._io:
            self._check_running()
            assert self._capture is not None and self._actions is not None
            self._actions.check_ready()
            return self._capture.capture(self._window_id)

    async def _act(self, commands: list[dict[str, object]]) -> list[ActionResult]:
        async with self._io:
            self._check_running()
            assert self._actions is not None
            return await execute_actions(self._actions, commands, self._stopped)

    async def _observe_structured(self) -> dict:
        session = self._check_running()
        observation = project(await session.request("observe"),
                              rpg=any(key in self.fixture for key in (
                                  "native_site", "merchant", "contract", "message_contract", "market")),
                              skills="sword_skill_points" in self.fixture, peer=self.team_role is not None,
                              energy=self.fixture.get("public_energy", False))
        if self.fixture.get("encounters"):
            observation["profile"] = ("veloren-native-market-expedition-tools" if "merchant" in self.fixture
                                      else "veloren-native-fixed-tools-combat")
        if "contract" in self.fixture:
            observation["profile"] = "veloren-native-contract-tools"
        return observation

    async def _call_tool(self, name: str, arguments: dict) -> dict:
        native, converted = validate_tool(name, arguments)
        async with self._io:
            session = self._check_running()
            self._active_tool = asyncio.create_task(
                session.request("action", timeout=None, action_type=native, **converted),
            )
            try:
                result = await self._active_tool
                if native == "inspect_terrain" and result.get("status") != "refused":
                    if result.get("terrain_query_schema_version") != "1.0":
                        raise ValueError("Unsupported native terrain query response")
                    return {"action_type": native, "status": "completed", "detail": result}
                return {key: result[key] for key in (
                    "action_type", "status", "started_tick", "finished_tick", "detail",
                ) if key in result}
            finally:
                self._active_tool = None

    async def begin(self) -> None:
        async with self._lifecycle:
            if self.phase != "ready" or self._session is None:
                raise RuntimeError("begin requires an initialized, not-yet-started game")
            self.phase = "beginning"
            if self.recording:
                assert self._window_id is not None and self.display_name is not None
                self._recorder = WindowRecording(
                    self._window_id, self.display_name, self.recording_path, self.recording_fps,
                    title_prefix="Veloren",
                )
                self._stack.push_async_callback(self._recorder.stop)
                await self._recorder.start()
            self._boundary["begin_requested_at_ns"] = time.monotonic_ns()
            await self._session.request("begin")
            self._boundary["begin_acknowledged_at_ns"] = time.monotonic_ns()
            self.phase = "running"
            self._write("boundaries.json", self._boundary)

    async def _cancel_tool(self) -> None:
        if self._active_tool is not None and not self._active_tool.done():
            self._active_tool.cancel()
            try:
                await self._active_tool
            except asyncio.CancelledError:
                pass

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
                assert self._actions is not None
                self._actions.release_all()
                await self._session.request("end")
            self._boundary["end_acknowledged_at_ns"] = time.monotonic_ns()
            self.phase = "ended"
            self._write("boundaries.json", self._boundary)

    async def save_snapshot(self, destination: Path) -> Path:
        async with self._lifecycle:
            if self.phase not in ("ready", "ended") or self._session is None:
                raise RuntimeError("Snapshots require an initial or terminal public boundary")
            destination = Path(destination).absolute()
            if destination.exists():
                raise FileExistsError(f"Snapshot already exists: {destination}")
            if any(part.is_symlink() for part in (destination, *destination.parents)):
                raise ValueError("Snapshot paths must not contain symlinks")
            started = time.monotonic_ns()
            # Long native journals can exceed the normal RPC timeout after the public gate closes.
            observation = await self._session.request("snapshot", timeout=180)
            destination.mkdir(parents=True)
            payload = json.dumps(observation, indent=2, allow_nan=False).encode()
            (destination / "observation.json").write_bytes(payload)
            (destination / "_livequest_snapshot.json").write_text(json.dumps({
                "schema": "veloren-endpoint", "phase": self.phase,
                "session_id": observation["session_id"], "capture_started_at_ns": started,
                "captured_at_ns": time.monotonic_ns(), "sha256": hashlib.sha256(payload).hexdigest(),
                "boundaries": self._boundary,
                "semantics": "Private native client readback after public gate; world continues, not an atomic server save.",
            }, indent=2) + "\n")
            return destination

    async def close(self) -> None:
        self._stopped.set()
        async with self._lifecycle:
            if self.phase == "closed":
                return
            await self._cancel_tool()
            try:
                await self._stack.aclose()
            finally:
                self.phase = "closed"
