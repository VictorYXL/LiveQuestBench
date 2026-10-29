"""Exact native replica cells with an unchanged original model."""

from pathlib import Path
from uuid import UUID

from game.minecraft.evaluators.state import evaluate_state, validate_state
from game.minecraft.evaluators.structure import validate_config
from game.minecraft.evaluators.world import AIR, read_blocks, region_bounds


def validate_replica(*, structure: dict, model_region: dict) -> None:
    validate_state(structure=structure)
    cells, dimension, build_low, build_high, _ = validate_config(structure)
    low, high = region_bounds(model_region, dimension)
    if any(high[i] - low[i] != build_high[i] - build_low[i] for i in range(3)):
        raise ValueError("Model and replica bounding boxes must have matching dimensions")
    if all(low[i] <= build_high[i] and build_low[i] <= high[i] for i in range(3)):
        raise ValueError("Original and replica regions cannot overlap")
    if any(max(point[i] for point in cells) != high[i] - low[i] for i in range(3)):
        raise ValueError("Replica target dimensions must cover the entire visible model")
    if any(name is None for name in cells.values()):
        raise ValueError("Replica target must declare every visible model cell, including air")


def verify_initial_replica(before: Path, *, structure: dict, model_region: dict) -> None:
    validate_replica(structure=structure, model_region=model_region)
    cells, dimension, build_low, build_high, _ = validate_config(structure)
    low, high = region_bounds(model_region, dimension)
    model = read_blocks(before, low, high, dimension)
    for point, expected in cells.items():
        actual = model[tuple(low[i] + point[i] for i in range(3))]
        if actual != expected and not (actual in AIR and expected in AIR):
            raise ValueError("Initial visible model does not match the replica target")
    if any(name not in AIR for name in read_blocks(before, build_low, build_high, dimension).values()):
        raise ValueError("Initial replica pad must be empty")


def evaluate_replica(before: Path, after: Path, player: UUID, *, structure: dict, model_region: dict) -> dict:
    verify_initial_replica(before, structure=structure, model_region=model_region)
    dimension = structure.get("dimension", "minecraft:overworld")
    low, high = region_bounds(model_region, dimension)
    initial = read_blocks(before, low, high, dimension)
    final = read_blocks(after, low, high, dimension)
    result = evaluate_state(before, after, player, structure=structure)
    result["checks"].append({"kind": "original_model_preserved", "passed": initial == final})
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " Exact replica materials and required air cells are checked at the marked orientation; "
        "the original model must remain unchanged. Endpoint success alone does not establish information-use benefit."
    )
    return result
