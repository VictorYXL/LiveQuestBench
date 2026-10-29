"""Author-only finite-clearance audit; never an agent observation or native simulator."""

import argparse
import json
import math
from pathlib import Path

from game.veloren.fixture import solid_voxels
from game.veloren.prototypes.ballistic_aperture import build_instance


def intersects_box(start, end, lower, upper):
    near, far = 0.0, 1.0
    for origin, target, low, high in zip(start, end, lower, upper):
        delta = target - origin
        if abs(delta) < 1e-12:
            if not low <= origin <= high:
                return False
        else:
            a, b = sorted(((low - origin) / delta, (high - origin) / delta))
            near, far = max(near, a), min(far, b)
            if near > far:
                return False
    return True


def clear_segment(start, end, cells, radius):
    return not any(intersects_box(
        start, end, [x - radius, y - radius], [x + 1 + radius, y + 1 + radius],
    ) for x, y in cells)


def ballistic_bounds(distance):
    # Pinned native sources: arrow_shot.ron, phys/mod.rs, phys/weather.rs,
    # body/object.rs, body/humanoid.rs and comp/fluid_dynamics.rs.
    speed, residual_speed, step, drag_bound = 115.0, .1, .1, 8.0
    linear_speed = speed - residual_speed - drag_bound * step / 2
    corrected_distance = distance + drag_bound * step**2 / 8
    time_bound = 2 * corrected_distance / (
        linear_speed + math.sqrt(linear_speed**2 - 2 * drag_bound * corrected_distance)
    )
    wind_bound = math.sqrt(600)
    drag_factor = .5 * 1.225 * (.02 * math.pi * .005**2) / .003
    relative_speed_bound = speed + residual_speed + 33 * time_bound + wind_bound
    assert drag_factor * relative_speed_bound**2 < drag_bound
    lateral_acceleration = (
        drag_factor * relative_speed_bound * (wind_bound + residual_speed)
        / (1 - drag_factor * relative_speed_bound * time_bound)
    )
    # The final collision ray can cover only part of its integration step.
    integration_bound = .5 * (time_bound**2 + step * time_bound) + step**2 / 8
    lateral_error = residual_speed * time_bound + lateral_acceleration * integration_bound
    muzzle_z = 501 + (20 / 9 * 1.05) * .8
    lower_z = muzzle_z - (25 + drag_bound) * integration_bound
    assert lateral_error < .04 and 502 < lower_z < muzzle_z < 503
    return {
        "maximum_flight_seconds": time_bound,
        "maximum_transverse_displacement": lateral_error,
        "vertical_corridor": [lower_z, muzzle_z],
        "assumptions": [
            "Stock starter bow fully charged: range multiplier1, launch speed115m/s.",
            "Grounded scale1 MaleHuman atz501, horizontal aim, residual horizontal speed<=0.1m/s.",
            "Dry-air native arrow: mass0.003kg, dimensions0.01x0.8x0.01m, drag coefficient0.02.",
            "Native air density1.225; simulated wind squared-magnitude clamp600.",
            "Native force-step cap0.1s, gravity<=25m/s^2; conservative8m/s^2 total aerodynamic bound.",
            "Stationary grounded native target; moving or jumping targets require lawful waiting/re-aiming.",
        ],
        "scope": "Conservative source-bound component argument, not an engine replay or task success.",
    }


