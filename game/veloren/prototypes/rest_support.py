"""Generate a private physical support mapping with a mapping-independent public goal."""

import argparse
import json
from pathlib import Path
import random
import secrets

import yaml

from game.veloren.fixture import solid_voxels, validate_fixture


PUBLIC_TASK = """Finish with at least one health, stationary and grounded inside either upper recess of the
second marked wall. The two walls are directly ahead of the start, one behind the
other. The final recesses are five metres above the floor; stand well inside, not
on their entrance sill. The final goal is centred at (18710.5, 10822.5, 506),
with horizontal tolerance 1.2 metres and vertical tolerance 0.5 metres.

Both walls have the same double-bar marker. Within this episode, their interior
ground-support shelf is on the same side, but that side is initially unknown.
The other recess lacks the shallow interior shelf. This is actual native rock
geometry, not a rule penalising a wrong guess. You may explore the first wall
and apply its feedback to the second, or use another lawful solution.

Use ordinary viewing, movement, jumping and climbing. Native collision, falling,
energy expenditure and recovery supply the feedback. Look inside from a lawful
position if useful. There is no required failed attempt, number of trials, rest
duration, route or side. The floor permits ordinary recovery after a short fall; its two-metre-high
perimeter wall limits accidental walk-offs but can be climbed normally.
there is no teleport, refill, reset or added protection. Native time and resources
continue during reasoning. The whole episode allows 600 seconds.

This is an isolated mechanism prototype. Its endpoint score measures only the
public final position, grounding, speed and survival, not learning or practice
completion. A learning claim additionally needs a recorded same-episode discovery
and application contrast against history-free or mismatched-history policies.
"""


def build_instance(world_path: Path, seed: int) -> tuple[dict, dict]:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("The private instance seed must be a u64")
    side = random.Random(seed).choice(("left", "right"))
    blocks = []

    def box(x, y, z, width, depth, height):
        blocks.append({"origin": [x, y, z], "size": [width, depth, height]})

    box(18700, 10800, 501, 20, 1, 2)
    box(18700, 10829, 501, 20, 1, 2)
    box(18700, 10800, 501, 1, 30, 2)
    box(18719, 10800, 501, 1, 30, 2)
    for front in (10808, 10820):
        box(18707, front, 501, 7, 1, 5)
        box(18707, front, 509, 7, 1, 2)
        for x in (18707, 18710, 18713):
            box(x, front, 501, 1, 5, 10)
        box(18707, front + 4, 501, 7, 1, 5)
        box(18707, front + 4, 506, 7, 1, 5)
        box(18708 if side == "left" else 18711, front + 1, 505, 2, 3, 1)
        for x in (18707, 18713):
            box(x, front - 1, 504, 1, 1, 1)
    fixture = {
        "world_path": str(world_path.resolve()), "world_seed": 130626853,
        "time_of_day": "12:00", "day_length": 30, "calendar": "none",
        "public_energy": True,
        "platform": {"origin": [18700, 10800, 500], "size": [20, 30], "block": "Rock"},
        "blocks": blocks,
        "player_state": {
            "position": [18710.5, 10803.5, 501], "look": [0, 1, 0],
            "health": 100, "inventory": {},
            "equipment": {
                "active_mainhand": "common.items.weapons.sword.starter",
                "chest": "common.items.armor.misc.chest.worker_purple_brown",
                "feet": "common.items.armor.misc.foot.sandals",
                "legs": "common.items.armor.misc.pants.worker_brown",
                "glider": "common.items.glider.basic_white",
                "lantern": "common.items.lantern.black_0",
            },
        },
    }
    validate_fixture(fixture)
    task = {
        "id": "hidden_rest_support_prototype_v4", "game": "veloren",
        "task_type": "visual_motor", "task": PUBLIC_TASK, "time_limit_seconds": 600,
        "fixture": fixture,
        "evaluator": {"name": "state", "parameters": {
            "min_health": 1,
            "position": {"target": [18710.5, 10822.5, 506],
                         "horizontal_tolerance": 1.2, "vertical_tolerance": 0.5,
                         "max_speed": 0.1},
        }},
    }
    private = {
        "schema": "hidden-native-rest-support/4", "seed": seed,
        "shelf_side": side, "realized_mapping_count": 2,
        "authored_voxels": len(solid_voxels(fixture)),
        "qualification": False, "learning_benefit": "not_estimated",
        "version_scope": "Publish a fully interior endpoint tolerance excluding common-sill overhang; add real perimeter walls after observed walk-off. Route observer remains disabled.",
        "policy_access": "Authoring/scorer audit only; never supply this manifest or fixture to a policy.",
    }
    return task, private


def write_instance(output: Path, world_path: Path) -> Path:
    task, private = build_instance(world_path, secrets.randbits(64))
    output.mkdir(parents=True, exist_ok=False)
    path = output / "task.yaml"
    path.write_text(yaml.safe_dump(task, sort_keys=False))
    (output / "private-instance.json").write_text(json.dumps(private, indent=2) + "\n")
    (output / "public-instructions.txt").write_text(task["task"])
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(write_instance(arguments.output, arguments.world))
