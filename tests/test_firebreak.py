from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from game.minecraft.evaluators.firebreak import evaluate_firebreak
from benchmark.config import load_task
from benchmark.factory import make_game


def score(lost, quiet=400):
    registry = {"protected": [{"position": [x, 75, 0]} for x in range(5)]}
    evidence = {"destroyed": [{"cell": [x, 75, 0], "tick": 150} for x in lost],
                "quiet_ticks": quiet, "burning_cells": 0}
    with (
        patch("game.minecraft.evaluators.firebreak.verify_initial_firebreak"),
        patch("game.minecraft.evaluators.firebreak.manifest", return_value=registry),
        patch("game.minecraft.evaluators.firebreak.evidence", return_value=evidence),
        patch("game.minecraft.evaluators.firebreak.nbtlib.load",
              side_effect=[{"Data": {"Time": 100}}, {"Data": {"Time": 600}}]),
        patch("game.minecraft.evaluators.firebreak.evaluate_state",
              return_value={"checks": [{"kind": "position", "passed": True}]}),
    ):
        return evaluate_firebreak(Path("before"), Path("after"), UUID(int=1), position={})


def test_destroyed_originals_are_not_credited_as_rebuilds():
    assert score([0])["success"]
    assert not score([0, 1])["success"]


def test_fire_free_dwell_is_mandatory():
    assert not score([], quiet=399)["success"]


@pytest.mark.parametrize("lost", [[0, 0], [7]])
def test_bad_original_cell_evidence_is_invalid(lost):
    with pytest.raises(ValueError, match="Invalid irreversible"):
        score(lost)


def test_firebreak_rejects_unsupported_state_parameters_at_admission(tmp_path):
    task = load_task(Path(__file__).resolve().parents[1] /
                     "config/minecraft/tasks/structured_tools/village_firebreak.yaml")
    task = replace(task, evaluator_parameters={**task.evaluator_parameters, "min_health": 5})
    with pytest.raises(TypeError, match="min_health"):
        make_game(task, tmp_path, headless=True, recording=False, recording_fps=5)
