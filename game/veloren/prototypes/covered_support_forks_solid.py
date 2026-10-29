"""Separate solid-scene candidate; preserves the measured camera-only v1."""

import argparse
import json
from pathlib import Path
import secrets

import yaml

from game.veloren.fixture import validate_fixture
from game.veloren.prototypes.covered_support_forks import build_candidate


SCENE_PROFILE = "native-solid-scene/1"
SCENE_DISCLOSURE = """
This v2 condition additionally uses native-solid-scene/1. Experimental scene
shaders, including Wireframe and debug-buffer views, are unavailable through
chat, saved preferences and pipeline changes. Ordinary solid rendering,
first/third-person viewing, the native minimap, world map and HUD remain.
This is a renderer observation restriction, not a physical-route or score rule.
"""


def build_solid_candidate(world_path: Path, seed: int) -> tuple[dict, dict]:
    task, private = build_candidate(world_path, seed)
    task["id"] = "covered_support_forks_local_solid_v2"
    task["task"] += SCENE_DISCLOSURE
    task["fixture"]["scene_observation"] = SCENE_PROFILE
    validate_fixture(task["fixture"])
    private.update({
        "schema": "covered-support-forks-local-solid/2",
        "scene_observation": SCENE_PROFILE,
        "predecessor": "covered_support_forks_local_camera_v1",
        "development_approval": (
            "Isolated candidate binding to the parent-authorized general restrictive-render "
            "repair. No canonical adoption or additional native allowance."
        ),
        "native_validation": "Not performed for v2; v1 component evidence is not relabelled.",
    })
    return task, private


def write_solid_candidate(output: Path, world_path: Path) -> Path:
    task, private = build_solid_candidate(world_path, secrets.randbits(64))
    output.mkdir(parents=True, exist_ok=False)
    task_path = output / "task.yaml"
    task_path.write_text(yaml.safe_dump(task, sort_keys=False))
    (output / "private-instance.json").write_text(json.dumps(private, indent=2) + "\n")
    (output / "public-instructions.txt").write_text(task["task"])
    return task_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(write_solid_candidate(args.output, args.world))
