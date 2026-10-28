from copy import deepcopy

import pytest

from game.veloren.evaluators.itinerary import itinerary_checks


def score(points):
    initial = {
        "session_id": "same", "self_identity": {"uid": 7},
        "survival": {"health": {"current": 100}},
        "position": [0, 0, 201], "velocity": [0, 0, 0], "on_ground": True,
        "private_route_evidence": {
            "schema": "native-client-motion/1", "route_schema": "native-client-route/1",
            "session_id": "same", "uid": 7, "samples": 10, "through_tick": 20,
            "route_samples": [{"sequence": 1, "position": [0, 0, 201]}],
        },
    }
    final = deepcopy(initial)
    evidence = final["private_route_evidence"]
    evidence.update(samples=30, through_tick=40)
    evidence["route_samples"].extend(
        {"sequence": 11 + index, "position": point} for index, point in enumerate(points))
    return initial, final


VISIT = {"target": [10, 10, 201], "horizontal_tolerance": 2, "vertical_tolerance": .5}
RETURN = {"target": [0, 0, 201], "horizontal_tolerance": 2,
          "vertical_tolerance": .5, "max_speed": .1}


@pytest.mark.parametrize(("points", "expected"), [
    ([], False),
    ([[10, 10, 206], [0, 0, 201]], False),
    ([[10, 10, 201], [0, 0, 201]], True),
])
def test_visit_requires_new_correct_floor_sample(points, expected):
    assert itinerary_checks(*score(points), visits=[VISIT], position=RETURN)["success"] is expected


def test_visit_rejects_rewritten_native_history():
    initial, final = score([[10, 10, 201]])
    final["private_route_evidence"]["route_samples"][0]["position"][0] = 1
    with pytest.raises(ValueError, match="history changed"):
        itinerary_checks(initial, final, visits=[VISIT], position=RETURN)
