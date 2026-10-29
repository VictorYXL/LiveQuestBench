from copy import deepcopy

import pytest

from game.veloren.evaluators.workstation import workstation_checks


def boundaries():
    first = {
        "session_id": "same", "self_identity": {"uid": 7}, "tick": 20,
        "survival": {"health": {"current": 100}},
        "position": [0, 0, 144], "velocity": [0, 0, 0], "on_ground": True,
        "dialogue_markers": [], "nearby_entities": [],
        "private_route_evidence": {
            "schema": "native-client-motion/1", "route_schema": "native-client-route/1",
            "session_id": "same", "uid": 7, "samples": 10, "through_tick": 20,
            "route_samples": [{"sequence": 1, "position": [0, 0, 144]}],
        },
    }
    last = deepcopy(first)
    last["tick"] = 40
    last["private_route_evidence"].update(samples=30, through_tick=40)
    last["private_route_evidence"]["route_samples"].append(
        {"sequence": 11, "position": [10, 10, 144]})
    sender = {"uid": 8, "lifecycle": "native-guide"}
    last["dialogue_markers"] = [{
        "schema_version": "1.0", "source": "validated_server_dialogue", "kind": "Marker",
        "received_client_tick": 25, "sender_uid": 8, "sender": sender,
        "marker": {"label": {"Localized": {"key": "hud-map-workshop"}},
                   "wpos": {"x": 10, "y": 10}},
    }]
    last["nearby_entities"] = [{
        "uid": 8, "control_target": sender, "health": {"dead": False}, "position": [1, 0, 144],
    }]
    return first, last


PARAMETERS = {"workshop_marker": [10, 10], "guide_distance": 3,
              "visits": [{"target": [10, 10, 144], "horizontal_tolerance": 2,
                          "vertical_tolerance": .5}]}


def test_native_directions_interior_and_original_guide():
    assert workstation_checks(*boundaries(), **PARAMETERS)["success"]


@pytest.mark.parametrize("missing", ["directions", "guide", "floor"])
def test_workstation_rejects_missing_native_stage(missing):
    first, last = boundaries()
    if missing == "directions":
        last["dialogue_markers"] = []
    elif missing == "guide":
        last["nearby_entities"][0]["control_target"] = {"uid": 8, "lifecycle": "replacement"}
    else:
        last["private_route_evidence"]["route_samples"][-1]["position"][2] += 5
    assert not workstation_checks(first, last, **PARAMETERS)["success"]


@pytest.mark.parametrize("original_dead", [False, True])
def test_later_nearer_directions_sender_cannot_replace_original_guide(original_dead):
    first, last = boundaries()
    last["nearby_entities"][0].update(position=[10, 0, 144], health={"dead": original_dead})
    later = deepcopy(last["dialogue_markers"][0])
    later.update(received_client_tick=30, sender_uid=9,
                 sender={"uid": 9, "lifecycle": "later-guide"})
    last["dialogue_markers"].append(later)
    last["nearby_entities"].append({
        "uid": 9, "control_target": later["sender"], "health": {"dead": False},
        "position": [1, 0, 144],
    })
    result = workstation_checks(first, last, **PARAMETERS)
    assert not result["success"]
    reunion = next(row for row in result["checks"] if row["kind"] == "original_guide_reunion")
    assert reunion["distances"] == ([] if original_dead else [10])


def test_repeated_directions_from_original_guide_preserve_reunion():
    first, last = boundaries()
    later = deepcopy(last["dialogue_markers"][0])
    later["received_client_tick"] = 30
    last["dialogue_markers"].append(later)
    assert workstation_checks(first, last, **PARAMETERS)["success"]
    last["dialogue_markers"].reverse()
    with pytest.raises(ValueError, match="receipt order"):
        workstation_checks(first, last, **PARAMETERS)
