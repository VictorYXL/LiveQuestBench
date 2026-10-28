"""Admission for frozen references and separately published paired additions."""

from pathlib import Path

import pytest

from benchmark.config import CAPABILITIES, load_experiment, load_task
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
        assert {Path(t.source.path).name for t in experiment.tasks} <= {
            path.name for path in (root / "tasks" / mode).glob("*.yaml")
        }


@pytest.mark.parametrize("game", ["minecraft", "veloren"])
def test_published_additions_have_matching_admitted_tracks(game, tmp_path):
    pytest.importorskip("nbtlib")
    root = Path(__file__).resolve().parents[2] / "config" / game
    reference = load_experiment(root / "experiments/structured_tools.yaml")
    reference_names = {Path(task.source.path).name for task in reference.tasks}
    additions = [
        {path.name for path in (root / "tasks" / mode).glob("*.yaml")} - reference_names
        for mode in ("structured_tools", "visual_motor")
    ]
    assert additions[0] == additions[1]
    for name in sorted(additions[0]):
        left, right = [
            load_task(root / "tasks" / mode / name)
            for mode in ("structured_tools", "visual_motor")
        ]
        assert (left.task_type, right.task_type) == ("structured_tool", "visual_motor")
        # Track-specific control manuals may differ; native goals and scoring may not.
        for field in ("id", "fixture", "participants", "evaluator",
                      "evaluator_parameters", "capabilities", "time_limit_seconds"):
            assert getattr(left, field) == getattr(right, field), (name, field)
        for task in (left, right):
            make_game(task, tmp_path / task.id / task.task_type,
                      headless=True, recording=False, recording_fps=5)
