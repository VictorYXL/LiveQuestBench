"""Endpoint inventory scoring adapted from GameAgentVisual's inventory evaluator."""

from pathlib import Path
import re
from uuid import UUID

import nbtlib


def inventory(world: Path, player: UUID) -> dict[str, int]:
    data = nbtlib.load(world / "playerdata" / f"{player}.dat")
    if int(data["DataVersion"]) != 3700:
        raise ValueError("Inventory evaluation requires Minecraft Java 1.20.4")
    counts: dict[str, int] = {}
    for stack in data["Inventory"]:
        name, count = str(stack["id"]), int(stack["Count"])
        if not re.fullmatch(r"minecraft:[a-z0-9_]+", name) or count <= 0:
            raise ValueError("Invalid saved inventory stack")
        counts[name] = counts.get(name, 0) + count
    return counts


def validate_requirements(requirements: object) -> list[tuple[str, int | None, int | None, int | None]]:
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Provide at least one inventory requirement")
    parsed = []
    for requirement in requirements:
        if not isinstance(requirement, dict) or set(requirement) - {"item", "min_count", "max_count", "min_delta"}:
            raise ValueError("Invalid inventory requirement")
        name = requirement.get("item")
        if not isinstance(name, str) or not re.fullmatch(r"(minecraft:)?[a-z0-9_]+", name):
            raise ValueError("Invalid inventory item identifier")
        name = name if ":" in name else "minecraft:" + name
        thresholds = {key: requirement[key] for key in ("min_count", "max_count", "min_delta") if key in requirement}
        if not thresholds or any(type(value) is not int or value < 0 for value in thresholds.values()):
            raise ValueError("Inventory thresholds must be nonnegative integers")
        low, high, delta_min = requirement.get("min_count"), requirement.get("max_count"), requirement.get("min_delta")
        if high is not None and low is not None and high < low:
            raise ValueError("max_count must not be below min_count")
        parsed.append((name, low, high, delta_min))
    return parsed


def evaluate_inventory(
    before: Path, after: Path, player: UUID, requirements: list[dict],
) -> dict:
    parsed = validate_requirements(requirements)
    initial, final = inventory(before, player), inventory(after, player)
    checks = []
    for name, low, high, delta_min in parsed:
        old, new = initial.get(name, 0), final.get(name, 0)
        checks.append({
            "item": name, "before_count": old, "actual_count": new, "delta": new - old,
            "passed": (low is None or new >= low) and (high is None or new <= high)
            and (delta_min is None or new - old >= delta_min),
        })
    return {"success": all(check["passed"] for check in checks), "checks": checks,
            "player_uuid": str(player), "inventory_before": initial, "inventory_after": final}
