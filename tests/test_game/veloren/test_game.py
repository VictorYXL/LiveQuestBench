"""Real Veloren pixel/motor and native-tool lifecycle checks."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

pytest.importorskip("Xlib", reason="Install the veloren extra to run game checks")
pytest.importorskip("PIL", reason="Install the veloren extra to run game checks")

from game.backends.x11.interface import MotorInterface
from game.base_game import AgentAccessClosed
from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory, inventory_counts
from game.veloren.game import VelorenGame
from game.veloren.structured_tools.interface import StructuredInterface, agent_tools


def test_native_tool_wait_uses_episode_cutoff_and_releases_lock(tmp_path, veloren_fixture):
    from types import SimpleNamespace

    game = VelorenGame(output_dir=tmp_path / "game", fixture=veloren_fixture, track="structured_tool")
    game.phase = "running"
    calls = []

    async def scenario():
        submitted = asyncio.Event()
        cancelled = asyncio.Event()

        async def request(method, *, timeout=60, **arguments):
            calls.append((method, timeout, arguments))
            submitted.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        game._session = SimpleNamespace(check_ready=lambda: None, request=request)
        action = asyncio.create_task(game._call_tool("JumpTool", {}))
        await submitted.wait()
        await game._cancel_tool()
        with pytest.raises(asyncio.CancelledError):
            await action
        assert cancelled.is_set()
        assert not game._io.locked()
        assert game._active_tool is None

    asyncio.run(scenario())
    assert calls == [("action", None, {"action_type": "jump"})]


def test_native_rpc_keeps_payload_operation_separate_from_transport_method(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from game.veloren.runtime.session import VelorenSession

    session = VelorenSession(tmp_path, ":test", "structured_tool", {})
    sent = {}

    class Input:
        def write(self, value):
            sent.update(json.loads(value))

        async def drain(self):
            session.pending[sent["id"]].set_result({"accepted": True})

    monkeypatch.setattr(session, "check_ready", lambda: None)
    monkeypatch.setattr(session, "process", SimpleNamespace(stdin=Input()))
    assert asyncio.run(session.request(
        "action", action_type="context_interact", operation="talk",
        target={"uid": 7, "lifecycle": "incarnation:Entity(7, 1)"},
    )) == {"accepted": True}
    assert sent["op"] == "action" and sent["arguments"]["operation"] == "talk"
    assert not session.pending


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_VELOREN_TEST") != "1", reason="Opt-in native Veloren test")
@pytest.mark.parametrize("track", ["visual_motor", "structured_tool"])
def test_native_movement_and_cutoff(track: str, headless: bool, recording: bool, veloren_fixture: dict) -> None:
    root = Path(__file__).resolve().parents[3] / "output/test"
    output = root / f"veloren-{track}-{uuid4().hex}"
    print(f"Veloren game artifacts: {output}")
    game = VelorenGame(output_dir=output, fixture=veloren_fixture, track=track, headless=headless, recording=recording)

    async def scenario() -> None:
        try:
            await game.start()
            public = game.get_agent_interface()
            with pytest.raises(AgentAccessClosed):
                await public.observe()
            before = await game.save_snapshot(output / "before")
            await game.begin()
            if isinstance(public, MotorInterface):
                frame = await public.observe()
                assert frame.image.size == (960, 540)
                assert any(low != high for low, high in frame.image.getextrema())
                frame.image.save(output / "frame.png")
                assert game._session is not None
                camera_before = await game._session.request("inspect_frame")
                await public.act([
                    {"name": "mouse_move_relative", "arguments": {"dx": 60, "dy": 0}},
                    {"name": "wait", "arguments": {"milliseconds": 200}},
                    {"name": "key_down", "arguments": {"key": "i"}},
                    {"name": "wait", "arguments": {"milliseconds": 100}},
                    {"name": "key_up", "arguments": {"key": "i"}},
                    {"name": "wait", "arguments": {"milliseconds": 200}},
                ])
                (await public.observe()).image.save(output / "inventory.png")
                camera_after = await game._session.request("inspect_frame")
                (output / "camera-check.json").write_text(json.dumps({
                    "before": camera_before, "after": camera_after,
                }, indent=2) + "\n")
                assert camera_after["hud"]["inventory"] is True
                assert abs(camera_after["camera"]["orientation_radians"][0]
                           - camera_before["camera"]["orientation_radians"][0]) > .01
                await public.act([
                    {"name": "key_down", "arguments": {"key": "i"}},
                    {"name": "wait", "arguments": {"milliseconds": 100}},
                    {"name": "key_up", "arguments": {"key": "i"}},
                    {"name": "wait", "arguments": {"milliseconds": 200}},
                ])
                await public.act([
                    {"name": "key_down", "arguments": {"key": "w"}},
                    {"name": "wait", "arguments": {"milliseconds": 200}},
                    {"name": "key_up", "arguments": {"key": "w"}},
                    {"name": "wait", "arguments": {"milliseconds": 300}},
                ])
                active = asyncio.create_task(public.act([
                    {"name": "mouse_down", "arguments": {"button": "left"}},
                    {"name": "key_down", "arguments": {"key": "w"}},
                    {"name": "wait", "arguments": {"milliseconds": 10000}},
                ]))
            else:
                assert isinstance(public, StructuredInterface)
                move_tool = next(tool for tool in agent_tools() if tool.name == "MoveTool")
                rejected = json.loads(await move_tool.execute(
                    public, {"direction": "forward", "duration_ticks": 121},
                ))
                assert rejected["error"] == "invalid_tool_arguments" and rejected["executed"] is False
                observation = await public.observe()
                assert observation["profile"] == "veloren-native-fixed-tools-v3"
                assert observation["local_geometry"]["scope"] == "body_local_loaded_terrain"
                assert (await public.call_tool("TurnTool", {"degrees": 20}))["status"] == "completed"
                assert (await public.call_tool("JumpTool", {}))["status"] == "completed"
                assert (await public.call_tool("PickupTool", {}))["status"] == "refused"
                assert (await public.call_tool("UseItemTool", {"slot": 99}))["status"] == "refused"
                assert (await public.call_tool("UseItemTool", {"slot": 1}))["status"] == "completed"
                recipe = observation["known_recipes"]["items"][0]["recipe"]
                assert (await public.call_tool("CraftTool", {"recipe": recipe, "amount": 1}))["status"] == "failed"
                receipt = json.loads(await move_tool.execute(public, {"direction": "forward", "duration_ticks": 20}))
                assert receipt["status"] == "completed"
                active = asyncio.create_task(public.call_tool(
                    "MoveTool", {"direction": "forward", "duration_ticks": 120},
                ))
            await asyncio.sleep(.15)
            if track == "visual_motor":
                held = await game._session.request("inspect_frame")
                assert "Primary" in held["physical_input"]["queued_inputs"]
            await asyncio.wait_for(game.end(), 10)
            try:
                await active
            except (asyncio.CancelledError, AgentAccessClosed):
                pass
            with pytest.raises(AgentAccessClosed):
                await public.observe()
            after = await game.save_snapshot(output / "after")
            if track == "visual_motor":
                released = await game._session.request("inspect_frame")
                assert released["physical_input"] == {"enabled": False, "queued_inputs": []}
            score = evaluate_displacement(before, after, min_distance=.5)
            assert score["success"], score
            assert evaluate_health(before, after, min_health=1)["success"]
            first = json.loads((before / "observation.json").read_text())
            last = json.loads((after / "observation.json").read_text())
            assert all(buff["kind"] != "Invulnerability"
                       for observation in (first, last) for buff in observation["survival"]["buffs"])
            retired = json.loads((output / "fixture.json").read_text())["administrator_retirement"]
            assert retired["confirmed_absent"]
            assert retired["uid"] != first["self_identity"]["uid"]
            assert all(entity["uid"] != retired["uid"]
                       for observation in (first, last) for entity in observation["nearby_entities"])
            assert last["tick"] > first["tick"]
            assert abs(last["look"][0] - first["look"][0]) > .01, "View input did not turn the native actor"
            assert evaluate_inventory(before, after, item="common.items.consumable.potion_minor", min_count=1)["success"]
            if track == "structured_tool":
                assert inventory_counts(first)["common.items.food.cheese"] == 1
                assert inventory_counts(last).get("common.items.food.cheese", 0) == 0
            (output / "result.json").write_text(json.dumps({
                "integration_status": "passed", "score": score,
                "client_updates_advanced": last["tick"] - first["tick"],
            }, indent=2) + "\n")
        finally:
            await game.close()
            await game.close()
        assert game._session is not None and game._session.process is not None
        assert game._session.process.returncode == 0
        native_cleanup = json.loads((output / "native-cleanup.json").read_text())
        assert native_cleanup["server_stopped"]
        assert any(buff["kind"] == "Invulnerability" for buff in native_cleanup["setup_admin_protection"])
        if recording:
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                            "-map", "0:v:0", "-f", "null", "-"],
                           check=True, capture_output=True, timeout=30)

    asyncio.run(scenario())
