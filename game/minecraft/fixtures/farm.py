"""Native parent-bound breeding event and surviving offspring identities."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-farm-breeding/1"


def farm_pack():
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native farm breeding evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_farm:tick"]},
        "data/livequest_farm/advancements/breed.json": {
            "criteria": {"offspring": {
                "trigger": "minecraft:bred_animals",
                "conditions": {
                    "parent": {"type": "minecraft:sheep", "nbt": '{Tags:["lqb_parent_a"]}'},
                    "partner": {"type": "minecraft:sheep", "nbt": '{Tags:["lqb_parent_b"]}'},
                    "child": {"type": "minecraft:sheep"},
                },
            }},
            "rewards": {"function": "livequest_farm:breed"},
        },
        "data/livequest_farm/functions/breed.mcfunction": "\n".join([
            "data modify storage livequest:farm events append value {children:[]}",
            "data modify storage livequest:farm events[-1].player set from entity @s UUID",
            "execute store result storage livequest:farm events[-1].tick long 1 run time query gametime",
            # Vanilla fires the criterion before inserting the newborn into the world.
            "tag @e[type=sheep] add lqb_farm_prebirth",
            "schedule function livequest_farm:collect_child 1t replace",
            "advancement revoke @s only livequest_farm:breed",
        ]) + "\n",
        "data/livequest_farm/functions/collect_child.mcfunction": "\n".join([
            "execute store result storage livequest:farm events[-1].captured_tick long 1 run time query gametime",
            "execute at @e[type=sheep,tag=lqb_parent_a,limit=1] as @e[type=sheep,tag=!lqb_farm_prebirth,distance=..4] run function livequest_farm:candidate",
        ]) + "\n",
        "data/livequest_farm/functions/candidate.mcfunction": "\n".join([
            "execute store result score @s lqb_farm_age run data get entity @s Age",
            "execute if score @s lqb_farm_age matches -24000..-23998 run data modify storage livequest:farm events[-1].children append from entity @s UUID",
            "execute if score @s lqb_farm_age matches -24000..-23998 run tag @s add lqb_farm_child",
        ]) + "\n",
        "data/livequest_farm/functions/tick.mcfunction": "\n".join([
            "execute if data storage livequest:farm schema run data modify storage livequest:farm alive set value []",
            "execute if data storage livequest:farm schema as @e[type=sheep,tag=lqb_farm_child,nbt=!{Health:0.0f}] run data modify storage livequest:farm alive append from entity @s UUID",
        ]) + "\n",
    }


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in farm_pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(value).hexdigest() for name, value in pack_bytes().items()}


def install_observer(world: Path):
    for name, raw in pack_bytes().items():
        target = world / "datapacks/livequest_farm" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (world / "livequest-farm.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [
        "scoreboard objectives add lqb_farm_age dummy",
        f'data merge storage livequest:farm {{schema:"{SCHEMA}",events:[],alive:[]}}',
    ]