def support_report(task, selected, stance_error=.09):
    voxels = solid_voxels(task["fixture"])
    arrow_cells = {(x, y) for x, y, z in voxels if z == 502}
    body_cells = {(x, y) for x, y, z in voxels if z in (501, 502, 503)}
    checked_paths = 0
    minimum_clearance = .5
    minimum_contact_length = 1.0
    maximum_distance = 0.0
    firing_points = []
    entry_x = (18709.7, 18712.5, 18715.3)[selected]
    impact_dx = (.25, 0, -.25)[selected]
    for front in (10810, 10832):
        for target_x in (18712.45, 18712.55):
            for target_y in (front + 10.4, front + 12.6):
                impact = [target_x + impact_dx, target_y - .25]
                stance = [entry_x + (entry_x - impact[0]) * 4.5 / (impact[1] - front - .5),
                          front - 4]
                firing_points.append(stance)
                for dx in (-stance_error, stance_error):
                    for dy in (-stance_error, stance_error):
                        start = [stance[0] + dx, stance[1] + dy]
                        length = math.dist(start, impact)
                        direction = [(b - a) / length for a, b in zip(start, impact)]
                        target = [target_x, target_y]
                        offset = sum((a - b) * v for a, b, v in zip(target, impact, direction))
                        end = [p + (offset + .15) * v for p, v in zip(impact, direction)]
                        perpendicular = abs((target_x - start[0]) * direction[1]
                                            - (target_y - start[1]) * direction[0])
                        # Entity collision samples at <=0.3m; retain a longer clear
                        # chord inside the target, rather than one interior point.
                        contact_length = math.sqrt(.4**2 - (perpendicular + .04)**2) + .15
                        minimum_contact_length = min(minimum_contact_length, contact_length)
                        assert clear_segment(start, start, body_cells, .45), "Blocked firing stance"
                        low, high = 0.0, .5
                        assert clear_segment(start, end, arrow_cells, 0), "Blocked nominal ray"
                        for _ in range(16):
                            middle = (low + high) / 2
                            if clear_segment(start, end, arrow_cells, middle):
                                low = middle
                            else:
                                high = middle
                        minimum_clearance = min(minimum_clearance, low)
                        maximum_distance = max(maximum_distance, math.dist(start, end))
                        checked_paths += 1
    for first in firing_points[:4]:
        for second in firing_points[4:]:
            route = [first, [18702.5, 10806], [18702.5, 10828], second]
            for start, end in zip(route, route[1:]):
                assert clear_segment(start, end, body_cells, .45), "Blocked inter-structure walk"
                for x in range(math.floor(min(start[0], end[0]) - .45),
                               math.floor(max(start[0], end[0]) + .45) + 1):
                    for y in range(math.floor(min(start[1], end[1]) - .45),
                                   math.floor(max(start[1], end[1]) + .45) + 1):
                        assert (x, y, 500) in voxels, "Unsupported walk"
    assert minimum_clearance > .04, "Insufficient finite projectile clearance"
    assert minimum_contact_length > .3, "Insufficient native entity sampling interval"
    return {
        "selected": selected, "checked_extreme_rays": checked_paths,
        "minimum_xy_square_tube_half_width": minimum_clearance,
        "maximum_root_to_impact_distance": maximum_distance,
        "minimum_target_contact_length": minimum_contact_length,
        "native_source_ballistic_bounds": ballistic_bounds(maximum_distance),
        "native_point_projectile_tube_half_width_checked": .04,
        "stance_axis_error_checked": stance_error,
        "standing_body_half_width": .45,
        "standing_body_height": 7 / 3,
        "fully_supported_inter_structure_walk": True,
        "target_grounded_position_bounds": {
            "x": [18712.45, 18712.55],
            "y_relative_to_front": [10.4, 12.6],
            "z": 502,
        },
        "scope": "Finite geometry at extreme grounded poses plus conditional native-source bounds. "
                 "Not an engine replay, public motor execution, success or learning score.",
    }


def audit(world):
    reports = {}
    for seed in range(64):
        task, private = build_instance(world, seed)
        choice = private["open_slot"]
        if choice not in reports:
            reports[choice] = support_report(task, choice)
        if len(reports) == 3:
            break
    return {
        "schema": "native-aperture-finite-clearance/1",
        "author_only": True, "native_episode": False, "qualified": False,
        "task": "hidden_ballistic_aperture_prototype_v7",
        "layouts": [reports[key] for key in sorted(reports)],
        "limits": [
            "Grounded target positions only; ordinary waiting/re-aiming remains legal.",
            "The .04m tube is a geometry margin, not an unexplained claim about all native errors.",
            "Native arrows use point terrain collision, not a finite body radius.",
            "This audit reads private authored geometry and must never guide an episode policy.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.world)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
