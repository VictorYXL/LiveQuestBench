"""Author-only physical route/inspection witnesses, never a scorer or controller."""

import argparse
import heapq
import json
import math
from pathlib import Path

from game.veloren.fixture import solid_voxels
from game.veloren.prototypes.covered_support_forks_solid import build_solid_candidate
from game.veloren.prototypes.rest_support_audit import sweep_clear


HEIGHT = 2.3333332538604736
RADIUS = .45


def supported_cells(voxels, z):
    return {
        (x, y) for x, y, floor_z in voxels if floor_z == z - 1
        and sweep_clear(voxels, [x + .5, y + .5, z], [x + .5, y + .5, z],
                        radius=RADIUS, height=HEIGHT, supported=True)
    }


def distances(cells, start):
    if start not in cells:
        raise ValueError("The route witness must start on full native-body support")
    result, parents, pending = {start: 0.0}, {start: None}, [(0.0, start)]
    while pending:
        cost, (x, y) = heapq.heappop(pending)
        if cost != result[(x, y)]:
            continue
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            nxt = (x + dx, y + dy)
            if nxt not in cells:
                continue
            # Requiring both side cells proves the whole diagonal sweep's box.
            if dx and dy and ((x + dx, y) not in cells or (x, y + dy) not in cells):
                continue
            candidate = cost + math.hypot(dx, dy)
            if candidate < result.get(nxt, float("inf")):
                result[nxt] = candidate
                parents[nxt] = (x, y)
                heapq.heappush(pending, (candidate, nxt))
    return result, parents


def segment_hit(voxels, start, end):
    """First solid unit-AABB hit; no image/rendering or camera-pose claim."""
    hit, nearest = None, float("inf")
    ranges = [range(math.floor(min(a, b)), math.floor(max(a, b)) + 1)
              for a, b in zip(start, end)]
    for x in ranges[0]:
        for y in ranges[1]:
            for z in ranges[2]:
                cell = (x, y, z)
                if cell not in voxels:
                    continue
                low, high = 0.0, 1.0
                for a, b, bound in zip(start, end, cell):
                    delta = b - a
                    if delta == 0:
                        if not bound <= a <= bound + 1:
                            high = -1
                            break
                    else:
                        t1, t2 = (bound - a) / delta, (bound + 1 - a) / delta
                        low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
                if low <= high and low < nearest:
                    hit, nearest = cell, low
    return hit


def world_cell(origin, stage, x, y):
    sign = stage["heading_y"]
    offset_x = stage["entry"][0] - .5
    offset_y = stage["entry"][1] + sign * 4 - .5
    return (int(origin[0] + offset_x + sign * x),
            int(origin[1] + offset_y + sign * y))


def inspection_patch(voxels, other_voxels, stand, patches):
    eye = (stand[0] + .5, stand[1] + .5, 501 + HEIGHT * .8)
    for x, y in patches:
        target = (x, y, 500)
        occupied, absent = (voxels, other_voxels) if target in voxels else (other_voxels, voxels)
        if all(
            segment_hit(occupied, eye, (x + dx, y + dy, 500.999)) == target
            and segment_hit(absent, eye, (x + dx, y + dy, 500.999)) is None
            for dx, dy in ((.375, .375), (.375, .625), (.625, .375), (.625, .625))
        ):
            return {"voxel": list(target), "surface_patch_width_m": .25}
    return None


