"""Optional passive samples of native skeleton AI targets."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-native-target-trace/1"
PACK = "livequest_targets"
FILES = {
    "pack.mcmeta": json.dumps({"pack": {"pack_format": 26, "description": "Passive native AI targets"}}),
    "data/minecraft/tags/functions/tick.json": json.dumps({"values": ["livequest_targets:tick"]}),
    "data/livequest_targets/functions/tick.mcfunction": "\n".join([
        "execute store result score #now lqtarget run time query gametime",
        "scoreboard players operation #elapsed lqtarget = #now lqtarget",
        "scoreboard players operation #elapsed lqtarget -= #last lqtarget",
        "execute if score #elapsed lqtarget matches 20.. run function livequest_targets:sample",
    ]) + "\n",
    "data/livequest_targets/functions/sample.mcfunction": "\n".join([
        "data modify storage livequest:targets frames append value {enemies:[]}",
        "execute store result storage livequest:targets frames[-1].tick long 1 run time query gametime",
        "execute as @e[type=minecraft:skeleton] run function livequest_targets:enemy",
        "scoreboard players operation #last lqtarget = #now lqtarget",
    ]) + "\n",
    "data/livequest_targets/functions/enemy.mcfunction": "\n".join([
        "data modify storage livequest:targets current set value {target_is_player:0b}",
        "data modify storage livequest:targets current.enemy set from entity @s UUID",
        "execute on target run data modify storage livequest:targets current.target set from entity @s UUID",
        "execute on target if entity @s[type=minecraft:player] run data modify storage livequest:targets current.target_is_player set value 1b",
        "data modify storage livequest:targets frames[-1].enemies append from storage livequest:targets current",
    ]) + "\n",
}
INITIAL_COMMANDS = [
    "scoreboard objectives add lqtarget dummy",
    "execute store result score #last lqtarget run time query gametime",
    f'data merge storage livequest:targets {{schema:"{SCHEMA}",frames:[]}}',
]


def target_hashes(world: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((world / "datapacks" / PACK / name).read_bytes()).hexdigest()
        for name in FILES
    }


def prepare_target_trace(world: Path) -> None:
    for name, content in FILES.items():
        path = world / "datapacks" / PACK / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (world / "livequest-target-trace.json").write_text(json.dumps({
        "schema": SCHEMA, "sample_interval_ticks": 20,
        "pack_sha256": target_hashes(world),
    }, indent=2) + "\n")
