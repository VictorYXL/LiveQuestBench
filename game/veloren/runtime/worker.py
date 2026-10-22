"""Private VelorenBench runtime reuse, isolated from public Agent interfaces."""

import asyncio
from contextlib import AsyncExitStack, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
from uuid import uuid4

from scripts.rpg_benchmark import runtime, setup
from scripts.rpg_benchmark.native import Journal, NativeBridge, NativeConfig, NativeRefusal, private_server
from scripts.rpg_benchmark.renderer import RendererBridge


class LocalRenderer(RendererBridge):
    async def start(self) -> None:
        self.ready = asyncio.get_running_loop().create_future()
        self.renderer_ready = asyncio.get_running_loop().create_future()
        settings = self.out / "renderer-config"
        settings.mkdir()
        (settings / "settings.ron").write_text(
            '(show_disclaimer:false,networking:(use_srv:false,use_quic:false,enable_discord_integration:false),'
            'audio:(output:Off),graphics:(terrain_view_distance:4,entity_view_distance:4,lod_distance:0,'
            'max_fps:Max(30),max_background_fps:Max(30),window:(size:(960,540),maximised:false),'
            'fullscreen:(enabled:false),render_mode:(shadow:None,cloud:Minimal,bloom:Off,profiler_enabled:false)),)\n'
        )
        self.stderr = (self.out / "renderer.log").open("x")
        env = os.environ | {
            "HOME": str(self.out / "home"), "VELOREN_ASSETS": self.renderer["paths"]["assets"],
            "VELOREN_SESSION_ID": self.name, "VOXYGEN_CONFIG": str(settings),
            "VELOREN_USERDATA": str(self.out / "renderer-userdata"), "WGPU_BACKEND": "vulkan",
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
        }
        Path(env["HOME"]).mkdir(exist_ok=True)
        self.process = await asyncio.create_subprocess_exec(
            self.renderer["paths"]["executable"], "--server", f"127.0.0.1:{self.port}",
            "--client-type", "game", "--agent-bridge", "--agent-frame-dir", str(self.frames),
            "--agent-observation", "hybrid", "--agent-offline-user", self.name,
            "--agent-character", self.name, "--agent-create-character",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=self.stderr, env=env, limit=16 * 1024 * 1024,
        )
        from scripts.rpg_benchmark.lifecycle import process_start_ticks
        self.start_ticks = process_start_ticks(self.process.pid)
        self.reader_task = asyncio.create_task(self._read())
        await asyncio.wait_for(asyncio.shield(self.ready), 120)
        await asyncio.wait_for(asyncio.shield(self.renderer_ready), 120)
        if self.renderer_ready.result()["data"]["same_client"] is not True:
            raise RuntimeError("Renderer is not the controlled native player")


