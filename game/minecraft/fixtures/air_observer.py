"""Passive vanilla one-second air/effect samples; never controls a player."""

import hashlib
from pathlib import Path


SCHEMA = "minecraft-air-salvage/1"


def air_pack() -> dict:
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native air/effect samples"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_air:tick"]},
        "data/livequest_air/functions/tick.mcfunction": "\n".join([
            "scoreboard players add #clock lqair 1",
            "execute if score #clock lqair matches 20.. as @a run function livequest_air:sample",
            "execute if score #clock lqair matches 20.. run scoreboard players set #clock lqair 0",
        ]) + "\n",
        "data/livequest_air/functions/sample.mcfunction": "\n".join([
            "data modify storage livequest:air samples append value {active_effects:[]}",
            *[f"data modify storage livequest:air samples[-1].{key} set from entity @s {key}"
              for key in ("UUID", "Pos", "Health", "Air", "active_effects")],
            "execute store result storage livequest:air samples[-1].tick long 1 run time query gametime",
        ]) + "\n",
    }


def air_hashes(world: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((world / "datapacks/livequest_air" / name).read_bytes()).hexdigest()
        for name in air_pack()
    }
