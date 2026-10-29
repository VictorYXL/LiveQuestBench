"""Passive, versioned final-repair witnesses; the original observer is unchanged."""

import hashlib
import json
from pathlib import Path

SCHEMA = "minecraft-circuit-feedback/3"
STABLE_TICKS = 100
NAMESPACE = "livequest_feedback"


def mined_blocks():
    return json.loads(Path(__file__).with_name("circuit_feedback_blocks.json").read_text())["identifiers"]


def pack():
    commands = {}

    def function(name, lines):
        commands[f"data/{NAMESPACE}/functions/{name}.mcfunction"] = "\n".join(lines) + "\n"

    function("initialize", [
        "scoreboard objectives add lqf dummy",
        *[f"scoreboard objectives add lqfm{i} minecraft.mined:minecraft.{block}"
          for i, block in enumerate(mined_blocks())],
        "scoreboard players set #last lqf 0",
        "scoreboard players set #stable lqf 0",
        "scoreboard players set #pending lqf -1",
        f'data merge storage livequest:feedback {{schema:"{SCHEMA}",events:[],edits:[]}}',
    ])
    function("tick", [
        "execute if data storage livequest:feedback schema run function livequest_feedback:clock",
    ])
    function("clock", [
        "execute store result score #clock lqf run time query gametime",
        "execute unless score #clock lqf = #last_clock lqf run function livequest_feedback:sample",
        "scoreboard players operation #last_clock lqf = #clock lqf",
    ])
    sample = [
        "scoreboard players set #input lqf 0",
        "execute if block 0 72 5 lever[powered=true] run scoreboard players set #input lqf 1",
        "execute unless score #input lqf = #last lqf run scoreboard players operation #pending lqf = #input lqf",
        "execute unless score #input lqf = #last lqf run scoreboard players set #stable lqf 0",
        "scoreboard players set #correct lqf 0",
    ]
    for mode, boolean in ((0, "false"), (1, "true")):
        sample.append(
            f"execute if score #input lqf matches {mode} "
            f"if block 0 72 5 lever[powered={boolean}] "
            f"if block 24 72 5 redstone_lamp[lit={boolean}] "
            f"if block 24 72 7 iron_door[half=lower,open={boolean}] "
            "run scoreboard players set #correct lqf 1"
        )
    sample += [
        "execute if score #correct lqf matches 0 run scoreboard players set #stable lqf 0",
        "execute if score #correct lqf matches 1 run scoreboard players add #stable lqf 1",
        "execute if score #pending lqf matches 0..1 if score #stable lqf matches 1 as @a run function livequest_feedback:start",
        f"execute if score #pending lqf matches 0..1 if score #stable lqf matches {STABLE_TICKS}.. as @a run function livequest_feedback:finish",
        "scoreboard players operation #last lqf = #input lqf",
    ]
    function("sample", sample)
    function("count_mined", [
        "scoreboard players set #mined lqf 0",
        *[f"execute if score @s lqfm{i} matches 0.. run scoreboard players operation #mined lqf += @s lqfm{i}"
          for i, _block in enumerate(mined_blocks())],
    ])
    function("start", [
        "function livequest_feedback:count_mined",
        "scoreboard players operation #start_mined lqf = #mined lqf",
        "execute store result score #start_tick lqf run time query gametime",
    ])
    function("finish", [
        "function livequest_feedback:count_mined",
        "execute if score #mined lqf = #start_mined lqf run function livequest_feedback:record",
        "execute unless score #mined lqf = #start_mined lqf run scoreboard players set #stable lqf 0",
    ])
    function("record", [
        "data modify storage livequest:feedback events append value {}",
        "data modify storage livequest:feedback events[-1].player set from entity @s UUID",
        "execute store result storage livequest:feedback events[-1].tick long 1 run time query gametime",
        "execute store result storage livequest:feedback events[-1].start_tick long 1 run scoreboard players get #start_tick lqf",
        "execute store result storage livequest:feedback events[-1].input int 1 run scoreboard players get #input lqf",
        "execute store result storage livequest:feedback events[-1].mined int 1 run scoreboard players get #mined lqf",
        "execute store result storage livequest:feedback events[-1].edits int 1 run data get storage livequest:feedback edits",
        "scoreboard players set #pending lqf -1",
    ])
    function("edit", [
        "data modify storage livequest:feedback edits append value {}",
        "data modify storage livequest:feedback edits[-1].player set from entity @s UUID",
        "execute store result storage livequest:feedback edits[-1].tick long 1 run time query gametime",
        "scoreboard players set #stable lqf 0",
    ])
    for name in ("placed", "interacted"):
        function(name, [
            f"advancement revoke @s only livequest_feedback:{name}",
            "execute if data storage livequest:feedback schema run function livequest_feedback:edit",
        ])
    commands.update({
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive final-repair circuit witnesses"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_feedback:tick"]},
        "data/livequest_feedback/advancements/placed.json": {
            "criteria": {"placed": {"trigger": "minecraft:placed_block"}},
            "rewards": {"function": "livequest_feedback:placed"},
        },
        "data/livequest_feedback/advancements/interacted.json": {
            "criteria": {"interacted": {
                "trigger": "minecraft:item_used_on_block",
                "conditions": {"location": [{
                    "condition": "minecraft:inverted",
                    "term": {"condition": "minecraft:location_check", "predicate": {
                        "position": {"x": {"min": 0, "max": .999999}, "y": {"min": 72, "max": 72.999999},
                                     "z": {"min": 5, "max": 5.999999}},
                        "block": {"blocks": ["minecraft:lever"]},
                    }},
                }]},
            }},
            "rewards": {"function": "livequest_feedback:interacted"},
        },
    })
    return commands


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(value).hexdigest() for name, value in pack_bytes().items()}


def install_observer(world):
    for name, value in pack_bytes().items():
        path = world / "datapacks" / NAMESPACE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (world / "livequest-feedback.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    return ["function livequest_feedback:initialize"]
