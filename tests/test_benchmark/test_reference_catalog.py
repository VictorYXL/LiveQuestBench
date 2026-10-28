"""Admission and paired-world regressions for the twelve reference objectives."""

from pathlib import Path

import pytest

from benchmark.config import CAPABILITIES, load_experiment
from benchmark.factory import make_game


@pytest.mark.parametrize("game", ["minecraft", "veloren"])
def test_reference_tracks_share_goals_worlds_and_scoring(game, tmp_path):
    pytest.importorskip("nbtlib")
    root = Path(__file__).resolve().parents[2] / "config" / game
    st, vm = [load_experiment(root / "experiments" / f"{mode}.yaml")
              for mode in ("structured_tools", "visual_motor")]
    assert len(st.tasks) == len(vm.tasks) == 6
    assert {t.capabilities.primary[0] for t in st.tasks} == set(CAPABILITIES)
    for left, right in zip(st.tasks, vm.tasks, strict=True):
        assert left.id == right.id
        assert left.task == right.task
        assert left.fixture == right.fixture
        assert left.participants == right.participants
        assert left.evaluator == right.evaluator
        assert left.evaluator_parameters == right.evaluator_parameters
        assert left.capabilities == right.capabilities
        assert left.time_limit_seconds == right.time_limit_seconds
        for task in (left, right):
            make_game(task, tmp_path / task.id / task.task_type,
                      headless=True, recording=False, recording_fps=5)
    for mode, experiment in (("structured_tools", st), ("visual_motor", vm)):
        assert {Path(t.source.path).name for t in experiment.tasks} == {
            path.name for path in (root / "tasks" / mode).glob("*.yaml")
        }
