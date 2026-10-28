"""Passive vanilla inventory milestones; no gameplay or order enforcement."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-workshop-orders/1"
ORDERS = {
    1: {"cooked_beef": 2, "iron_ingot": 2},
    2: {"cooked_beef": 4, "glass": 4},
    3: {"cooked_beef": 8, "glass": 4, "iron_ingot": 2, "iron_pickaxe": 1},
    4: {"cooked_beef": 8, "glass": 8, "iron_ingot": 2, "iron_pickaxe": 1, "shield": 1},
}


def order_pack() -> dict[str, str | dict]:
    files: dict[str, str | dict] = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive workshop delivery milestones"}},
    }
    for order, items in ORDERS.items():
        files[f"data/livequest_workshop/advancements/order_{order}.json"] = {
            "criteria": {"delivery": {
                "trigger": "minecraft:inventory_changed",
                "conditions": {"items": [{"items": ["minecraft:" + item], "count": {"min": count}}
                                         for item, count in items.items()]},
            }},
            "rewards": {"function": f"livequest_workshop:order_{order}"},
        }
        files[f"data/livequest_workshop/functions/order_{order}.mcfunction"] = "\n".join([
            f"data modify storage livequest:workshop events append value {{order:{order}}}",
            "data modify storage livequest:workshop events[-1].player set from entity @s UUID",
            "execute store result storage livequest:workshop events[-1].tick long 1 run time query gametime",
        ]) + "\n"
    return files


def pack_hashes(world: Path) -> dict[str, str]:
    return {name: hashlib.sha256((world / "datapacks/livequest_workshop" / name).read_bytes()).hexdigest()
            for name in order_pack()}


def expected_hashes() -> dict[str, str]:
    return {name: hashlib.sha256(
        (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
    ).hexdigest() for name, value in order_pack().items()}
