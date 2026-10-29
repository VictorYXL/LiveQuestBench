"""Player-owned vanilla target-hit evidence; visible latches remain native redstone."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-arrow-gallery/1"
TARGETS = [(24, 73, -6), (24, 76, 3), (24, 79, 12)]


def pack():
    hit, lamps = [], ["data modify storage livequest:gallery lamps set value []"]
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive attributed target hits"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_gallery:tick"]},
        "data/livequest_gallery/advancements/hit.json": {
            "criteria": {"hit": {"trigger": "minecraft:target_hit",
                                 "conditions": {"projectile": {"type": "minecraft:arrow"}}}},
            "rewards": {"function": "livequest_gallery:hit"},
        },
    }
    for index, (x, y, z) in enumerate(TARGETS):
        for strength in range(1, 16):
            hit.append(
                f"execute if block {x} {y} {z} target[power={strength}] "
                f"unless data storage livequest:gallery hits[{{target:{index}}}] "
                f"run function livequest_gallery:record{index}"
            )
        files[f"data/livequest_gallery/functions/record{index}.mcfunction"] = "\n".join([
            f"data modify storage livequest:gallery hits append value {{target:{index}}}",
            "data modify storage livequest:gallery hits[-1].player set from entity @s UUID",
            "execute store result storage livequest:gallery hits[-1].tick long 1 run time query gametime",
        ]) + "\n"
        lamps += [
            f"execute if block 29 {y+1} {z} redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 1",
            f"execute unless block 29 {y+1} {z} redstone_lamp[lit=true] run data modify storage livequest:gallery lamps append value 0",
        ]
    hit += ["advancement revoke @s only livequest_gallery:hit"]
    files["data/livequest_gallery/functions/hit.mcfunction"] = "\n".join(hit) + "\n"
    files["data/livequest_gallery/functions/lamps.mcfunction"] = "\n".join(lamps) + "\n"
    files["data/livequest_gallery/functions/tick.mcfunction"] = (
        "execute if data storage livequest:gallery schema run function livequest_gallery:lamps\n")
    return files


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in pack_bytes().items()}


def install_observer(world: Path):
    for name, raw in pack_bytes().items():
        path = world / "datapacks/livequest_gallery" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (world / "livequest-gallery.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [f'data merge storage livequest:gallery {{schema:"{SCHEMA}",hits:[],lamps:[0,0,0]}}']
