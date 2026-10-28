"""Ordered native glide landings with proficiency separate from learning benefit."""

import math
from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state


def validate_glide_route(*, landings: list[dict], position: dict) -> None:
    if not isinstance(landings, list) or not 2 <= len(landings) <= 16:
        raise ValueError("A glide route requires between two and sixteen landing goals")
    validate_state(position=position)
    for landing in landings:
        validate_state(glide_landing=landing)


def glide_route_checks(initial: dict, final: dict, *, landings: list[dict], position: dict) -> dict:
    validate_glide_route(landings=landings, position=position)
    result = state_checks(initial, final, position=position, glide_landing=landings[0])
    events = next(row["landings"] for row in result["checks"] if row["kind"] == "glide_landing")
    result["checks"] = [row for row in result["checks"] if row["kind"] != "glide_landing"]
    matched = []
    for index, event in enumerate(events):
        if len(matched) == len(landings):
            break
        goal = landings[len(matched)]
        if (event["glide_distance"] >= goal["min_distance"]
                and math.dist(event["position"][:2], goal["target"][:2]) <= goal["horizontal_tolerance"]
                and abs(event["position"][2] - goal["target"][2]) <= goal["vertical_tolerance"]):
            matched.append(index)
    result["checks"].append({
        "kind": "ordered_glide_landings", "required": len(landings),
        "completed": len(matched), "matched_event_indices": matched,
        "passed": len(matched) == len(landings),
    })
    result["success"] = all(row["passed"] for row in result["checks"])
    result["landing_events"] = events
    result["learning_benefit"] = {
        "status": "not_estimated",
        "reason": "Ordered flight proficiency is not evidence of improvement without matched controls.",
    }
    result["semantics"] += (
        " Each ordered goal requires a distinct new native airborne-glide landing. "
        "Failed landings and retries remain in the history; no reset, walking-arrival substitute, "
        "mandatory control sequence or causal learning claim."
    )
    return result


def evaluate_glide_route(before: Path, after: Path, *, landings: list[dict], position: dict) -> dict:
    return glide_route_checks(*load_pair(before, after), landings=landings, position=position)
