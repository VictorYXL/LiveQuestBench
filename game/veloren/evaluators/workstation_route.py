"""Identity-bound native route visits followed by ordinary endpoint requirements."""

import math
from pathlib import Path

from game.route_transfer import validate_samples
from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state


def validate_itinerary(*, visits: list[dict], **state) -> None:
    if not isinstance(visits, list) or not 1 <= len(visits) <= 8:
        raise ValueError("Itinerary requires one to eight native regions")
    for visit in visits:
        if not isinstance(visit, dict) or set(visit) != {
            "target", "horizontal_tolerance", "vertical_tolerance",
        }:
            raise ValueError("Visit requires a three-dimensional region")
        validate_state(position={**visit, "max_speed": 0})
    validate_state(**state)


def route_samples(initial: dict, final: dict) -> list[dict]:
    first, last = (row["private_route_evidence"] for row in (initial, final))
    for boundary, evidence in ((initial, first), (final, last)):
        if (evidence["schema"] != "native-client-motion/1"
                or evidence["route_schema"] != "native-client-route/1"
                or evidence["session_id"] != boundary["session_id"]
                or evidence["uid"] != boundary["self_identity"]["uid"]):
            raise ValueError("Native route identity or schema mismatch")
        if (type(evidence["samples"]) is not int or evidence["samples"] < 1
                or type(evidence["through_tick"]) is not int or evidence["through_tick"] < 0):
            raise ValueError("Invalid native route counters")
        validate_samples(evidence["route_samples"])
        if not evidence["route_samples"]:
            raise ValueError("Missing native opening position")
        if any(row["sequence"] > evidence["samples"] for row in evidence["route_samples"]):
            raise ValueError("Route exceeds captured boundary")
    if (first["uid"] != last["uid"] or first["session_id"] != last["session_id"]
            or first["samples"] > last["samples"] or first["through_tick"] > last["through_tick"]):
        raise ValueError("Native route identity or counters changed")
    history = first["route_samples"]
    if last["route_samples"][:len(history)] != history:
        raise ValueError("Native route history changed")
    added = last["route_samples"][len(history):]
    if any(row["sequence"] <= first["samples"] for row in added):
        raise ValueError("Route sample predates measured play")
    return added


def itinerary_checks(initial: dict, final: dict, *, visits: list[dict], **state) -> dict:
    validate_itinerary(visits=visits, **state)
    samples = route_samples(initial, final)
    result = state_checks(initial, final, **state)
    cursor = 0
    for index, visit in enumerate(visits):
        matched = None
        for offset in range(cursor, len(samples)):
            sample = samples[offset]
            point = sample["position"]
            if (math.dist(point[:2], visit["target"][:2]) <= visit["horizontal_tolerance"]
                    and abs(point[2] - visit["target"][2]) <= visit["vertical_tolerance"]):
                matched, cursor = sample["sequence"], offset + 1
                break
        result["checks"].append({"kind": "native_region_visit", "index": index,
                                 "sequence": matched, "passed": matched is not None})
        if matched is None:
            cursor = len(samples)
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " Ordered three-dimensional native route visits after readiness. "
        "Item counts do not attribute pickups to a particular source UID."
    )
    return result


def evaluate_itinerary(before: Path, after: Path, *, visits: list[dict], **state) -> dict:
    return itinerary_checks(*load_pair(before, after), visits=visits, **state)
