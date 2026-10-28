"""Passive vanilla player-position sampling for route-transfer qualification."""

import hashlib
import json


SCHEMA = "minecraft-native-route/1"


def route_pack() -> dict[str, dict | str]:
    return {
        "pack.mcmeta": {
            "pack": {"pack_format": 26, "description": "Passive native route evidence"},
        },
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_route:tick"]},
        "data/livequest_route/functions/tick.mcfunction": "\n".join([
            "execute store result score #samples lq_route run data get storage livequest:route samples",
            "execute if score #samples lq_route matches ..89999 as @a at @s run function livequest_route:sample",
            "execute if score #samples lq_route matches 90000.. run data modify storage livequest:route overflow set value 1b",
        ]) + "\n",
        "data/livequest_route/functions/sample.mcfunction": "\n".join([
            "data modify storage livequest:route samples append value {}",
            "data modify storage livequest:route samples[-1].player set from entity @s UUID",
            "data modify storage livequest:route samples[-1].position set from entity @s Pos",
            "execute store result storage livequest:route samples[-1].tick long 1 run time query gametime",
        ]) + "\n",
    }


def pack_text(value: dict | str) -> str:
    return value if isinstance(value, str) else json.dumps(value, indent=2) + "\n"


def expected_hashes() -> dict[str, str]:
    return {name: hashlib.sha256(pack_text(value).encode()).hexdigest()
            for name, value in route_pack().items()}