def audit(world_path):
    candidates = [build_solid_candidate(world_path, seed) for seed in (0, 1)]
    variants = [solid_voxels(task["fixture"]) for task, _ in candidates]
    rows = []
    for index, (task, private) in enumerate(candidates):
        voxels, other = variants[index], variants[1 - index]
        upper = supported_cells(voxels, 501)
        start = tuple(int(v) for v in task["fixture"]["player_state"]["position"][:2])
        goal = tuple(int(v) for v in task["evaluator"]["parameters"]["position"]["target"][:2])
        all_distances, parents = distances(upper, start)
        path, cursor = [], goal
        while cursor is not None:
            path.append(cursor)
            cursor = parents[cursor]
        path.reverse()
        stages = []
        for stage in private["source_proposal"]["stages"]:
            origin = private["source_proposal"]["origin"]
            entry = world_cell(origin, stage, 0, -4)
            exit_cell = world_cell(origin, stage, 0, 19 + stage["gap_span"])
            from_entry, _ = distances(upper, entry)
            from_exit, _ = distances(upper, exit_cell)
            inspections = {}
            for side, xs in (("left", range(-5, -2)), ("right", range(3, 6))):
                patches = [world_cell(origin, stage, x, y)
                           for x in xs for y in (12, 13)]
                options = []
                for x in range(-9, 10):
                    if (side == "left" and x >= 0) or (side == "right" and x <= 1):
                        continue
                    for y in range(-1, 12):
                        stand = world_cell(origin, stage, x, y)
                        if stand not in upper or stand not in from_entry or stand not in from_exit:
                            continue
                        patch = inspection_patch(voxels, other, stand, patches)
                        if patch is not None:
                            options.append((
                                from_entry[stand] + from_exit[stand],
                                from_entry[stand], stand, patch,
                            ))
                if not options:
                    raise ValueError("No direct inspection witness found")
                cost, approach, stand, patch = min(options, key=lambda row: row[:3])
                inspections[side] = {
                    "standing_cell": list(stand),
                    "eye_position": [stand[0] + .5, stand[1] + .5, 501 + HEIGHT * .8],
                    "visible_patch": patch,
                    "entry_to_view_grid_walk_m": approach,
                    "entry_via_view_to_exit_grid_walk_m": cost,
                    "extra_vs_known_supported_grid_walk_m": cost - from_entry[exit_cell],
                }
            lower = supported_cells(voxels, 496)
            wrong_x = 4 if private["side"] == "left" else -4
            lower_start = world_cell(origin, stage, wrong_x, 12)
            lower_end = world_cell(origin, stage, wrong_x, 11 + stage["gap_span"])
            lower_distance, _ = distances(lower, lower_start)
            lip = [lower_end[0] + .5, lower_end[1] + .5, 501]
            floor = [lower_end[0] + .5, lower_end[1] + .5, 496]
            deck_cell = world_cell(origin, stage, wrong_x, 12 + stage["gap_span"])
            deck = [deck_cell[0] + .5, deck_cell[1] + .5, 501]
            recovery_clear = (
                sweep_clear(voxels, floor, lip, radius=RADIUS, height=HEIGHT, supported=False)
                and sweep_clear(voxels, lip, deck, radius=RADIUS, height=HEIGHT, supported=False)
                and sweep_clear(voxels, deck, deck, radius=RADIUS, height=HEIGHT, supported=True)
            )
            bridge = {tuple(origin[i] + p[i] for i in (0, 1)) for p in stage["bridge"]}
            stages.append({
                "heading_y": stage["heading_y"],
                "gap_m": stage["gap_span"],
                "known_supported_grid_walk_m": from_entry[exit_cell],
                "inspection": inspections,
                "lower_recovery": {
                    "floor_grid_walk_between_inner_centres_m": lower_distance[lower_end],
                    "vertical_clearance_to_deck_m": 5,
                    "lip_horizontal_crossing_m": 1,
                    "full_body_sweeps_clear": recovery_clear,
                    "native_execution_or_time_measured": False,
                },
                "whole_supported_route_crosses_this_bridge": bool(bridge.intersection(path)),
            })
        compass_choices = ["left" if stage["heading_y"] == 1 else "right" for stage in stages]
        compass_views = [tuple(stage["inspection"][side]["standing_cell"])
                         for stage, side in zip(stages, compass_choices)]
        compass_cost, cursor = 0.0, start
        for waypoint in compass_views + [goal]:
            compass_cost += distances(upper, cursor)[0][waypoint]
            cursor = waypoint
        first_left_view = tuple(stages[0]["inspection"]["left"]["standing_cell"])
        first_only_cost = all_distances[first_left_view] + distances(upper, first_left_view)[0][goal]
        native_anchor = (18715, 10836)
        rows.append({
            "side": private["side"],
            "whole_supported_grid_walk_m": all_distances[goal],
            "whole_supported_route_cells": [list(p) for p in path],
            "stages": stages,
            "first_application_left_inspection_then_remember_bit": {
                "whole_supported_grid_walk_m": first_only_cost,
                "extra_vs_known_whole_grid_walk_m": first_only_cost - all_distances[goal],
                "second_information_acquisition_required": False,
            },
            "memoryless_world_west_inspection_and_ground_retreat": {
                "relative_choices": compass_choices,
                "unsupported_initial_choices": sum(side != private["side"] for side in compass_choices),
                "whole_supported_grid_walk_m": compass_cost,
                "extra_vs_known_whole_grid_walk_m": compass_cost - all_distances[goal],
                "ability_energy_expenditure": "No climbing/gliding/jumping is required by this supported walk.",
            },
            "continuation_from_native_endpoint_cell_centre": {
                "anchor": [native_anchor[0] + .5, native_anchor[1] + .5, 501],
                "remaining_supported_grid_walk_m": distances(upper, native_anchor)[0][goal],
                "boundary": "Nearby fully supported cell centre, not an invented intermediate native pose.",
            },
        })
    return {
        "schema": "covered-support-forks-cold-route-witness/1",
        "kind": "static_actual_fixture_native_body_and_solid_visibility",
        "native_execution": False,
        "metric": (
            "Metres along shortest eight-neighbour cell-centre supported walks with both "
            "side cells clear at diagonal steps, not a score, "
            "elapsed time, global-optimal controller or lower bound on all legal routes. "
            "Inspection is a first-person solid-ray witness to a quarter-metre patch, not "
            "a rendered classification. Third-person corner viewing, finer continuous paths, "
            "jump/glide/cling can be cheaper and remain legal."
        ),
        "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.world), indent=2) + "\n")
