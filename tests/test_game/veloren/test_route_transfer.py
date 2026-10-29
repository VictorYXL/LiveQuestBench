"""Route history must remain actor-bound and inside measured native boundaries."""

from copy import deepcopy

import pytest

from game.veloren.evaluators.route_transfer import route_transfer_checks


def boundaries():
    initial = {
        "session_id": "same", "self_identity": {"uid": 7},
        "survival": {"health": {"current": 100}},
        "position": [0, 0, 201], "velocity": [0, 0, 0], "on_ground": True,
        "private_route_evidence": {
            "schema": "native-client-motion/1", "route_schema": "native-client-route/2",
            "session_id": "same", "uid": 7, "samples": 10, "through_tick": 20,
            "route_samples": [{"sequence": 1, "position": [0, 0, 201]}],
        },
    }
    return initial, deepcopy(initial)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("uid", 8, "identity"),
    ("session_id", "other", "identity"),
    ("route_schema", "native-client-route/1", "schema"),
    ("samples", True, "counters"),
    ("route_samples", [], "opening position"),
    ("route_samples", [{"sequence": 11, "position": [0, 0, 201]}], "capture boundary"),
    ("route_samples", [{"sequence": 1, "position": [0, 0, 201]},
                       {"sequence": 1, "position": [0, 0, 201]}], "sequence"),
    ("route_samples", [{"sequence": 1, "position": [0, 0, 201]},
                       {"sequence": 9, "position": [1, 0, 201]}], "predates"),
])
def test_native_route_rejects_invalid_identity_and_timeline(field, value, message):
    initial, final = boundaries()
    final["private_route_evidence"][field] = value
    with pytest.raises(ValueError, match=message):
        route_transfer_checks(initial, final, variant=0, origin=[0, 0, 201])


def test_native_route_rejects_changed_opening_history():
    initial, final = boundaries()
    final["private_route_evidence"]["route_samples"][0]["position"][0] = 1
    with pytest.raises(ValueError, match="history changed"):
        route_transfer_checks(initial, final, variant=0, origin=[0, 0, 201])


def test_route_authoring_capacity_is_opt_in_and_still_bounded():
    from game.veloren.fixture import solid_voxels

    fixture = {
        "platform": {"origin": [0, 0, 0], "size": [2, 2]},
        "blocks": [{"origin": [10, 0, 0], "size": [90, 50, 1]},
                   {"origin": [10, 0, 1], "size": [90, 50, 1]}],
    }
    with pytest.raises(ValueError, match="8192"):
        solid_voxels(fixture)
    fixture["route_evidence"] = True
    assert len(solid_voxels(fixture)) == 9004
    fixture["blocks"].append({"origin": [10, 0, 2], "size": [90, 50, 1]})
    with pytest.raises(ValueError, match="10240"):
        solid_voxels(fixture)


def test_private_route_history_is_not_in_agent_observations():
    from game.veloren.structured_tools.interface import FIELDS, project

    initial, _ = boundaries()
    observation = {field: None for field in FIELDS}
    observation.update(initial)
    assert "private_route_evidence" not in project(observation)
