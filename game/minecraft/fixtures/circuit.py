"""Observe player-operated native input/output transitions without driving them."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-circuit-behavior/1"


def pack():
    sample = [
        "scoreboard players set #input lqb_circuit 0",
        "execute if block 0 72 5 lever[powered=true] run scoreboard players set #input lqb_circuit 1",
        "execute unless score #input lqb_circuit = #last lqb_circuit run scoreboard players operation #pending lqb_circuit = #input lqb_circuit",
        "execute unless score #input lqb_circuit = #last lqb_circuit run scoreboard players set #stable lqb_circuit 0",
        "scoreboard players set #correct lqb_circuit 0",
    ]
    for signal, boolean in ((0, "false"), (1, "true")):
        sample.append(
            f"execute if score #input lqb_circuit matches {signal} if block 0 72 5 lever[powered={boolean}] "
            f"if block 24 72 5 redstone_lamp[lit={boolean}] if block 24 72 7 iron_door[half=lower,open={boolean}] "
            "run scoreboard players set #correct lqb_circuit 1"
        )
    sample += [
        "execute if score #correct lqb_circuit matches 1 run scoreboard players add #stable lqb_circuit 1",
        "execute if score #correct lqb_circuit matches 0 run scoreboard players set #stable lqb_circuit 0",
        "execute if score #pending lqb_circuit matches 0..1 if score #stable lqb_circuit matches 10.. as @a run function livequest_circuit:record",
        "scoreboard players operation #last lqb_circuit = #input lqb_circuit",
    ]
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive circuit input/output evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_circuit:tick"]},
        "data/livequest_circuit/functions/tick.mcfunction":
            "execute if data storage livequest:circuit schema run function livequest_circuit:clock\n",
        "data/livequest_circuit/functions/clock.mcfunction": "\n".join([
            "execute store result score #clock lqb_circuit run time query gametime",
            "execute unless score #clock lqb_circuit = #last_clock lqb_circuit run function livequest_circuit:sample",
            "scoreboard players operation #last_clock lqb_circuit = #clock lqb_circuit",
        ]) + "\n",
        "data/livequest_circuit/functions/sample.mcfunction": "\n".join(sample) + "\n",
        "data/livequest_circuit/functions/record.mcfunction": "\n".join([
            "data modify storage livequest:circuit events append value {}",
            "data modify storage livequest:circuit events[-1].player set from entity @s UUID",
            "execute store result storage livequest:circuit events[-1].tick long 1 run time query gametime",
            "execute store result storage livequest:circuit events[-1].input int 1 run scoreboard players get #input lqb_circuit",
            "scoreboard players set #pending lqb_circuit -1",
            "scoreboard players set #last_clock lqb_circuit -1",
        ]) + "\n",
    }


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(value).hexdigest() for name, value in pack_bytes().items()}


def install_observer(world: Path):
    for name, value in pack_bytes().items():
        path = world / "datapacks/livequest_circuit" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (world / "livequest-circuit.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return [
        "scoreboard objectives add lqb_circuit dummy",
        "scoreboard players set #last lqb_circuit 0",
        "scoreboard players set #stable lqb_circuit 0",
        "scoreboard players set #pending lqb_circuit -1",
        f'data merge storage livequest:circuit {{schema:"{SCHEMA}",events:[]}}',
    ]
