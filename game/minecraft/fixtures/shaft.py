"""Passive native upper-landing visit, not a movement or construction controller."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-service-shaft/1"


def pack():
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive shaft ascent witness"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_shaft:tick"]},
        "data/livequest_shaft/predicates/upper.json": {
            "condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"position": {
                "x": {"min": 3, "max": 13}, "y": {"min": 69, "max": 71}, "z": {"min": 3, "max": 7},
            }}},
        },
        "data/livequest_shaft/functions/tick.mcfunction": (
            "execute if data storage livequest:shaft schema as @a[tag=!lqb_shaft_upper] "
            "at @s if predicate livequest_shaft:upper run function livequest_shaft:upper\n"
        ),
        "data/livequest_shaft/functions/upper.mcfunction": "\n".join([
            "data modify storage livequest:shaft visits append value {}",
            "data modify storage livequest:shaft visits[-1].player set from entity @s UUID",
            "execute store result storage livequest:shaft visits[-1].tick long 1 run time query gametime",
            "tag @s add lqb_shaft_upper",
        ]) + "\n",
    }


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in pack_bytes().items()}


def install_observer(world: Path):
    for name, raw in pack_bytes().items():
        path = world / "datapacks/livequest_shaft" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (world / "livequest-shaft.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [f'data merge storage livequest:shaft {{schema:"{SCHEMA}",visits:[]}}']
