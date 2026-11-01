"""Canonical task matrix and game-factory admission."""

from collections import Counter
from pathlib import Path
import re

import pytest

from benchmark.config import CAPABILITIES, load_experiment, load_task
from benchmark.factory import make_game


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("game", ["minecraft", "veloren"])
def test_complete_paired_catalog_and_real_factory_admission(game, tmp_path):
    tracks = {}
    for folder, track in (("structured_tools", "structured_tool"), ("visual_motor", "visual_motor")):
        paths = sorted((ROOT / "config" / game / "tasks" / folder).glob("*.yaml"))
        tasks = [load_task(path) for path in paths]
        assert len(tasks) == 30
        assert len({task.id for task in tasks}) == 30
        counts = Counter()
        for task in tasks:
            assert task.game == game and task.task_type == track
            assert task.capabilities is not None and len(task.capabilities.primary) == 1
            counts.update(task.capabilities.primary)
            assert not re.search(r"_v\d+|_prototype|_c\d+$", task.id)
            assert Path(task.source.path).stem == task.id
            assert not re.search(
                r"DEVELOPMENTAL|Version\d+|not an admitted benchmark task|This v\d+ condition",
                task.task,
            )
            binding = make_game(
                task, tmp_path / folder / task.id,
                headless=True, recording=False, recording_fps=10,
            )
            assert binding.game.phase == "new"
        assert counts == Counter({capability: 5 for capability in CAPABILITIES})
        full = load_experiment(ROOT / "config" / game / "experiments" / f"full_{folder}.yaml")
        assert {task.source.path for task in full.tasks} == {task.source.path for task in tasks}
        assert len(full.tasks) == 30 and full.repetitions == 1
        tracks[track] = {task.id: task for task in tasks}
    assert tracks["structured_tool"].keys() == tracks["visual_motor"].keys()
    visual_profiles = {"camera_observation", "route_observation", "scene_observation"}
    for task_id, first in tracks["structured_tool"].items():
        second = tracks["visual_motor"][task_id]
        assert first.capabilities == second.capabilities
        assert first.time_limit_seconds == second.time_limit_seconds
        assert (first.evaluator, first.evaluator_parameters) == (
            second.evaluator, second.evaluator_parameters,
        )
        assert {key: value for key, value in first.fixture.items() if key not in visual_profiles} == {
            key: value for key, value in second.fixture.items() if key not in visual_profiles
        }
