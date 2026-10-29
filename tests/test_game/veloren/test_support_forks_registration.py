from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from benchmark.config import ParticipantConfig, load_task
from benchmark.factory import make_game
from game.veloren.fixture import solid_voxels
from game.veloren.prototypes.covered_support_forks_solid import build_solid_candidate
from game.veloren.support_forks import prepare_episode_fixture


TASK = Path("config/veloren/tasks/visual_motor/covered_support_forks_local_solid_v2.yaml")


def test_default_factory_materializes_both_reviewed_mappings_without_io(tmp_path, monkeypatch):
    task = load_task(TASK)
    original = deepcopy(task.fixture)
    draws = iter((0, 0, 1))
    monkeypatch.setattr("game.veloren.support_forks.secrets.randbits", lambda bits: next(draws))
    fixtures = []
    for index, seed in enumerate((0, 0, 1)):
        output = tmp_path / str(index)
        binding = make_game(task, output, headless=True, recording=False, recording_fps=5)
        expected, _ = build_solid_candidate(Path(task.fixture["world_path"]), seed)
        assert binding.game.fixture == expected["fixture"]
        assert binding.game.phase == "new"
        assert not output.exists()
        assert len(solid_voxels(binding.game.fixture)) == 6974
        assert binding.game.fixture.get("route_observation") is None
        assert not binding.game.fixture.get("route_evidence", False)
        fixtures.append(binding.game.fixture)
    assert fixtures[0] == fixtures[1]
    assert fixtures[0] is not fixtures[1]
    assert fixtures[0]["blocks"] is not fixtures[1]["blocks"]
    assert fixtures[1]["blocks"] != fixtures[2]["blocks"]
    assert task.fixture == original


@pytest.mark.parametrize("change", ["goal", "resources", "scene", "route", "instructions", "track", "team"])
def test_registration_rejects_contract_drift_before_drawing_private_mapping(monkeypatch, change):
    task = load_task(TASK)
    fixture, parameters = deepcopy(task.fixture), deepcopy(task.evaluator_parameters)
    if change == "goal":
        parameters["position"]["horizontal_tolerance"] = 20
        task = replace(task, evaluator_parameters=parameters)
    elif change == "resources":
        fixture["player_state"]["health"] = 200
        task = replace(task, fixture=fixture)
    elif change == "scene":
        fixture.pop("scene_observation")
        task = replace(task, fixture=fixture)
    elif change == "route":
        fixture["route_observation"] = "native-route-local-view/1"
        task = replace(task, fixture=fixture)
    elif change == "instructions":
        task = replace(task, task=task.task + "\nYou must visit the sample.")
    elif change == "track":
        task = replace(task, task_type="structured_tool")
    else:
        task = replace(task, participants=(ParticipantConfig("extra", fixture["player_state"]),))
    monkeypatch.setattr(
        "game.veloren.support_forks.secrets.randbits",
        lambda bits: pytest.fail("An invalid contract must fail before choosing a mapping"),
    )
    with pytest.raises(ValueError, match="must match review"):
        make_game(task, Path("unused-preflight"), headless=True, recording=False, recording_fps=5)


def test_generated_instance_is_checked_before_binding(monkeypatch):
    task = load_task(TASK)
    monkeypatch.setattr("game.veloren.support_forks.secrets.randbits", lambda bits: 42)

    def corrupted_output(world, seed):
        candidate, private = build_solid_candidate(world, seed)
        if seed == 42:
            candidate["evaluator"]["parameters"]["position"]["max_speed"] = 20
        return candidate, private

    monkeypatch.setattr("game.veloren.support_forks.build_solid_candidate", corrupted_output)
    with pytest.raises(ValueError, match="two reviewed mappings"):
        prepare_episode_fixture(task)


def test_unrelated_default_factory_does_not_use_l05_generation(tmp_path, monkeypatch):
    task = load_task(Path("config/veloren/tasks/visual_motor/mountain_workshop_circuit.yaml"))
    monkeypatch.setattr(
        "game.veloren.support_forks.secrets.randbits",
        lambda bits: pytest.fail("Unrelated tasks must retain their original fixture"),
    )
    binding = make_game(task, tmp_path / "ordinary", headless=True, recording=False, recording_fps=5)
    assert binding.game.fixture == task.fixture
    assert not (tmp_path / "ordinary").exists()
