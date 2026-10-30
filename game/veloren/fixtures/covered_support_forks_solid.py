"""Paired covered-support tasks with shared native geometry and endpoint scoring."""

import argparse
import json
from pathlib import Path
import secrets

import yaml

from game.veloren.fixture import validate_fixture
from game.veloren.fixtures.covered_support_forks import PUBLIC_TASK, build_candidate


SCENE_PROFILE = "native-solid-scene/1"
TASK_ID = "covered_support_forks"
STRUCTURED_TOOLS = (
    "MoveTool", "TurnTool", "LookTool", "JumpTool", "WallJumpTool",
    "StopTool", "GlideTool", "InspectTerrainTool", "RespawnTool",
)
SCENE_DISCLOSURE = """
The visual interface also uses native-solid-scene/1. Experimental scene
shaders, including Wireframe and debug-buffer views, are unavailable through
chat, saved preferences and pipeline changes. Ordinary solid rendering,
first/third-person viewing, the native minimap, world map and HUD remain.
This is a renderer observation restriction, not a physical-route or score rule.
"""
STRUCTURED_DISCLOSURE = """
Use the ordinary structured player observation and the listed fixed tools.
InspectTerrainTool reads actual native terrain within ten horizontal metres
and two vertical metres of your current position. It is not a global map or a
line-of-sight guarantee. Query the raised pad and nearby floor from legal
positions; no side label, hidden mapping or recommended route is supplied.
MoveTool is camera-relative, bounded and does not navigate or avoid falls.
Reobserve after turning or moving. Learning and use of the sample are optional.
"""


def build_solid_candidate(
    world_path: Path, seed: int, track: str = "visual_motor",
) -> tuple[dict, dict]:
    if track not in ("structured_tool", "visual_motor"):
        raise ValueError("Covered support requires a supported public track")
    task, private = build_candidate(world_path, seed)
    task["id"] = TASK_ID
    task["task_type"] = track
    task["capabilities"] = {
        "primary": ["within_episode_learning"],
        "secondary": ["spatial_interaction"],
    }
    if track == "visual_motor":
        task["task"] += SCENE_DISCLOSURE
        task["fixture"]["scene_observation"] = SCENE_PROFILE
    else:
        task["task"] = PUBLIC_TASK + STRUCTURED_DISCLOSURE
        task["tools"] = list(STRUCTURED_TOOLS)
        task["fixture"].pop("camera_observation")
    validate_fixture(task["fixture"])
    private.update({
        "schema": "covered-support-forks-instance/1",
        "track": track,
        "camera_observation": task["fixture"].get("camera_observation"),
        "scene_observation": task["fixture"].get("scene_observation"),
        "native_validation": "Generation is not native execution or qualification.",
    })
    private.pop("development_approval")
    return task, private


def write_solid_candidate(output: Path, world_path: Path, track: str = "visual_motor") -> Path:
    task, private = build_solid_candidate(world_path, secrets.randbits(64), track)
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
    parser.add_argument("--track", choices=("structured_tool", "visual_motor"), default="visual_motor")
    args = parser.parse_args()
    print(write_solid_candidate(args.output, args.world, args.track))
