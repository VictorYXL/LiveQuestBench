"""Stock-family diagnostic: deliberately does not claim hidden temporal profiles."""

import argparse
import json
from pathlib import Path
import random
import secrets

import yaml

from game.veloren.fixture import validate_fixture
from game.veloren.evaluators.encounter import validate_encounter


PUBLIC_TASK = """Defeat all four original enemies, personally damage each one, never
die and finish with at least one health within 900 seconds. The ordinary
starter sword and three minor potions are available. Enemies retain their
native attacks and autonomous movement. No reset, replenishment, compulsory
block, failed trial, order or prescribed attack pattern is required.

The two nearer stone bays have one-bar and two-bar markers; the two farther
bays repeat those markers. Within this episode a marker corresponds to the
same native enemy family in both rows, but the assignment is initially
unknown. Observe and engage through the public native interface. Using body,
name, motion, attacks and prior knowledge is legal; use your observations in
later combat if useful. Enemy identities are never redacted.

This is a stock-family engineering diagnostic, not established combat-timing
learning. There are only two family assignments. Recognizing a body or using
a generic combat policy can make learning the marker relationship unnecessary.
The public combat score does not measure learned timing or counter causality.
"""


def build_instance(world_path: Path, seed: int, track: str = "visual_motor"):
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("The private seed must be a u64")
    if track not in ("visual_motor", "structured_tool"):
        raise ValueError("Unsupported track")
    assets = ["common.entity.benchmark.male_green_legoom", "common.entity.benchmark.male_wolf"]
    random.Random(seed).shuffle(assets)
    blocks, encounters = [], []
    for row, y in (("near", 10838), ("far", 10870)):
        for marker, x in enumerate((18709, 18725)):
            blocks.extend([
                {"origin": [x - 3, y - 3, 501], "size": [1, 7, 4]},
                {"origin": [x + 3, y - 3, 501], "size": [1, 7, 4]},
                {"origin": [x - 3, y + 3, 501], "size": [7, 1, 4]},
            ])
            for bar in range(marker + 1):
                blocks.append({"origin": [x - 2 + bar * 2, y + 3, 505], "size": [1, 1, 1]})
            encounters.append({
                "role": f"{row}_marker_{marker + 1}", "asset": assets[marker],
                "position": [x + .5, y + .5, 501],
            })
    fixture = {
        "world_path": str(world_path.resolve()), "world_seed": 130626853,
        "time_of_day": "12:00", "day_length": 30, "calendar": "none",
        "platform": {"origin": [18700, 10800, 500], "size": [36, 80], "block": "Rock"},
        "blocks": blocks, "encounters": encounters,
        "player_state": {
            "position": [18717.5, 10803.5, 501], "look": [0, 1, 0],
            "health": 100, "inventory": {"common.items.consumable.potion_minor": 3},
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
    parameters = {"roles": [row["role"] for row in encounters], "no_death": True, "min_health": 1}
    validate_fixture(fixture)
    validate_encounter(**parameters)
    return {
        "id": "native_combat_family_diagnostic_v1", "game": "veloren",
        "task_type": track, "task": PUBLIC_TASK, "time_limit_seconds": 900,
        "fixture": fixture, "evaluator": {"name": "encounter", "parameters": parameters},
    }, {
        "schema": "native-combat-family-diagnostic/1", "seed": seed,
        "marker_assets": assets, "realized_mapping_count": 2,
        "qualified": False, "native_validation": "not_run",
        "hidden_temporal_profile": False,
        "policy_access": "Authoring only; not controller input.",
        "construct_gap": "Public body recognition and generic combat may dominate the marker mapping.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--track", choices=("visual_motor", "structured_tool"), default="visual_motor")
    args = parser.parse_args()
    task, private = build_instance(args.world, secrets.randbits(64), args.track)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False))
    (args.output / "private-instance.json").write_text(json.dumps(private, indent=2) + "\n")
    (args.output / "public-instructions.txt").write_text(task["task"])
