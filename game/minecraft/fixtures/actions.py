"""Passive action evidence retained independently of retired workshop authors."""

import hashlib
from pathlib import Path


ACTION_SCHEMA = "minecraft-action-sequence/1"


def action_pack() -> dict[str, str | dict]:
    files: dict[str, str | dict] = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native block and damage ordering"}},
    }
    for kind, trigger, conditions in (
        ("block", "entity_hurt_player", {"damage": {"blocked": True, "type": {
            "direct_entity": {"type": "minecraft:husk"},
        }}}),
        ("damage", "player_hurt_entity", {"damage": {"taken": {"min": 0.1}}, "entity": {"type": "minecraft:husk"}}),
    ):
        files[f"data/livequest_actions/advancements/{kind}.json"] = {
            "criteria": {"effect": {"trigger": "minecraft:" + trigger, "conditions": conditions}},
            "rewards": {"function": "livequest_actions:" + kind},
        }
        files[f"data/livequest_actions/functions/{kind}.mcfunction"] = "\n".join([
            f'data modify storage livequest:actions events append value {{kind:"{kind}"}}',
            "data modify storage livequest:actions events[-1].player set from entity @s UUID",
            "execute store result storage livequest:actions events[-1].tick long 1 run time query gametime",
            f"advancement revoke @s only livequest_actions:{kind}",
        ]) + "\n"
    return files


def action_hashes(world: Path) -> dict[str, str]:
    return {name: hashlib.sha256((world / "datapacks/livequest_actions" / name).read_bytes()).hexdigest()
            for name in action_pack()}
