"""Passive entry events for the three native quarry interiors."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-quarry-visits/1"
SITES = [(32, 6), (-28, 12), (6, 35)]


def pack_bytes():
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive quarry entry evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_quarry:tick"]},
    }
    tick = []
    for index, (x, z) in enumerate(SITES):
        files[f"data/livequest_quarry/predicates/site{index}.json"] = {
            "condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"position": {
                "x": {"min": x, "max": x + 3}, "y": {"min": 72, "max": 75},
                "z": {"min": z, "max": z + 4},
            }}},
        }
        tick += [
            f"execute as @a at @s unless predicate livequest_quarry:site{index} run tag @s remove lqb_quarry_{index}",
            f"execute as @a[tag=!lqb_quarry_{index}] at @s if predicate livequest_quarry:site{index} run function livequest_quarry:enter{index}",
        ]
        files[f"data/livequest_quarry/functions/enter{index}.mcfunction"] = "\n".join([
            f"data modify storage livequest:quarry visits append value {{site:{index}}}",
            "data modify storage livequest:quarry visits[-1].player set from entity @s UUID",
            "execute store result storage livequest:quarry visits[-1].tick long 1 run time query gametime",
            f"tag @s add lqb_quarry_{index}",
        ]) + "\n"
    files["data/livequest_quarry/functions/sample.mcfunction"] = "\n".join(tick) + "\n"
    files["data/livequest_quarry/functions/tick.mcfunction"] = (
        "execute if data storage livequest:quarry schema run function livequest_quarry:sample\n")
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in files.items()}


def expected_hashes():
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in pack_bytes().items()}


def install_observer(world: Path):
    for name, raw in pack_bytes().items():
        path = world / "datapacks/livequest_quarry" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (world / "livequest-quarry.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [f'data merge storage livequest:quarry {{schema:"{SCHEMA}",visits:[]}}']
