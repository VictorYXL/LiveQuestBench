"""Explicit fixture admission, immutable world resets and native state contracts."""

from copy import deepcopy
import asyncio
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from benchmark.config import ConfigError, load_experiment, load_task
from benchmark.factory import validate_experiment
from game.veloren.fixture import validate_fixture, verify_player


ROOT = Path(__file__).resolve().parents[1]


def test_missing_and_implicit_fixtures_are_rejected(tmp_path):
    task_path = ROOT / "config/minecraft/tasks/st/collect_3_logs.yaml"
    original = yaml.safe_load(task_path.read_text())
    for invalid in (None, "movement", {}):
        data = deepcopy(original)
        data["fixture"] = invalid
        path = tmp_path / "task.yaml"
        path.write_text(yaml.safe_dump(data))
        if invalid == {}:
            config = load_experiment(ROOT / "config/minecraft/experiments/collect_3_logs.yaml")
            with pytest.raises(ValueError, match="Minecraft fixture"):
                validate_experiment(replace(config, tasks=(load_task(path),)))
        else:
            with pytest.raises(ConfigError, match="fixture"):
                load_task(path)
    config = load_experiment(ROOT / "config/minecraft/experiments/collect_3_logs.yaml")
    task = replace(config.tasks[0], fixture={**config.tasks[0].fixture, "world_path": str(tmp_path / "missing")})
    with pytest.raises(FileNotFoundError):
        validate_experiment(replace(config, tasks=(task,)))


def test_world_paths_and_native_resets(tmp_path):
    pytest.importorskip("nbtlib")
    from game.minecraft.evaluators.world import read_blocks
    from game.minecraft.init_player_state import PlayerState
    from game.minecraft.runtime.session import copy_world

    source_file = ROOT / "config/minecraft/tasks/st/collect_3_logs.yaml"
    relative = load_task(source_file)
    source = Path(relative.fixture["world_path"])
    raw = yaml.safe_load(source_file.read_text())
    raw["fixture"]["world_path"] = str(source)
    absolute_file = tmp_path / "absolute.yaml"
    absolute_file.write_text(yaml.safe_dump(raw))
    assert load_task(absolute_file).fixture == relative.fixture
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob("*") if p.is_file()}
    state = PlayerState.from_dict(relative.fixture["player_state"])
    for name in ("first", "second"):
        destination = tmp_path / name
        copy_world(source, destination, state, UUID(int=1))
        assert set(read_blocks(destination, (0, 72, -2), (0, 74, -2), state.dimension).values()) == {"minecraft:oak_log"}
        if name == "first":
            (destination / "region/r.0.-1.mca").write_bytes(b"deliberately damaged disposable working copy")
    assert hashes == {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in source.rglob("*") if p.is_file()}
    assert not (source / "playerdata").exists()


def test_veloren_explicit_fields_and_native_state_validation():
    fixture = load_task(ROOT / "config/veloren/tasks/st/move_2_metres.yaml").fixture
    assert validate_fixture(fixture) == fixture
    for key in ("map_asset", "world_seed", "platform", "player_state", "time_of_day", "calendar"):
        missing = deepcopy(fixture)
        del missing[key]
        with pytest.raises(ValueError):
            validate_fixture(missing)
    shifted = deepcopy(fixture)
    shifted["platform"]["origin"][0] += 20
    with pytest.raises(ValueError, match="declared platform"):
        validate_fixture(shifted)
    with pytest.raises(ValueError, match="exactly"):
        validate_fixture("movement")
    player = fixture["player_state"]
    observation = {
        "position": player["position"], "look": player["look"], "on_ground": True, "velocity": [0, 0, 0],
        "survival": {"health": {"current": player["health"]}, "buffs": []},
        "inventory": {
            "items": [{"item": {"id": {"Simple": name}, "amount": count}} for name, count in player["inventory"].items()],
            "equipment": {slot: {"id": {"Simple": name}} for slot, name in player["equipment"].items()},
        },
    }
    verify_player(fixture, observation)
    observation["inventory"]["items"] = []
    with pytest.raises(RuntimeError, match="inventory or equipment"):
        verify_player(fixture, observation)


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_VELOREN_TEST") != "1", reason="Opt-in native fixture initialization")
def test_veloren_changed_configuration_is_applied(headless, recording):
    from game.veloren.game import VelorenGame

    fixture = load_task(ROOT / "config/veloren/tasks/st/move_2_metres.yaml").fixture
    fixture["platform"]["origin"][0] += 16
    fixture["player_state"]["position"][0] += 16
    fixture["player_state"]["health"] = 95
    fixture["player_state"]["inventory"] = {"common.items.food.cheese": 2}
    output = ROOT / "output/test" / f"veloren-fixture-parameters-{uuid4().hex}"
    game = VelorenGame(output_dir=output, fixture=fixture, track="structured_tool",
                       headless=headless, recording=recording)

    async def scenario():
        try:
            await game.start()
            before = await game.save_snapshot(output / "before")
            observation = json.loads((before / "observation.json").read_text())
            verify_player(fixture, observation)
            receipt = json.loads((output / "fixture.json").read_text())
            assert receipt["construction"]["origin"] == fixture["platform"]["origin"]
            assert receipt["world"]["configuration"] == fixture
            assert receipt["world"]["map_sha256"]
        finally:
            await game.close()

    asyncio.run(scenario())