class Session:
    def __init__(self, config: dict, output: Path, track: str, fixture: str):
        self.config, self.output, self.track, self.fixture = config, output, track, fixture
        self.stack = AsyncExitStack()
        self.started = False
        self.running = False
        self.record = {"username": "Admin" + uuid4().hex[:10]}

    async def start(self) -> dict:
        if self.started:
            raise RuntimeError("Session is single-use")
        self.started = True
        cfg = self.config
        for path, digest in cfg["sha256"].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Prepared runtime changed: {path}")
        selected = runtime.load_runtime(Path(cfg["upstream_runtime"]), cfg["upstream_sha256"], backend="renderer")
        renderer = selected["renderer"]
        renderer["paths"]["executable"] = cfg["renderer"]
        paths = renderer["paths"]
        native = NativeConfig(
            server=Path(paths["server"]), bridge=Path(selected["renderer_fixture_helper"]["executable"]),
            assets=Path(paths["assets"]), root=Path(paths["source_root"]), small_world=False,
        )
        journal = Journal(self.output / "native.jsonl")
        self.stack.callback(journal.close)
        port, userdata = await self.stack.enter_async_context(private_server(self.output, self.record, native))
        admin = NativeBridge(self.output, self.record["username"], port, userdata, journal, native)
        self.stack.push_async_callback(admin.close)
        await admin.start()
        os.environ["LIVEQUEST_PHYSICAL_INPUT"] = "1" if self.track == "visual_motor" else "0"
        self.actor = LocalRenderer(
            self.output, "Player" + uuid4().hex[:10], port, userdata, journal, native,
            renderer=renderer, frames=self.output / "frames",
        )
        self.stack.push_async_callback(self.actor.close)
        await self.actor.start()
        opening = await setup.ready_observation(self.actor)
        if self.fixture == "movement":
            # A bounded, private setup platform, not a public movement shortcut.
            here = setup.position(opening)
            origin = [int(here[0]), int(here[1]), int(here[2]) + 20]
            await setup.site(admin, self.actor, "flat", {"flat_origin": origin}, size=(12, 12))
        elif self.fixture != "spawn":
            raise ValueError("Unknown fixture")
        opening = await setup.ready_observation(self.actor)
        setup.require_living(opening)
        self.record["actor"] = self.actor.ready.result()
        (self.output / "fixture.json").write_text(json.dumps({
            "fixture": self.fixture, "opening": opening,
        }, indent=2) + "\n")
        return {"renderer_pid": self.actor.process.pid, "actor": self.actor.ready.result(),
                "runtime": cfg, "display": os.environ["DISPLAY"]}

    async def frame_fence(self) -> dict:
        current = await self.actor.request("observe", origin="lifecycle")
        return {"schema_version": "1.0", "expected_session_id": current["session_id"],
                "actor": current["control_actor"]}

    async def physical(self, enabled: bool) -> dict:
        return await self.actor.request(
            "physical_input", {**await self.frame_fence(), "enabled": enabled}, origin="lifecycle",
        )

    async def dispatch(self, operation: str, args: dict) -> dict:
        if operation == "start":
            return await self.start()
        if operation == "begin":
            if self.track == "visual_motor":
                await self.physical(True)
            self.running = True
            return {"running": True}
        if operation == "end":
            self.running = False
            if self.track == "visual_motor":
                await self.physical(False)
            await setup.action(self.actor, "stop", origin="cleanup", require_completed=True)
            return {"running": False}
        if operation == "snapshot":
            if self.running:
                raise RuntimeError("Snapshot requires a closed public gate")
            return await self.actor.request("observe", origin="snapshot")
        if operation == "inspect_frame":
            return await self.actor.request("frame", await self.frame_fence(), origin="private-validation")
        if not self.running:
            raise RuntimeError("Public native operation outside running boundary")
        if operation == "observe":
            return await self.actor.request("observe", origin="agent")
        if operation == "action":
            if self.track != "structured_tool":
                raise PermissionError("VM cannot invoke native skills")
            if args.get("action_type") not in (
                "move_forward", "move_backward", "move_left", "move_right",
                "turn", "jump", "pickup", "use_item", "craft",
            ):
                raise PermissionError("Native action is not in the fixed public skill set")
            try:
                return await setup.action(self.actor, origin="agent", require_completed=False, **args)
            except NativeRefusal as error:
                expected = {
                    ("pickup", "invalid_action", "no pickable item within range"),
                    ("pickup", "pickup_send_rejected",
                     "local client does not send pickup while dead; not a server refusal"),
                    ("use_item", "invalid_action", "inventory slot is empty or unavailable"),
                }
                refusal = error.native_error
                if (args["action_type"], refusal.get("code"), refusal.get("message")) not in expected:
                    raise
                return {"action_type": args["action_type"], "status": "refused", "detail": refusal}
        raise ValueError(f"Unknown worker operation: {operation}")

    async def close(self) -> None:
        try:
            await self.stack.aclose()
        finally:
            (self.output / "native-cleanup.json").write_text(json.dumps(self.record, indent=2) + "\n")


async def main() -> None:
    config_path, output, track, fixture = sys.argv[1:]
    session = Session(json.loads(Path(config_path).read_text()), Path(output), track, fixture)
    output_stream = sys.stdout
    pending = set()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop.set)

    async def respond(request):
        try:
            value = await session.dispatch(request["op"], request["arguments"])
            response = {"id": request["id"], "ok": True, "result": value}
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            response = {"id": request["id"], "ok": False,
                        "error": {"type": type(error).__name__, "message": str(error)}}
        output_stream.write(json.dumps(response, allow_nan=False) + "\n")
        output_stream.flush()

    reader = asyncio.StreamReader(limit=16 * 1024 * 1024)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    with redirect_stdout(sys.stderr):
        try:
            while not stop.is_set():
                reading = asyncio.create_task(reader.readline())
                stopping = asyncio.create_task(stop.wait())
                done, _ = await asyncio.wait({reading, stopping}, return_when=asyncio.FIRST_COMPLETED)
                stopping.cancel()
                await asyncio.gather(stopping, return_exceptions=True)
                if reading not in done:
                    reading.cancel()
                    await asyncio.gather(reading, return_exceptions=True)
                    break
                line = reading.result()
                if not line:
                    break
                request = json.loads(line)
                if request["op"] == "close":
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    await session.close()
                    output_stream.write(json.dumps({"id": request["id"], "ok": True, "result": {"closed": True}}) + "\n")
                    output_stream.flush()
                    break
                task = asyncio.create_task(respond(request))
                pending.add(task)
                task.add_done_callback(pending.discard)
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
