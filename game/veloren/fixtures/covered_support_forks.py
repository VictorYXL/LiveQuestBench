"""Isolated camera-bound candidate; never modifies the canonical task registry."""

import argparse
import hashlib
import json
from pathlib import Path
import secrets

import yaml

from game.veloren.fixture import solid_voxels, validate_fixture
from game.veloren.fixtures.support_fork_proposal import build_proposal_geometry


CAMERA_PROFILE = "native-local-camera/1"
PUBLIC_TASK = """Reach the far end of the second covered gallery. Finish with at least one health, grounded and
stationary near (18738.5, 10813.5, 501), with horizontal tolerance 1.2 metres,
vertical tolerance 0.5 metres and speed at most 0.1 metres/second.

The starting chamber contains a small raised Rock pad on one side, between two
Rock cues. Seen facing forward from the starting position, this pad indicates
which relative side has a supported bridge in each of the two galleries.
The side is chosen anew for this episode. The first gallery leads away from the
starting chamber; its far exit connects around to the second gallery, which is
entered facing the opposite compass direction. Thus the same relative side is
not the same compass direction in both galleries.

Each gallery divides into two covered approaches. One has a continuous Rock
bridge; the other opens over a lower recovery floor. The two gaps have different
lengths. The sample is optional: you may inspect either approach directly,
retreat, rest, jump, glide, climb, recover from a fall or take any lawful route.
There is no required probe, mistake, checkpoint, side choice or sample visit.
The endpoint score does not check learning or the route used.

Ordinary native collision, falling, energy expenditure and recovery apply.
There is no task-time teleport, refill, reset or added protection. Native time
and resources continue during reasoning. The entire episode allows 600 seconds.
"""

CAMERA_DISCLOSURE = """
The visual interface uses native-local-camera/1: camera distance is capped
at 10 metres and its path from the actual player eye cannot cross solid or
unloaded terrain, including near-wall fallback, zoom or mode changes. Freefly
is unavailable. If a safe local world view cannot be established, the world is
withheld rather than showing through walls; the ordinary HUD remains available.
First/third-person viewing, the native voxel minimap and world map remain legal.

"""


def build_candidate(world_path: Path, seed: int) -> tuple[dict, dict]:
    fixture, proposal = build_proposal_geometry(world_path, seed)
    fixture["camera_observation"] = CAMERA_PROFILE
    validate_fixture(fixture)
    task = {
        "id": "covered_support_forks_local_camera_v1",
        "game": "veloren",
        "task_type": "visual_motor",
        "task": PUBLIC_TASK + CAMERA_DISCLOSURE,
        "time_limit_seconds": 600,
        "fixture": fixture,
        "evaluator": {"name": "state", "parameters": {
            "min_health": 1,
            "position": {
                "target": proposal["proposed_endpoint"],
                "horizontal_tolerance": 1.2,
                "vertical_tolerance": .5,
                "max_speed": .1,
            },
        }},
    }
    voxel_bytes = json.dumps(sorted(solid_voxels(fixture)), separators=(",", ":")).encode()
    private = {
        "schema": "covered-support-forks-local-camera/1",
        "seed": seed,
        "side": proposal["side"],
        "realized_mapping_count": 2,
        "authored_voxels": proposal["authored_voxels"],
        "geometry_sha256": hashlib.sha256(voxel_bytes).hexdigest(),
        "source_proposal": proposal,
        "camera_observation": CAMERA_PROFILE,
        "route_observation": None,
        "development_approval": "Parent22:07 isolated development; not canonical adoption.",
        "qualification": False,
        "learning_benefit": "not_measured",
        "policy_access": "Author/scorer only. Never provide this manifest or fixture to a policy.",
    }
    return task, private


def write_candidate(output: Path, world_path: Path) -> Path:
    task, private = build_candidate(world_path, secrets.randbits(64))
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
    print(write_candidate(args.output, args.world))
