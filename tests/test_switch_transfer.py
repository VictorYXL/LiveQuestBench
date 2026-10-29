from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from game.minecraft.evaluators.switch_transfer import evaluate_switch


def score(*, toggles=2, feedback=True, mode=2, ready=True):
    player = UUID(int=1)
    data = {
        "application_toggles": toggles, "practice_toggles": 2, "phase": 2,
        "practice_feedback": feedback,
        "ready_1": ready, "ready_2": True,
        "events": [{"application": i, "tick": 100 + i, "player": [0, 0, 0, 1]} for i in (1, 2)],
    }
    with (
        patch("game.minecraft.evaluators.switch_transfer.verify_initial_switch"),
        patch("game.minecraft.evaluators.switch_transfer.registry", return_value={}),
        patch("game.minecraft.evaluators.switch_transfer.evidence", return_value=data),
        patch("game.minecraft.evaluators.switch_transfer.nbtlib.load",
              side_effect=[{"Data": {"Time": 100}}, {"Data": {"Time": 200}}, {"playerGameType": mode}]),
        patch("game.minecraft.evaluators.switch_transfer.evaluate_state",
              return_value={"checks": [{"kind": "position", "passed": True}]}),
    ):
        return evaluate_switch(Path("before"), Path("after"), player, position={})


def test_native_application_success_is_not_learning_benefit():
    result = score()
    assert result["success"]
    assert result["learning_benefit"]["status"] == "not_estimated"


def test_output_completion_does_not_waive_toggle_budget():
    assert not score(toggles=5)["success"]


def test_toggling_without_native_practice_feedback_does_not_count():
    assert not score(feedback=False)["success"]


def test_adventure_protection_must_remain_enabled():
    assert not score(mode=0)["success"]


def test_transient_ordered_success_does_not_allow_wrong_final_outputs():
    assert not score(ready=False)["success"]
