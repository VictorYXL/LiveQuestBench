import copy
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

from benchmark.config import load_task
from benchmark.factory import make_game
from game.minecraft.fixtures import camel_delivery_flush_v4 as condition
from game.minecraft.fixtures import camel_delivery_registration as registration
from game.minecraft.runtime.session import copy_world
from game.minecraft.fixtures.camel_delivery_start import CourierInitializationServer


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "config/minecraft/fixtures/camel_courier_flush_v4"


@pytest.mark.parametrize("index", (0, 1))
@pytest.mark.parametrize("track", ("structured_tools", "visual_motor"))
def test_both_tracks_bind_the_original_hidden_v4_instance_and_explicit_scorer(monkeypatch, index, track):
    choose = Mock(return_value=index)
    monkeypatch.setattr(registration.secrets, "randbelow", choose)
    task = load_task(ROOT / f"config/minecraft/tasks/{track}/camel_courier_flush_v4.yaml")
    never = ROOT / "output/not-started-camel-registration-test"
    binding = make_game(task, never, headless=True, recording=False, recording_fps=5)
    choose.assert_called_once_with(2)
    assert binding.game.world_path == ASSETS / f"instance_{index}"
    assert registration.verify_initial(binding.game.world_path) == (.05, .20)[index]
    assert binding.game.player_state.position == [-42.5, 72.0, 1.5]
    assert binding.game.player_state.inventory == []
    assert task.task == condition.PUBLIC_GOAL
    assert task.time_limit_seconds == 1200
    assert task.evaluator == "camel_delivery_flush_v4"
    assert not task.evaluator_parameters
    assert not never.exists()
    assert binding.game.server_factory.func is CourierInitializationServer
    assert binding.game.server_factory.keywords["template"] == ASSETS / f"instance_{index}"
    if track == "structured_tools":
        assert {"InspectFurnaceTool", "FurnaceClickTool", "InspectVitalsTool",
                "GoToPositionTool", "DigTool", "PlaceTool", "RespawnTool"} <= set(task.tools)
    else:
        assert task.tools is None
    score = Mock(return_value={"success": False, "condition": condition.VERSION})
    # create_binding captures the selected evaluator, so bind again after replacing it.
    monkeypatch.setattr(condition, "evaluate", score)
    binding = make_game(task, never, headless=True, recording=False, recording_fps=5)
    binding.game.player_uuid = UUID("2688f575-edcc-37d3-b359-7ead8d40d728")
    assert binding.evaluate(Path("before"), Path("after"))["condition"] == condition.VERSION
    score.assert_called_once_with(Path("before"), Path("after"), binding.game.player_uuid)


def test_distribution_rejects_relabeling_both_assets_as_one_response(monkeypatch):
    data = json.loads((ASSETS / registration.MANIFEST).read_text())
    changed = copy.deepcopy(data)
    changed["worlds"][1]["movement_speed"] = .05
    monkeypatch.setattr(registration.json, "loads", lambda text: changed)
    with pytest.raises(ValueError, match="Both reviewed native response"):
        registration.select_world(ASSETS)


def test_release_readiness_rejects_the_simplified_player_start(monkeypatch):
    load = registration.nbtlib.load
    monkeypatch.setattr(registration.nbtlib, "load", lambda path: {
        "Pos": [6.0, 73.4, 22.5], "Inventory": [], "RootVehicle": {},
    } if Path(path).name == "player.dat" else load(path))
    with pytest.raises(ValueError, match="simplified mounted-A"):
        registration.verify_initial(ASSETS / "instance_0", "player")


