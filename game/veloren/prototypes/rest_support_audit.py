"""Offline, author-only geometry checks; never native events or policy observations."""

import argparse
import json
import math
from pathlib import Path

import yaml

from game.veloren.evaluators.endpoints import state_checks, validate_state
from game.veloren.fixture import solid_voxels


def _cells(low, high):
    return range(math.floor(low), math.ceil(high))


def sweep_clear(voxels, start, end, *, radius, height, supported):
    """Conservative full-footprint proof for one axis-aligned segment.

    The pinned native terrain collision uses an AABB, not the public combat
    radius. This proves clearance/support, not motion, visibility or grounding.
    """
    if radius <= 0 or height <= 0 or not all(
        math.isfinite(value) for value in (*start, *end, radius, height)
    ):
        raise ValueError("Body dimensions and coordinates must be finite and positive")
    if sum(a != b for a, b in zip(start, end)) > 1:
        raise ValueError("Only axis-aligned sweeps are supported")
    low = [min(a, b) for a, b in zip(start, end)]
    high = [max(a, b) for a, b in zip(start, end)]
    xs = _cells(low[0] - radius, high[0] + radius)
    ys = _cells(low[1] - radius, high[1] + radius)
    zs = _cells(low[2], high[2] + height)
    if any((x, y, z) in voxels for x in xs for y in ys for z in zs):
        return False
    if supported:
        if start[2] != end[2] or not float(start[2]).is_integer():
            raise ValueError("Supported sweeps require one integer-height Rock surface")
        return all((x, y, int(start[2]) - 1) in voxels for x in xs for y in ys)
    return True


def audit_instance(task, *, radius=0.45, height=2.3333332538604736):
    """Audit the existing v4 fixture without changing task/score or reading a seed."""
    if task["id"] != "hidden_rest_support_prototype_v4":
        raise ValueError("This diagnostic is scoped to the unchanged v4 candidate")
    parameters = task["evaluator"]["parameters"]
    validate_state(**parameters)
    voxels = solid_voxels(task["fixture"])
    def module(front):
        return {
            (x, y - front, z) for x, y, z in voxels
            if 18707 <= x < 18714 and front - 1 <= y < front + 5 and 501 <= z < 511
        }
    identical = module(10808) == module(10820)
    rows = []
    for side, x in (("left", 18709.5), ("right", 18711.5)):
        modules = []
        for front in (10808, 10820):
            sill = [x, front + 0.5, 506]
            interior = [x, front + 2.5, 506]
            modules.append({
                "front": front,
                "sill": sill,
                "interior": interior,
                "common_sill_supported": sweep_clear(
                    voxels, sill, sill, radius=radius, height=height, supported=True),
                "sill_to_interior_supported": sweep_clear(
                    voxels, sill, interior, radius=radius, height=height, supported=True),
                "front_ascent_clear": sweep_clear(
                    voxels, [x, front - 0.5, 501], [x, front - 0.5, 506],
                    radius=radius, height=height, supported=False),
                "lip_crossing_clear": sweep_clear(
                    voxels, [x, front - 0.5, 506], sill,
                    radius=radius, height=height, supported=False),
            })
        endpoint = modules[1]["interior"]
        hypothetical = {
            "position": endpoint, "velocity": [0, 0, 0], "on_ground": True,
            "survival": {"health": {"current": 100}},
        }
        goal_accepts = state_checks({}, hypothetical, **parameters)["success"]
        rows.append({
            "side": side, "modules": modules,
            "hypothetical_stationary_endpoint_accepted": goal_accepts,
            "supported_endpoint_witness": goal_accepts and modules[1]["sill_to_interior_supported"],
        })
    start = task["fixture"]["player_state"]["position"]
    approach = [start, [18705.5, start[1], 501], [18705.5, 10819.5, 501]]
    approaches = {
        row["side"]: all(
            sweep_clear(voxels, a, b, radius=radius, height=height, supported=True)
            for a, b in zip(
                approach, approach[1:] + [[row["modules"][1]["sill"][0], 10819.5, 501]]
            )
        ) for row in rows
    }
    return {
        "schema": "rest-support-static-composition/1",
        "task_id": task["id"],
        "evidence_kind": "offline_geometry_and_hypothetical_predicate_checks",
        "native_execution": False,
        "body_assumptions": {"terrain_half_width_m": radius, "height_m": height, "scale": 1},
        "module_translation_y_m": 12,
        "modules_identical_under_translation": identical,
        "mapping_independent_ground_approaches": approaches,
        "sides": rows,
        "supported_endpoint_witness_count": sum(row["supported_endpoint_witness"] for row in rows),
        "scope": (
            "Full-footprint static Rock support and clearance, with the actual endpoint predicate. "
            "No claim of native lip traversal, visual observability, timing, learned benefit or success. "
            "The airborne transition from wall contact onto the sill still needs native grounding "
            "evidence or a reviewed applicable native component argument."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_instance(yaml.safe_load(args.task.read_text())), indent=2))
