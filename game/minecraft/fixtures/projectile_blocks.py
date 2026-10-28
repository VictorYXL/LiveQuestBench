"""Passive vanilla advancement evidence for skeleton arrows blocked by a shield."""

import hashlib
from pathlib import Path


SCHEMA = "minecraft-skeleton-projectile-blocks/1"


def projectile_pack() -> dict[str, str | dict]:
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive skeleton projectile blocks"}},
        "data/livequest_shield/advancements/block.json": {
            "criteria": {"block": {"trigger": "minecraft:entity_hurt_player", "conditions": {
                "damage": {"blocked": True, "type": {
                    "direct_entity": {"type": "minecraft:arrow"},
                    "source_entity": {"type": "minecraft:skeleton"},
                }},
            }}},
            "rewards": {"function": "livequest_shield:block"},
        },
        "data/livequest_shield/functions/block.mcfunction": "\n".join([
            'data modify storage livequest:shield events append value {kind:"skeleton_arrow_block"}',
            "data modify storage livequest:shield events[-1].player set from entity @s UUID",
            "execute store result storage livequest:shield events[-1].tick long 1 run time query gametime",
            "advancement revoke @s only livequest_shield:block",
        ]) + "\n",
    }


def projectile_hashes(world: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((world / "datapacks/livequest_shield" / name).read_bytes()).hexdigest()
        for name in projectile_pack()
    }