@pytest.mark.parametrize("index", (0, 1))
def test_native_readiness_records_private_selection_and_rejects_another_instance(monkeypatch, tmp_path, index):
    monkeypatch.setattr(registration.secrets, "randbelow", lambda size: index)
    task = load_task(ROOT / "config/minecraft/tasks/structured_tools/camel_courier_flush_v4.yaml")
    binding = make_game(task, tmp_path, headless=True, recording=False, recording_fps=5)
    uuid = UUID("2688f575-edcc-37d3-b359-7ead8d40d728")
    binding.game.player_uuid = uuid
    before = tmp_path / "offline-before"
    copy_world(binding.game.world_path, before, binding.game.player_state, uuid)
    binding.game.player_state.verify(registration.nbtlib.load(before / "playerdata" / f"{uuid}.dat"), uuid)
    binding.verify_initial(before)
    private = json.loads((tmp_path / "native-camel-instance.json").read_text())
    assert private["instance_index"] == index
    assert private["condition"] == condition.VERSION
    assert private["private_authoring_provenance_not_agent_observation"]
    other = tmp_path / "offline-wrong-instance"
    copy_world(ASSETS / f"instance_{1 - index}", other, binding.game.player_state, uuid)
    with pytest.raises(RuntimeError, match="differs from the selected instance"):
        binding.verify_initial(other)


@pytest.mark.parametrize("index", (0, 1))
def test_start_restores_only_original_native_courier_after_freeze(monkeypatch, tmp_path, index):
    from game.minecraft.runtime.server import MinecraftServer
    from game.minecraft.evaluators.camel_delivery import original_camel
    _, original = original_camel(ASSETS / f"instance_{index}")
    expected = registration.nbtlib.parse_nbt(original.snbt())
    expected.pop("id", None)
    drifted = registration.nbtlib.parse_nbt(expected.snbt())
    drifted["Pos"][0] = registration.nbtlib.Double(-40.25)
    drifted["Motion"][1] = registration.nbtlib.Double(-.0784)
    drifted["Brain"]["memories"]["startup_memory"] = registration.nbtlib.Compound()
    drifted["startup_extra"] = registration.nbtlib.Int(1)
    calls = []

    async def start(server):
        calls.append("native_start")

    async def command(server, text):
        calls.append(text)
        if text == "tick freeze":
            return ["[Server thread/INFO]: The game is frozen"]
        if text.startswith("data merge"):
            assert original["UUID"].snbt() in text
            assert text.endswith(expected.snbt())
            def merge(target, source):
                for key, value in source.items():
                    if isinstance(value, registration.nbtlib.Compound) and key in target:
                        merge(target[key], value)
                    else:
                        target[key] = registration.nbtlib.parse_nbt(value.snbt())
            merge(drifted, expected)
            return ["Modified entity data"]
        if text.startswith("data modify"):
            field, value = text.split("] ", 1)[1].split(" set value ", 1)
            drifted[json.loads(field)] = registration.nbtlib.parse_nbt(value)
            return ["Modified entity data"]
        if text.startswith("data remove"):
            del drifted[json.loads(text.split("] ", 1)[1])]
            return ["Modified entity data"]
        console = drifted.snbt().replace("0.08500000089406967f", "0.085f")
        return ["[Server thread/INFO]: Camel has the following entity data: " + console]

    monkeypatch.setattr(MinecraftServer, "start", start)
    monkeypatch.setattr(MinecraftServer, "command", command)
    server = CourierInitializationServer(tmp_path, Path("server.jar"), "java", 512, 0, 120, 30,
                                         template=ASSETS / f"instance_{index}")
    asyncio.run(server.start())
    assert calls[:2] == ["native_start", "tick freeze"]
    assert any(' "Brain" set value ' in call for call in calls)
    assert calls[-2].startswith("data remove")
    result = json.loads((tmp_path / "courier-startup-restoration.json").read_text())
    assert result["restoration_verified"] and result["initialization_only"]
    after = registration.nbtlib.parse_nbt(result["native_after_snbt"])
    assert after["Pos"] == expected["Pos"] and after["Brain"] == expected["Brain"]
    assert "startup_extra" not in after
    assert result["full_native_nbt_verified"]
    with pytest.raises(RuntimeError, match="only once"):
        asyncio.run(server.start())
