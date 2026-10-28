"""Before/after blueprint scoring following GameAgentVisual's StructureEvaluator."""

import math
from pathlib import Path

from game.minecraft.evaluators.world import AIR, Position, block_name, read_blocks, region_bounds


MAX_CELL_COMPARISONS = 5000000


def _parse_structure(structure: object) -> dict[Position, str | None]:
    if not isinstance(structure, list) or not structure:
        raise ValueError("target.structure must be a nonempty rectangular list in [y][z][x] order")
    cells: dict[Position, str | None] = {}
    depth = width = None
    for y, layer in enumerate(structure):
        if not isinstance(layer, list) or not layer or (depth is not None and len(layer) != depth):
            raise ValueError("Structure layers must have equal, nonzero depth")
        depth = len(layer)
        for z, row in enumerate(layer):
            if not isinstance(row, list) or not row or (width is not None and len(row) != width):
                raise ValueError("Structure rows must have equal, nonzero width")
            width = len(row)
            for x, value in enumerate(row):
                cells[x, y, z] = None if value is None else block_name(value)
    if not any(name is not None and name not in AIR for name in cells.values()):
        raise ValueError("Structure must contain at least one required non-air block")
    return cells


def _rotate(position: Position, turns: int) -> Position:
    x, y, z = position
    for _ in range(turns):
        x, z = -z, x
    return x, y, z


def validate_config(config: object) -> tuple[dict[Position, str | None], str, Position, Position, dict]:
    if not isinstance(config, dict) or set(config) - {"target", "match", "dimension", "region"}:
        raise ValueError("Invalid structure evaluator configuration")
    target = config.get("target")
    if not isinstance(target, dict) or set(target) != {"structure"}:
        raise ValueError("Structure evaluation requires target.structure")
    cells = _parse_structure(target["structure"])
    dimension = config.get("dimension", "minecraft:overworld")
    if not isinstance(dimension, str):
        raise ValueError("Structure dimension must be a string")
    low, high = region_bounds(config.get("region"), dimension)
    match = config.get("match", {})
    thresholds = ("min_recall", "min_precision", "min_iou")
    flags = ("rotation_invariant", "require_empty", "require_new_blocks")
    if not isinstance(match, dict) or set(match) - set(thresholds + flags):
        raise ValueError("Invalid structure match settings")
    for key in thresholds:
        value = match.get(key, 1.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} must be finite and in [0, 1]")
    for key in flags:
        if type(match.get(key, True)) is not bool:
            raise ValueError(f"{key} must be a boolean")
    settings = {key: match.get(key, 1.0) for key in thresholds} | {key: match.get(key, True) for key in flags}
    if len(cells) > MAX_CELL_COMPARISONS:
        raise ValueError("Structure exceeds the supported comparison budget")
    return cells, dimension, low, high, settings


def evaluate_structure(before: Path, after: Path, config: dict) -> dict:
    """Match a translated, optionally Y-rotated blueprint inside an explicit region.

    Names are scored, not block properties, entities, functionality or causality.
    Invalid configuration and incomplete evidence raise instead of yielding a score.
    """
    cells, dimension, low, high, settings = validate_config(config)
    initial = read_blocks(before, low, high, dimension)
    final = read_blocks(after, low, high, dimension)
    changes = {p: (initial[p], value) for p, value in final.items() if initial[p] != value}
    materials = {name for name in cells.values() if name is not None and name not in AIR}
    placed = {p: value for p, (_, value) in changes.items() if value in materials}
    anchors = placed if settings["require_new_blocks"] else {
        p: value for p, value in final.items() if value in materials
    }
    best = best_rank = None
    comparisons = 0
    for turns in range(4 if settings["rotation_invariant"] else 1):
        rotated = {_rotate(p, turns): value for p, value in cells.items()}
        positive = {p: value for p, value in rotated.items() if value is not None and value not in AIR}
        minimum = tuple(min(p[axis] for p in rotated) for axis in range(3))
        maximum = tuple(max(p[axis] for p in rotated) for axis in range(3))
        offsets: set[Position] = set()
        for p, actual in anchors.items():
            for q, expected in positive.items():
                comparisons += 1
                if comparisons > MAX_CELL_COMPARISONS:
                    raise ValueError("Structure search exceeds comparison budget; narrow the scoring region")
                if actual != expected:
                    continue
                offset = (p[0] - q[0], p[1] - q[1], p[2] - q[2])
                if all(low[axis] <= offset[axis] + minimum[axis]
                       and offset[axis] + maximum[axis] <= high[axis] for axis in range(3)):
                    offsets.add(offset)
        for offset in sorted(offsets):
            comparisons += len(cells) + len(placed)
            if comparisons > MAX_CELL_COMPARISONS:
                raise ValueError("Structure search exceeds comparison budget; narrow the scoring region")
            footprint = {
                (p[0] + offset[0], p[1] + offset[1], p[2] + offset[2]): value
                for p, value in rotated.items()
            }
            missing, empty = [], []
            matched = 0
            for p, expected in footprint.items():
                actual = final[p]
                if expected is None:
                    continue
                if expected in AIR:
                    if settings["require_empty"] and actual not in AIR:
                        empty.append({"position": list(p), "actual": actual})
                elif actual == expected and (not settings["require_new_blocks"] or initial[p] != expected):
                    matched += 1
                else:
                    missing.append({"position": list(p), "expected": expected, "before": initial[p], "actual": actual})
            extra = [{"position": list(p), "actual": value} for p, value in placed.items() if p not in footprint]
            count = len(positive)
            recall = matched / count
            precision = matched / (matched + len(extra)) if matched + len(extra) else 1.0
            iou = matched / (count + len(extra))
            passed = (recall >= settings["min_recall"] and precision >= settings["min_precision"]
                      and iou >= settings["min_iou"] and not empty)
            rank = (passed, recall, precision, iou, -len(empty))
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best = {
                    "passed": passed, "rotation_degrees": turns * 90, "offset": list(offset),
                    "matched": matched, "target_count": count, "extra_count": len(extra),
                    "empty_violations": len(empty), "recall": recall, "precision": precision, "iou": iou,
                    "missing": missing, "extra": extra, "empty_violations_detail": empty,
                }
    success = best is not None and best["passed"]
    return {
        "success": success, "evaluator": "structure", "version": "minecraft-1.20.4-structure",
        "dimension": dimension, "region": {"min": list(low), "max": list(high)}, "settings": settings,
        "coverage": {"before_blocks": len(initial), "after_blocks": len(final), "changed_blocks": len(changes)},
        "best_match": best,
        "changes_sample": [{"position": list(p), "before": old, "after": new}
                           for p, (old, new) in list(changes.items())[:200]],
        "changes_truncated": len(changes) > 200,
        "reason": "structure requirements met" if success else "structure requirements not met",
    }
