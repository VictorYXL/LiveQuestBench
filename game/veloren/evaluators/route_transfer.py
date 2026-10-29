"""Passive native physics-route history, separate from inferred learning benefit."""

from pathlib import Path

from game.route_transfer import build_layout, route_checks, validate_samples
from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state
from game.veloren.evaluators.deaths import death_metrics


def validate_route(*, variant: int, origin: list[int], min_health: float = 1) -> None:
    build_layout(variant, tuple(origin), headroom=3)
    validate_state(min_health=min_health)


def route_transfer_checks(initial: dict, final: dict, *, variant: int, origin: list[int],
                          min_health: float = 1) -> dict:
    validate_state(min_health=min_health)
    layout = build_layout(variant, tuple(origin), headroom=3)
    first, last = (row["private_route_evidence"] for row in (initial, final))
    for boundary, evidence in ((initial, first), (final, last)):
        if (evidence["schema"] != "native-client-motion/1"
                or evidence["route_schema"] != "native-client-route/2"
                or evidence["session_id"] != boundary["session_id"]
                or evidence["uid"] != boundary["self_identity"]["uid"]):
            raise ValueError("Native route identity or schema mismatch")
        if (type(evidence["samples"]) is not int or evidence["samples"] < 1
                or type(evidence["through_tick"]) is not int or evidence["through_tick"] < 0):
            raise ValueError("Invalid native route counters")
        validate_samples(evidence["route_samples"])
        if not evidence["route_samples"]:
            raise ValueError("Native route evidence has no opening position")
        if any(row["sequence"] > evidence["samples"] for row in evidence["route_samples"]):
            raise ValueError("Native route sample exceeds capture boundary")
    if (first["uid"] != last["uid"] or first["session_id"] != last["session_id"]
            or first["samples"] > last["samples"] or first["through_tick"] > last["through_tick"]):
        raise ValueError("Native route identity or counters changed")
    history = first["route_samples"]
    if last["route_samples"][:len(history)] != history:
        raise ValueError("Native route history changed")
    if any(row["sequence"] <= first["samples"] for row in last["route_samples"][len(history):]):
        raise ValueError("Native route sample predates measured play")
    samples = last["route_samples"][max(0, len(history) - 1):]
    deaths = death_metrics(initial, final)["deaths"]["count"]
    route = route_checks(samples, layout["wings"], layout["application_distance_limit"], deaths=deaths)
    x, y, z = layout["wings"][-1]["exit"]
    result = state_checks(initial, final, min_health=min_health, position={
        "target": [x + 1, y + 1, z], "horizontal_tolerance": 2,
        "vertical_tolerance": 0.5, "max_speed": 0.1,
    })
    result["checks"].append({"kind": "route_transfer", "passed": route["success"], **route})
    result["success"] = result["success"] and route["success"]
    result["learning_benefit"] = route["learning_benefit"]
    return result


def evaluate_route(before: Path, after: Path, *, variant: int, origin: list[int],
                   min_health: float = 1) -> dict:
    return route_transfer_checks(*load_pair(before, after), variant=variant, origin=origin,
                                 min_health=min_health)
