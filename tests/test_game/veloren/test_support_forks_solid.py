import json
from pathlib import Path

from benchmark.config import load_task
from game.veloren.prototypes.covered_support_forks import build_candidate
from game.veloren.prototypes.covered_support_forks_solid import build_solid_candidate, write_solid_candidate


WORLD = Path("config/veloren/fixtures/veloren_0_18_0_0.bin")


def test_solid_version_only_changes_declared_observation_and_identity():
    for seed in (0, 1):
        previous, previous_private = build_candidate(WORLD, seed)
        task, private = build_solid_candidate(WORLD, seed)
        assert task["id"] != previous["id"]
        assert task["task"].startswith(previous["task"])
        assert task["fixture"].pop("scene_observation") == "native-solid-scene/1"
        assert {k: v for k, v in task.items() if k not in ("id", "task")} == {
            k: v for k, v in previous.items() if k not in ("id", "task")
        }
        assert private["geometry_sha256"] == previous_private["geometry_sha256"]
        assert private["side"] == previous_private["side"]
        assert private["source_proposal"] == previous_private["source_proposal"]
        assert not private["qualification"]
        assert "route_observation" not in task["fixture"]
        assert "route_evidence" not in task["fixture"]


def test_written_task_discloses_the_added_condition_and_keeps_mapping_private(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "game.veloren.prototypes.covered_support_forks_solid.secrets.randbits",
        lambda bits: 1234567890123456789,
    )
    task_path = write_solid_candidate(tmp_path / "candidate", WORLD)
    task = load_task(task_path)
    instructions = (task_path.parent / "public-instructions.txt").read_text()
    private = json.loads((task_path.parent / "private-instance.json").read_text())
    assert instructions == task.task
    assert "native-solid-scene/1" in instructions
    assert "chat, saved preferences and pipeline changes" in instructions
    assert task.fixture["scene_observation"] == "native-solid-scene/1"
    assert private["side"] in ("left", "right")
    assert str(private["seed"]) not in instructions
    assert not private["qualification"]
