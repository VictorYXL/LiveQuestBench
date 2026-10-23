"""VM pixels and basic motor control, without LLM calls or screenshot dumps."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

nbtlib = pytest.importorskip("nbtlib", reason="Install the minecraft extra")
pytest.importorskip("Xlib", reason="Install the minecraft extra")
pytest.importorskip("PIL", reason="Install the minecraft extra")

from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.visual_motor.interface import MotorInterface, agent_tools
from game.backends.x11.actions import ActionError, ActionResult
from game.base_game import AgentAccessClosed


def test_motor_argument_rejection_and_execution_failures(caplog):
    async def run():
        calls = []

        async def observe():
            raise AssertionError("No observation required for argument validation")

        async def act(commands):
            calls.append(commands)
            return [ActionResult("wait", 1, 2)]

        tool = agent_tools()[0]
        interface = MotorInterface(observe, act)
        invalid = [
            {}, {"commands": "bad"}, {"commands": []}, {"commands": [None]},
            {"commands": [{"name": "wait", "arguments": {"milliseconds": True}}]},
            {"commands": [{"name": "key_down", "arguments": {"key": "unsupported"}}]},
            {"commands": [
                {"name": "key_down", "arguments": {"key": "w"}},
                *[{"name": "wait", "arguments": {"milliseconds": ms}} for ms in (100, 200, 700, 10000)],
            ]},
        ]
        for arguments in invalid:
            result = json.loads(await tool.execute(interface, arguments))
            assert result["success"] is False and result["error"] == "invalid_action_arguments"
            assert result["executed_commands"] == 0 and "unchanged" in result["held_controls"]
            assert not calls
        assert "11000" in result["message"] and "10000" in result["message"]
        assert "Motor batch rejected before execution" in caplog.text
        valid = {"commands": [
            {"name": "wait", "arguments": {"milliseconds": 3000}},
            {"name": "wait", "arguments": {"milliseconds": 7000}},
        ]}
        result = json.loads(await tool.execute(interface, valid))
        assert result == [{"operation": "wait", "started_at_ns": 1, "finished_at_ns": 2, "applied_delta": None}]
        assert calls == [valid["commands"]]

        async def broken_act(commands):
            raise ActionError("Target window lost keyboard focus; input stopped.")

        with pytest.raises(ActionError, match="lost keyboard focus"):
            await tool.execute(MotorInterface(observe, broken_act), valid)

    asyncio.run(run())


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in VM check")
def test_vm_observation_and_movement(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool, minecraft_world_path: Path,
) -> None:
    monkeypatch.setenv("MINECRAFT_PRISM_ROOT", "/nonexistent-livequest-prism")
    root = Path(os.environ.get(
        "MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[3] / "output" / "test"),
    )).resolve()
    output = root / f"minecraft-vm-{uuid4().hex}"
    print(f"Minecraft VM artifacts: {output}")
    state = PlayerState(position=(0.5, 72, 0.5), yaw=180)
    game = MinecraftGame(
        world_path=minecraft_world_path,
        output_dir=output,
        player_state=state,
        recording=recording, recording_fps=10,
        headless=headless,
    )

    async def run() -> None:
        try:
            await game.start()
            interface = game.get_agent_interface()
            assert isinstance(interface, MotorInterface)
            assert set(interface.__dataclass_fields__) == {"observe", "act"}
            with pytest.raises(RuntimeError):
                await interface.observe()
            await game.save_snapshot(output / "before")
            await game.begin()
            await asyncio.sleep(1)
            tool = agent_tools()[0]
            rejected = json.loads(await tool.execute(interface, {"commands": [
                {"name": "key_down", "arguments": {"key": "3"}},
                {"name": "wait", "arguments": {"milliseconds": 1000}},
                {"name": "wait", "arguments": {"milliseconds": 10000}},
            ]}))
            assert rejected["executed_commands"] == 0 and rejected["success"] is False
            first = await interface.observe()
            assert first.image.mode == "RGB" and first.image.width > 0 and first.image.height > 0
            extrema = [first.image.getchannel(channel).getextrema() for channel in ("R", "G", "B")]
            assert any(low != high for low, high in extrema)
            accepted = json.loads(await tool.execute(interface, {"commands": [
                {"name": "key_down", "arguments": {"key": "2"}},
                {"name": "wait", "arguments": {"milliseconds": 150}},
                {"name": "key_up", "arguments": {"key": "2"}},
                {"name": "key_down", "arguments": {"key": "w"}},
                {"name": "wait", "arguments": {"milliseconds": 1000}},
                {"name": "key_up", "arguments": {"key": "w"}},
                {"name": "wait", "arguments": {"milliseconds": 500}},
                {"name": "mouse_move_relative", "arguments": {"dx": 60, "dy": 0}},
            ]}))
            assert isinstance(accepted, list) and len(accepted) == 8
            # Let Minecraft recenter the pointer between bounded downward motions.
            for _ in range(6):
                await interface.act([
                    {"name": "mouse_move_relative", "arguments": {"dx": 0, "dy": 100}},
                    {"name": "wait", "arguments": {"milliseconds": 100}},
                ])
            await interface.act([
                {"name": "wait", "arguments": {"milliseconds": 750}},
                {"name": "mouse_down", "arguments": {"button": "left"}},
                {"name": "wait", "arguments": {"milliseconds": 2000}},
                {"name": "mouse_up", "arguments": {"button": "left"}},
                {"name": "wait", "arguments": {"milliseconds": 750}},
            ])
            second = await interface.observe()
            assert second.frame_id > first.frame_id and second.captured_at_ns > first.captured_at_ns
            pending = asyncio.create_task(interface.act([
                {"name": "wait", "arguments": {"milliseconds": 10000}},
            ]))
            await asyncio.sleep(0.1)
            assert not pending.done()
            await game.end()
            with pytest.raises(AgentAccessClosed, match="during wait"):
                await pending
            with pytest.raises(RuntimeError):
                await interface.observe()
            with pytest.raises(RuntimeError):
                await interface.act([{"name": "key_down", "arguments": {"key": "w"}}])
            after = await game.save_snapshot(output / "after")
            assert game.player_uuid is not None
            actual = nbtlib.load(after / "playerdata" / f"{game.player_uuid}.dat")
            assert int(actual["SelectedItemSlot"]) == 1
            assert sum((float(actual["Pos"][axis]) - state.position[axis]) ** 2 for axis in (0, 2)) > 0.01
            yaw_change = (float(actual["Rotation"][0]) - state.yaw + 180) % 360 - 180
            assert abs(yaw_change) > 1
            assert float(actual["Rotation"][1]) > 80
        finally:
            await game.close()
        if game.recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )

    asyncio.run(run())
