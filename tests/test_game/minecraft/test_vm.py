"""VM pixels and basic motor control, without LLM calls or screenshot dumps."""

import asyncio
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

nbtlib = pytest.importorskip("nbtlib", reason="Install the minecraft extra")
pytest.importorskip("Xlib", reason="Install the minecraft extra")
pytest.importorskip("PIL", reason="Install the minecraft extra")

from core.backends.x11.actions import ActionError
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.visual_motor.interface import action_tool_schema, validate_actions
from game.minecraft.visual_motor.interface import MotorInterface


def test_motor_commands() -> None:
    assert validate_actions([{"name": "wait", "arguments": {"milliseconds": 10000}}])
    with pytest.raises(ActionError):
        validate_actions([{"name": "wait", "arguments": {"milliseconds": 10001}}])
    with pytest.raises(ActionError):
        validate_actions([{"name": "console", "arguments": {"command": "give"}}])


def test_motor_schema_and_validation_agree() -> None:
    from agent_framework.llm_client.responses import array, obj, text

    schema = action_tool_schema()
    commands = obj(obj(obj(schema["parameters"])["properties"])["commands"])
    assert commands["minItems"] == 1 and commands["maxItems"] == 64
    variants = array(obj(commands["items"])["anyOf"])
    names = set()
    for raw in variants:
        properties = obj(obj(raw)["properties"])
        name = text(array(obj(properties["name"])["enum"])[0])
        names.add(name)
        arguments_schema = obj(properties["arguments"])
        fields = obj(arguments_schema["properties"])
        assert set(array(arguments_schema["required"])) == set(fields)
        assert arguments_schema["additionalProperties"] is False
        arguments = {
            field: array(obj(spec)["enum"])[0] if "enum" in obj(spec) else obj(spec)["minimum"]
            for field, spec in fields.items()
        }
        assert validate_actions([{"name": name, "arguments": arguments}]) == [(name, arguments)]
        for field, raw_spec in fields.items():
            spec = obj(raw_spec)
            if "enum" in spec:
                valid = array(spec["enum"])
                invalid = ["not-a-supported-input", 0, True]
            else:
                low, high = spec["minimum"], spec["maximum"]
                assert isinstance(low, int) and isinstance(high, int)
                valid, invalid = [low, high], [low - 1, high + 1, 0.5, True, "0"]
            for value in valid:
                assert validate_actions([{"name": name, "arguments": {**arguments, field: value}}])
            for value in invalid:
                with pytest.raises(ActionError):
                    validate_actions([{"name": name, "arguments": {**arguments, field: value}}])
        with pytest.raises(ActionError):
            validate_actions([{"name": name, "arguments": {**arguments, "extra": 1}}])
        for field in arguments:
            with pytest.raises(ActionError):
                validate_actions([{"name": name, "arguments": {
                    key: value for key, value in arguments.items() if key != field
                }}])
    assert names == {
        "key_down", "key_up", "mouse_down", "mouse_up", "mouse_move_relative",
        "mouse_move_to", "mouse_scroll", "wait", "release_all",
    }
    release = {"name": "release_all", "arguments": {}}
    assert len(validate_actions([release] * 64)) == 64
    for invalid in ([], [release] * 65, [{"name": "wait", "arguments": {"milliseconds": 5001}}] * 2):
        with pytest.raises(ActionError):
            validate_actions(invalid)
    assert validate_actions([{"name": "wait", "arguments": {"milliseconds": 5000}}] * 2)

    obj(schema["parameters"])["required"] = []
    assert obj(action_tool_schema()["parameters"])["required"] == ["commands"]


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in VM check")
def test_vm_observation_and_movement(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool,
) -> None:
    monkeypatch.setenv("MINECRAFT_PRISM_ROOT", "/nonexistent-livequest-prism")
    root = Path(os.environ.get(
        "MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[3] / "output" / "test"),
    )).resolve()
    output = root / f"minecraft-vm-{uuid4().hex}"
    print(f"Minecraft VM artifacts: {output}")
    state = PlayerState(position=(0.5, 72, 0.5), yaw=180)
    game = MinecraftGame(
        fixture=Path(os.environ["MINECRAFT_TEST_FIXTURE"]) if os.environ.get("MINECRAFT_TEST_FIXTURE") else None,
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
            first = await interface.observe()
            assert first.image.mode == "RGB" and first.image.width > 0 and first.image.height > 0
            extrema = [first.image.getchannel(channel).getextrema() for channel in ("R", "G", "B")]
            assert any(low != high for low, high in extrema)
            await interface.act([
                {"name": "key_down", "arguments": {"key": "2"}},
                {"name": "wait", "arguments": {"milliseconds": 150}},
                {"name": "key_up", "arguments": {"key": "2"}},
                {"name": "key_down", "arguments": {"key": "w"}},
                {"name": "wait", "arguments": {"milliseconds": 1000}},
                {"name": "key_up", "arguments": {"key": "w"}},
                {"name": "wait", "arguments": {"milliseconds": 500}},
                {"name": "mouse_move_relative", "arguments": {"dx": 60, "dy": 0}},
            ])
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
            await asyncio.sleep(1)
            await game.end()
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
