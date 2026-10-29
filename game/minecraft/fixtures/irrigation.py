"""Passive native hydration and dry-walkway stability evidence."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-irrigation-reconnection/1"
FIELDS = [(x, 72, z) for x in range(-8, -5) for z in (4, 5)] + [
    (x, 71, z) for x in range(6, 9) for z in (4, 5)]
WALKWAY = [(x, y, 8) for x in range(-12, 12) for y in (72, 73)]


def pack():
    checks = [f"if block {x} {y} {z} farmland[moisture=7]" for x, y, z in FIELDS]
    checks += [f"if block {x} {y} {z} air" for x, y, z in WALKWAY]
    checks += [f"positioned {x} {y} {z} if predicate livequest_irrigation:water_nearby"
               for x, y, z in FIELDS]
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native irrigation evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_irrigation:tick"]},
        "data/livequest_irrigation/predicates/water_nearby.json": {
            "condition": "minecraft:any_of",
            "terms": [
                {"condition": "minecraft:location_check", "offsetX": dx, "offsetY": dy, "offsetZ": dz,
                 "predicate": {"fluid": {"tag": "minecraft:water"}}}
                for dx in range(-4, 5) for dy in (0, 1) for dz in range(-4, 5)
            ],
        },
        "data/livequest_irrigation/functions/tick.mcfunction": (
            "execute if data storage livequest:irrigation schema run function livequest_irrigation:clock\n"),
        "data/livequest_irrigation/functions/clock.mcfunction": "\n".join([
            "execute store result score #clock lqb_water run time query gametime",
            "execute unless score #clock lqb_water = #last_clock lqb_water run function livequest_irrigation:sample",
            "scoreboard players operation #last_clock lqb_water = #clock lqb_water",
        ]) + "\n",
        "data/livequest_irrigation/functions/sample.mcfunction": "\n".join([
            "scoreboard players set #ready lqb_water 0",
            "execute " + " ".join(checks) + " run scoreboard players set #ready lqb_water 1",
            "execute if score #ready lqb_water matches 1 run scoreboard players add #stable lqb_water 1",
            "execute if score #ready lqb_water matches 0 run scoreboard players set #stable lqb_water 0",
            "execute store result storage livequest:irrigation stable_ticks long 1 run scoreboard players get #stable lqb_water",
        ]) + "\n",
    }


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in pack_bytes().items()}


def install_observer(world: Path):
    for name, raw in pack_bytes().items():
        path = world / "datapacks/livequest_irrigation" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (world / "livequest-irrigation.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [
        "scoreboard objectives add lqb_water dummy",
        "scoreboard players set #stable lqb_water 0",
        "scoreboard players set #last_clock lqb_water -1",
        f'data merge storage livequest:irrigation {{schema:"{SCHEMA}",stable_ticks:0L}}',
    ]
