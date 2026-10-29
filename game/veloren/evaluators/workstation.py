"""Native workshop directions, interior entry, new holdings and guide reunion."""

import math
from pathlib import Path

from game.veloren.evaluators.endpoints import finite, load_pair, player_motion
from game.veloren.evaluators.workstation_route import itinerary_checks, validate_itinerary


def validate_workstation(*, workshop_marker: list[int], guide_distance: float, **state) -> None:
    if (not isinstance(workshop_marker, list) or len(workshop_marker) != 2
            or any(type(value) is not int for value in workshop_marker)):
        raise ValueError("Workshop marker requires native integer XY")
    if finite(guide_distance, "guide_distance") <= 0:
        raise ValueError("Guide distance must be positive")
    validate_itinerary(**state)


def workstation_checks(initial: dict, final: dict, *, workshop_marker: list[int],
                       guide_distance: float, **state) -> dict:
    validate_workstation(workshop_marker=workshop_marker, guide_distance=guide_distance, **state)
    result = itinerary_checks(initial, final, **state)
    if initial["dialogue_markers"]:
        raise ValueError("Workshop task must open without received directions")
    if (type(initial["tick"]) is not int or type(final["tick"]) is not int
            or final["tick"] < initial["tick"]):
        raise ValueError("Invalid native directions clock")
    matches = []
    for receipt in final["dialogue_markers"]:
        tick = receipt["received_client_tick"]
        if (receipt["schema_version"] != "1.0" or receipt["source"] != "validated_server_dialogue"
                or receipt["kind"] != "Marker" or type(tick) is not int
                or not 0 <= tick <= final["tick"]):
            raise ValueError("Invalid received native directions")
        marker = receipt["marker"]
        if (tick >= initial["tick"]
                and marker["label"].get("Localized", {}).get("key") == "hud-map-workshop"
                and [marker["wpos"]["x"], marker["wpos"]["y"]] == workshop_marker):
            matches.append(receipt)
    if any(left["received_client_tick"] > right["received_client_tick"]
           for left, right in zip(matches, matches[1:])):
        raise ValueError("Native workshop directions are not in receipt order")
    point, speed, grounded = player_motion(final)
    distances = []
    for receipt in matches[:1]:
        guide = next((row for row in final["nearby_entities"]
                      if row["uid"] == receipt["sender_uid"]
                      and row["control_target"] == receipt["sender"]), None)
        if guide is not None and guide.get("health") and not guide["health"]["dead"]:
            distances.append(math.dist(point, guide["position"]))
    result["checks"].extend([
        {"kind": "native_workshop_directions", "received": len(matches), "passed": bool(matches)},
        {"kind": "original_guide_reunion", "distances": distances, "passed": grounded and speed <= .1
         and any(distance <= guide_distance for distance in distances)},
    ])
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " Directions are immutable native server-validated receipts for the declared workshop. "
        "Reunion uses the first qualifying receipt sender's UID and client lifecycle. "
        "Later directions cannot substitute a nearer resident."
    )
    return result


def evaluate_workstation(before: Path, after: Path, **parameters) -> dict:
    return workstation_checks(*load_pair(before, after), **parameters)
