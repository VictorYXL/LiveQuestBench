"""Reproduce the same-ST-stance camera/body fixed-point bridge offline."""

import argparse
import json
import math
from pathlib import Path

from veloren_s05_aim_geometry import (
    NATIVE, ST, digest, intersects_box, third_person_points,
)


EXTRA_SOURCES = (
    "voxygen/src/session/target.rs",
    "voxygen/src/session/settings_change.rs",
    "voxygen/src/key_state.rs",
    "voxygen/src/hud/esc_menu.rs",
    "voxygen/src/hud/settings_window/gameplay.rs",
    "voxygen/src/hud/settings_window/interface.rs",
    "voxygen/src/scene/figure/cache.rs",
    "common/src/comp/character_state.rs",
)


def compensated_body_direction(actor, target, body_heading):
    muzzle = (actor[0] + .44 * math.cos(body_heading),
              actor[1] + .44 * math.sin(body_heading))
    return math.atan2(target[1] - muzzle[1], target[0] - muzzle[0])


def same_stance(root, package):
    old = json.loads((package / "checks/s05-public-geometry-20261029.json").read_text())
    reference = json.loads((root / ST / "reference.json").read_text())
    fixture = json.loads((root / ST / "game/fixture.json").read_text())["fixture"]
    boxes = []
    for block in fixture["blocks"]:
        origin = [v - off for v, off in zip(block["origin"], (18700, 10800, 501))]
        boxes.append((origin, [a + b for a, b in zip(origin, block["size"])]))
    actions = reference["actions"]
    aims = [(index, row) for index, row in enumerate(actions)
            if row["input"]["name"] == "LookTool"
            and row["input"]["arguments"].get("z", 999) < 501]
    rows = []
    for aim_index in (*range(2, 17), *range(21, 36)):
        action_index, action = aims[aim_index]
        observation = max(
            (row for row in reference["public_motion_observations"]
             if row["elapsed"] <= action["elapsed"]),
            key=lambda row: row["elapsed"])
        actor = tuple(v - off for v, off in zip(observation["position"], (18700, 10800, 501)))
        args = action["input"]["arguments"]
        target = (args["x"] - 18700, args["y"] - 10800, .9)
        edge = 4 if aim_index < 20 else 21
        focus, muzzle = third_person_points(actor, target)
        dx, dy = target[0] - actor[0], target[1] - actor[1]
        distance = math.hypot(dx, dy)
        heading = math.atan2(dy, dx)
        camera_heading = heading + math.asin(.6 / distance)
        compensated = compensated_body_direction(actor, target, heading)
        assert abs(compensated - heading) < 1e-10
        assert not any(intersects_box(focus, target, lo, hi) for lo, hi in boxes)
        assert not any(intersects_box(muzzle, target, lo, hi) for lo, hi in boxes)
        cone = math.asin(.44 / distance)
        relative_to_normal = abs(math.atan2(dx, -dy))
        inset = actor[1] - edge
        cone_clearance = .44 * math.cos(cone + relative_to_normal) - inset
        look = action["result"]["detail"]["look"]
        drop = muzzle[2] - .9
        impact = [muzzle[j] + look[j] * drop / -look[2] for j in (0, 1)]
        attack = actions[action_index + 1]
        assert attack["input"] == {
            "name": "AttackTool", "arguments": {"channel": "primary", "duration_ticks": 30}}
        rows.append({
            "aim_sample_index": aim_index,
            "actor_public_sample_elapsed": observation["elapsed"],
            "actor_public_sample_position": observation["position"],
            "actor_public_sample_velocity": observation["velocity"],
            "target_ST_public_aim_xy": [args["x"], args["y"]],
            "analytic_target_height_above_floor": .9,
            "camera_focus_local": focus,
            "fixed_point_muzzle_local": muzzle,
            "camera_body_yaw_difference_degrees": math.degrees(camera_heading - heading),
            "focus_outboard_distance": edge - focus[1],
            "fixed_point_muzzle_outboard_distance": edge - muzzle[1],
            "body_cone_half_angle_degrees": math.degrees(cone),
            "body_cone_muzzle_outboard_lower_bound": cone_clearance,
            "ST_native_look_vector": look,
            "straight_ST_ray_distance_to_sampled_body_center_at_height_0_9": math.dist(impact, target[:2]),
            "native_attack_duration_ticks": 30,
            "look_finished_tick": action["result"]["finished_tick"],
            "attack_finished_tick": attack["result"]["finished_tick"],
            "unrefreshed_look_ticks_after_completion": (
                attack["result"]["finished_tick"] - action["result"]["finished_tick"]),
        })
    sources = dict(old["native_source_pins"])
    sources.update({name: digest(root / NATIVE / name) for name in EXTRA_SOURCES})
    for name, expected in sources.items():
        assert digest(root / NATIVE / name) == expected, name
    return {
        "schema": "livequest-s05-same-stance-camera-body-bridge/1",
        "analysis_base": "601989ea9286ac2f55a5731861c3654ef3235a8d",
        "status": "source_bound_constructive_transfer_proposal_not_new_native_success",
        "native_source_pins": sources,
        "retained_geometry_receipt_sha256": digest(package / "checks/s05-public-geometry-20261029.json"),
        "original_ST_reference_sha256": digest(root / ST / "reference.json"),
        "public_adapter_pins": {
            path: digest(package / path) for path in
            ("game/backends/x11/actions.py", "game/backends/x11/interface.py")},
        "native_ST_stance_samples": rows,
        "bounds_over_30_actual_sampled_stances": {
            "minimum_camera_focus_outboard": min(x["focus_outboard_distance"] for x in rows),
            "maximum_native_focus_interpolation_deadband_norm": math.sqrt(.001),
            "minimum_fixed_point_muzzle_outboard": min(x["fixed_point_muzzle_outboard_distance"] for x in rows),
            "minimum_entire_body_cone_muzzle_outboard": min(x["body_cone_muzzle_outboard_lower_bound"] for x in rows),
            "maximum_static_ST_ray_body_center_error": max(
                x["straight_ST_ray_distance_to_sampled_body_center_at_height_0_9"] for x in rows),
            "minimum_unrefreshed_ST_look_ticks": min(x["unrefreshed_look_ticks_after_completion"] for x in rows),
            "maximum_unrefreshed_ST_look_ticks": max(x["unrefreshed_look_ticks_after_completion"] for x in rows),
        },
        "proof_boundaries": [
            "Actor and targetXY samples are actual ST public history, not public VM observations.",
            "The third-person yaw differs from body yaw: the native compensated-body fixed point is proved separately.",
            "The body cone is a geometric invariant for a fixed target bearing once entered, not an observed renderer trajectory.",
            "Native damping and the instantaneous branch do not justify claiming exact asymptotic orientation convergence.",
            "Camera ray through the0.9m capsule-center point has zero distance to the native capsule axis regardless of wolf yaw.",
            "All30 recorded shots retain the native look during30 attack ticks; aggregate18+18 qualifying hits are actual native evidence, not per-action-ID attribution.",
            "The static ray error omits gravity and air drag; actual native hit evidence, not that straight-line calculation, grounds damage.",
            "No new camera mode, public settings change, player stance, hit or trajectory is represented as executed.",
            "No F3 key is admitted by the unchanged X11 key whitelist.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = same_stance(args.repository_root.resolve(), Path(__file__).resolve().parents[1])
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output),
                      "bounds": result["bounds_over_30_actual_sampled_stances"]}))


if __name__ == "__main__":
    main()
