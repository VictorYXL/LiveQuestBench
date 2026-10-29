"""Author a private real-Rock aperture assignment without a hidden scoring rule."""

import argparse
import json
from pathlib import Path
import random
import secrets

import yaml

from game.veloren.fixture import validate_fixture
from game.veloren.evaluators.encounter import validate_encounter


PUBLIC_TASK = """Defeat both original Green Legooms inside the two marked shooting structures.
Deal actual damage to each original enemy, never die, and finish with at least one
health. The ordinary starter bow, retained starter sword and native controls are
available. The continuous episode allows 900 seconds; there are no resets,
replacement enemies, refills or added protection.

Both structures have the same double-bar cue. Each has three one-metre-square
front slots, centred at x=18709.5, 18712.5 and 18715.5, z=502.5.
Their front faces are y=10810 and y=10832; each structure extends 15 metres back.
Exterior walking lanes at x=18702.5 and x=18725.5 connect both fronts;
their floor is z=501. Approach space extends four metres before each front.
The platform has ordinary two-metre-high Rock perimeter walls.
They reduce accidental walk-offs; climbing or leaving them remains legal.
Four metres behind each front, one opening in a second Rock baffle admits
one of the three front approaches. Which approach connects is initially
unknown, but identical in both structures during this episode.
Closed roofs, walls and narrow slots are actual native collision geometry,
not restrictions on allowed actions. Native projectile collision determines
which trajectories can pass; targets retain ordinary movement.
Target placement and the inner target cells are independent of this assignment.
Targets start more than 32 metres away. Their later public positions remain
truthful and can be used for aiming, but do not encode the assigned opening.
Each inner cell has a broad, one-metre-high front aperture that narrows behind
the entrance. The cell is intended to limit movement after impact; native AI, health, attacks
and projectile physics are unchanged. This is a ballistic-path task, not a
claim that a constrained target measures unrestricted target-leading skill.
Use lawful viewing, aiming, shots, impacts and combat feedback to investigate
and apply useful findings. Neither target is a compulsory practice stage;
application-stage probes and direct inspection are legitimate.

There is no required miss, trial count, shot budget, order or prescribed route.
The native enemies remain autonomous and can move. Walking, climbing, rolling, fresh inspection
and other legal combat solutions are allowed. Killing the enemies establishes
only the public combat goal, not learning or a projectile-specific strategy.
A learning claim requires separate same-episode history counterpolicies on
fresh hidden assignments, including robust inspection and close-combat controls.
"""


def build_instance(world_path: Path, seed: int, track: str = "visual_motor") -> tuple[dict, dict]:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("The private instance seed must be a u64")
    if track not in ("visual_motor", "structured_tool"):
        raise ValueError("Unsupported track")
    rng = random.Random(seed)
    open_slot = rng.randrange(3)
    blocks, encounters = [], []

    def box(x, y, z, width, depth, height):
        blocks.append({"origin": [x, y, z], "size": [width, depth, height]})

    box(18700, 10780, 501, 28, 1, 2)
    box(18700, 10851, 501, 28, 1, 2)
    box(18700, 10781, 501, 1, 70, 2)
    box(18727, 10781, 501, 1, 70, 2)
    slots = (18709, 18712, 18715)
    rear_windows = ((18710, 18711), (18712,), (18713, 18714))
    for role, front in (("practice_legoom", 10810), ("application_legoom", 10832)):
        for y in (front, front + 4):
            for x in range(18704, 18724):
                for z in range(501, 506):
                    openings = slots if y == front else rear_windows[open_slot]
                    if x in openings and z == 502:
                        continue
                    box(x, y, z, 1, 1, 1)
        box(18704, front, 501, 1, 15, 5)
        box(18723, front, 501, 1, 15, 5)
        box(18704, front + 14, 501, 20, 1, 5)
        box(18704, front, 506, 20, 15, 1)
        box(18705, front + 5, 501, 18, 9, 1)
        for x in (18711, 18713):
            box(x, front - 1, 505, 1, 1, 1)
        target_x = 18712
        for x in (target_x - 1, target_x + 1):
            box(x, front + 10, 502, 1, 4, 3)
        box(target_x - 1, front + 13, 502, 3, 1, 3)
        box(target_x - 1, front + 9, 505, 3, 5, 1)
        box(target_x - 1, front + 9, 503, 3, 1, 2)
        encounters.append({
            "role": role, "asset": "common.entity.benchmark.male_green_legoom",
            "position": [target_x + .5, front + 10.5, 502],
        })
    fixture = {
        "world_path": str(world_path.resolve()), "world_seed": 130626853,
        "time_of_day": "12:00", "day_length": 30, "calendar": "none",
        "platform": {"origin": [18700, 10780, 500], "size": [28, 72], "block": "Rock"},
        "blocks": blocks, "encounters": encounters,
        "player_state": {
            "position": [18712.5, 10783.5, 501], "look": [0, 1, 0],
            "health": 100, "inventory": {"common.items.weapons.sword.starter": 1},
            "equipment": {
                "active_mainhand": "common.items.weapons.bow.starter",
                "chest": "common.items.armor.misc.chest.worker_purple_brown",
                "feet": "common.items.armor.misc.foot.sandals",
                "legs": "common.items.armor.misc.pants.worker_brown",
                "glider": "common.items.glider.basic_white",
                "lantern": "common.items.lantern.black_0",
            },
        },
    }
    parameters = {"roles": [row["role"] for row in encounters], "no_death": True, "min_health": 1}
    validate_fixture(fixture)
    validate_encounter(**parameters)
    task = {
        "id": "hidden_ballistic_aperture_prototype_v7", "game": "veloren",
        "task_type": track, "task": PUBLIC_TASK, "time_limit_seconds": 900,
        "fixture": fixture, "evaluator": {"name": "encounter", "parameters": parameters},
    }
    private = {
        "schema": "hidden-native-ballistic-aperture/7", "seed": seed,
        "open_slot": open_slot, "realized_mapping_count": 3,
        "qualification": False, "native_validation": "not_run",
        "version_scope": "Keep v5 target-independent apertures; add real climbable perimeter walls after v6's native update pulse caused a walk-off. Three actual assignments. Changed physical fall risk is not unchanged difficulty or learning qualification.",
        "policy_access": "Authoring audit only; never supply this manifest or fixture to a policy.",
    }
    return task, private


def write_instance(output: Path, world_path: Path, track: str = "visual_motor") -> Path:
    task, private = build_instance(world_path, secrets.randbits(64), track)
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
    parser.add_argument("--track", choices=("visual_motor", "structured_tool"), default="visual_motor")
    args = parser.parse_args()
    print(write_instance(args.output, args.world, args.track))
