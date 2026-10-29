import pytest

from game.minecraft.fixtures.archery_evidence import evaluate_events


PLAYER = [1, 2, 3, 4]


def event(kind, tick, shots, **fields):
    return {"kind": kind, "tick": tick, "shots": shots, "player": PLAYER, **fields}


def test_owned_targets_and_actual_launch_counter():
    events = [event("shot", 1, 1), event("target_hit", 2, 1, target="application_1"),
              event("shot", 3, 2), event("target_hit", 4, 2, target="application_2")]
    assert evaluate_events(events, PLAYER, start_tick=0, end_tick=5)["application_diagnostic_success"]
    events[-1]["player"] = [5, 6, 7, 8]
    assert not evaluate_events(events, PLAYER, start_tick=0, end_tick=5)["application_diagnostic_success"]


def test_excess_launches_are_not_hidden_by_arrow_pickup():
    events = [event("shot", 1, 13), event("target_hit", 2, 13, target="application_1"),
              event("target_hit", 3, 13, target="application_2")]
    score = evaluate_events(events, PLAYER, start_tick=0, end_tick=5)
    assert score["native_launches"] == 13
    assert not score["application_diagnostic_success"]


@pytest.mark.parametrize("events", [
    [event("shot", 4, 1), event("shot", 3, 2)],
    [event("shot", 1, 2), event("shot", 2, 1)],
    [event("target_hit", 1, 1, target="unknown")],
])
def test_rejects_bad_native_sequence(events):
    with pytest.raises(ValueError):
        evaluate_events(events, PLAYER, start_tick=0, end_tick=5)
