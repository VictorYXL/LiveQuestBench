"""Offline conditional geometry, not a simulator or a new native outcome."""

import argparse
import hashlib
import json
import math
from pathlib import Path


NATIVE = "output/temp/veloren-native-route-20261027/source"
EXPERIMENTS = "output/temp/task_development/experiments"
ST = f"{EXPERIMENTS}/VE-S05-settled-progress-reference-st"
SOURCE_FILES = (
    "common/systems/src/phys/mod.rs",
    "common/systems/src/phys/collision.rs",
    "common/src/comp/body/mod.rs",
    "common/src/comp/body/humanoid.rs",
    "common/src/consts.rs",
    "common/src/states/utils.rs",
    "common/src/states/charged_ranged.rs",
    "voxygen/src/scene/mod.rs",
    "voxygen/src/scene/camera.rs",
    "voxygen/src/session/mod.rs",
    "voxygen/src/window.rs",
    "voxygen/src/settings/control.rs",
    "voxygen/src/hud/mod.rs",
    "voxygen/src/hud/overhead.rs",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def intersects_box(start, end, lower, upper):
    """Whether a closed segment enters the interior of a solid box."""
    enter, leave = 0.0, 1.0
    for a, b, low, high in zip(start, end, lower, upper):
        delta = b - a
        if abs(delta) < 1e-12:
            if not low < a < high:
                return False
            continue
        first, last = sorted(((low - a) / delta, (high - a) / delta))
        enter, leave = max(enter, first), min(leave, last)
        if enter >= leave:
            return False
    return enter < leave


def face_stance(target, y0, y1, height, outside=0.15):
    """Analysis witness in local authored coordinates, NOT public motor input."""
    x, y = target
    if x >= 24.45 - 1e-9:
        return "east", (24 + outside, min(y1 - .5, max(y0 + .5, y)), height)
    if y <= y0 - .45 + 1e-9:
        return "north", (min(23.5, max(22.5, x)), y0 - outside, height)
    if y >= y1 + .45 - 1e-9:
        return "south", (min(23.5, max(22.5, x)), y1 + outside, height)
    raise ValueError("Target center is not in the separated yard's exterior free region")


def near_wall_envelope(height, speed=115.0, target_speed=1.0, information_error=.1):
    """A sufficient conditional hit envelope, including nonzero target motion."""
    eye = (7 / 3) * .8
    drop = height + eye - .9
    pitch, yaw = math.radians(88), math.radians(3)
    flight = drop / (speed * math.sin(pitch))
    advance = drop / math.tan(pitch)
    x_min, x_max = .05 + .44 * math.cos(yaw), .20 + .44 + advance
    normal_error = max(abs(x_min - .75), abs(x_max - .45))
    tangent_error = .05 + (.44 + advance) * math.sin(yaw)
    static_error = math.hypot(normal_error, tangent_error)
    total_error = static_error + target_speed * flight + information_error
    return {
        "height_above_yard": height,
        "scale": 1,
        "actor_outside_band": [.05, .20],
        "terrain_support_overlap_min": .25,
        "collision_vertical_increment_nominal_max": .225,
        "muzzle_eye_height": eye,
        "muzzle_forward_offset": .44,
        "target_normal_distance_band": [.45, .75],
        "target_tangent_initial_error_max": .05,
        "pitch_degrees": [88, 89],
        "yaw_error_degrees_max": 3,
        "target_cross_section_height": .9,
        "projectile_initial_speed": speed,
        "flight_time_no_drag_upper_estimate": flight,
        "static_horizontal_error_bound": static_error,
        "conditional_target_speed_bound": target_speed,
        "additional_information_and_control_error_budget": information_error,
        "conditional_horizontal_error_bound": total_error,
        "wolf_capsule_core_radius": .625,
        "conditional_radius_margin": .625 - total_error,
    }


def third_person_points(actor, target):
    dx, dy = target[0] - actor[0], target[1] - actor[1]
    distance = math.hypot(dx, dy)
    if distance <= .6:
        raise ValueError("Target is inside the third-person lateral-focus circle")
    heading = math.atan2(dy, dx) + math.asin(.6 / distance)
    focus = (actor[0] + .6 * math.sin(heading),
             actor[1] - .6 * math.cos(heading), actor[2] + (7 / 3) * 1.05)
    muzzle = (actor[0] + .44 * dx / distance,
              actor[1] + .44 * dy / distance, actor[2] + (7 / 3) * .8)
    return focus, muzzle


def report(root):
    fixture_path = root / ST / "game/fixture.json"
    reference_path = root / ST / "reference.json"
    observation_path = root / ST / "before/observation.json"
    fixture = json.loads(fixture_path.read_text())["fixture"]
    reference = json.loads(reference_path.read_text())
    boxes = []
    for block in fixture["blocks"]:
        origin = [v - offset for v, offset in zip(block["origin"], (18700, 10800, 501))]
        boxes.append((origin, [a + b for a, b in zip(origin, block["size"])]))
    coverage = []
    for label, y0, y1, height, low_y, high_y in (
        ("north", 4, 12, 5, 1.5, 14.5),
        ("south", 21, 29, 6, 17.5, 30.5),
    ):
        clear = 0
        for ix in range(25):
            for iy in range(27):
                target = (22.5 + ix * .5, low_y + iy * .5)
                if target[1] > high_y:
                    continue
                try:
                    _, stance = face_stance(target, y0, y1, height)
                except ValueError:
                    continue
                camera = (stance[0], stance[1], height + 2.0)
                point = (*target, .9)
                if any(intersects_box(camera, point, lo, hi) for lo, hi in boxes):
                    raise AssertionError((label, target, stance))
                clear += 1
        coverage.append({
            "yard": label,
            "sampled_exterior_target_positions": clear,
            "all_selected_camera_segments_clear": True,
            "camera_height_for_grid_check": height + 2.0,
            "scope": "Static solid-terrain visibility only; not rendered pixels, native navigation or moving-target capture.",
        })
    shots = []
    for action in reference["actions"]:
        call = action["input"]
        if call["name"] != "LookTool" or call["arguments"].get("z", 999) >= 501:
            continue
        args = call["arguments"]
        shots.append({
            "elapsed": action["elapsed"],
            "target_xy_from_successful_ST_public_look_argument": [args["x"], args["y"]],
        })
    near_sequences = []
    for name, first, last, edge in (("north", 2, 16, 10804), ("south", 21, 35, 10821)):
        selected = shots[first:last + 1]
        xs = [x["target_xy_from_successful_ST_public_look_argument"][0] for x in selected]
        ds = [edge - x["target_xy_from_successful_ST_public_look_argument"][1] for x in selected]
        near_sequences.append({
            "yard": name, "indices_in_41_aim_samples": [first, last],
            "sample_count": len(selected),
            "elapsed_span": [selected[0]["elapsed"], selected[-1]["elapsed"]],
            "target_x_range": [min(xs), max(xs)],
            "normal_distance_from_face_range": [min(ds), max(ds)],
            "limit": "Discrete actual moving-target samples, not a continuous velocity bound and not VM-visible coordinates.",
        })
    far_examples = []
    for name, index, edge, height in (("north", 19, 4, 5), ("south", 40, 21, 6)):
        xy = shots[index]["target_xy_from_successful_ST_public_look_argument"]
        target = (xy[0] - 18700, xy[1] - 10800, 1.3)
        actor = (22.5, edge - .15, height)
        focus, muzzle = third_person_points(actor, target)
        assert not any(intersects_box(focus, target, lo, hi) for lo, hi in boxes)
        assert not any(intersects_box(muzzle, target, lo, hi) for lo, hi in boxes)
        far_examples.append({
            "yard": name, "actual_ST_aim_sample_index": index,
            "analytic_actor_local": actor, "analytic_target_local": target,
            "analytic_focus_local": focus, "analytic_muzzle_local": muzzle,
            "camera_and_muzzle_segments_clear": True,
            "limit": "Target XY is an actual historical ST sample; actor, focus and1.3m aim height are source-derived candidate geometry, not native VM poses.",
        })
    artifact_paths = [
        fixture_path, reference_path, observation_path,
        root / f"{EXPERIMENTS}/VE-S05-parallel-automatic-ranged-20261029-vm/automatic-012.png",
        root / f"{EXPERIMENTS}/VE-S05-parallel-automatic-ranged-20261029-vm/automatic-batches.jsonl",
        root / f"{EXPERIMENTS}/VE-S05-guarded-ranged-reference-vm/operator-028.png",
        root / f"{EXPERIMENTS}/VE-S05-hinted-bow-component-20261029-vm/component-003.png",
        root / f"{EXPERIMENTS}/VE-S05-hinted-bow-component-20261029-vm/component-controls.jsonl",
        root / f"{EXPERIMENTS}/VE-S05-hinted-bow-component-20261029-vm/game/renderer-config/settings.ron",
    ]
    return {
        "schema": "livequest-s05-conditional-public-geometry/1",
        "analysis_base": "b337c5c148c577e84a38adfb6a62e1d0669fbee4",
        "status": "conditional_source_geometry_for_independent_review_not_native_validation_or_admission",
        "new_native_or_model_episodes": 0,
        "native_source_pins": {p: digest(root / NATIVE / p) for p in SOURCE_FILES},
        "artifact_pins": {str(p.relative_to(root)): digest(p) for p in artifact_paths},
        "terrain_visibility_grid": coverage,
        "near_wall_conditional_envelopes": [near_wall_envelope(h) for h in (5, 6)],
        "far_target_native_compensation_examples": far_examples,
        "actual_ST_moving_target_samples": shots,
        "actual_ST_near_wall_sequences": near_sequences,
        "mandatory_limits": [
            "This is analytic source composition, not native execution of an outside-center stance.",
            "The envelopes assume scale1, released stationary player, grounded target and declared error/motion bounds.",
            "Gravity only reduces horizontal advance for a downward shot; air drag and target-height changes are not simulated.",
            "No historical sample establishes the conditional continuous1m/s target bound or100mm information-error budget.",
            "The support argument uses normal bounded vertical substeps, not the100-increment overflow branch.",
            "No screenshot is assigned an unrecorded camera mode, native position, grounding state or unique target UID.",
            "Original zero-shot and zero-damage/death outcomes remain unchanged; S05 remains unadmitted.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.repository_root.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output),
                      "visibility_samples": result["terrain_visibility_grid"],
                      "native_episodes": 0}))


if __name__ == "__main__":
    main()
