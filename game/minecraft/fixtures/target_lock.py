"""Vanilla analog comparator locks; all gameplay effects are native circuitry."""
import json
import math
from pathlib import Path
import re

from game.minecraft.fixtures.archery_evidence import install as install_archery


def diode_command(command):
    # Native diode FACING identifies its input; circuit coordinates describe signal flow.
    opposite = {"north": "south", "south": "north", "east": "west", "west": "east"}
    return re.sub(r"\b(repeater|comparator)\[facing=(north|south|east|west)",
                  lambda match: f"{match[1]}[facing={opposite[match[2]]}", command)


def signal_hopper(strength):
    total = max(1, math.ceil((strength - 1) * 320 / 14))
    items = []
    for slot in range(5):
        count = min(64, total)
        if count:
            items.append(f'{{Slot:{slot}b,id:"minecraft:paper",Count:{count}b}}')
        total -= count
    return "hopper{Items:[" + ",".join(items) + "]}"


def circuit(x0, y, z0, lower):
    blocks = {}

    def put(x, z, value, height=None):
        height = y if height is None else height
        blocks[(x0+x, height-1, z0+z)] = "bedrock"
        blocks[(x0+x, height, z0+z)] = value

    put(0, 0, "stone_bricks")
    for x in range(1, 10):
        put(x, 0, "comparator[facing=east]")
        put(x, 2, "comparator[facing=east]")
    put(0, 1, "comparator[facing=south]")
    put(0, 2, "stone_bricks")
    put(9, -1, "comparator[facing=south]")
    put(9, -2, signal_hopper(lower))
    put(9, 3, "comparator[facing=north]")
    put(9, 4, signal_hopper(lower+4))
    put(10, 0, "repeater[facing=east]")
    put(11, 0, "stone_bricks")
    put(12, 0, "redstone_wall_torch[facing=east]")
    put(10, 2, "repeater[facing=east]")
    for x in (11, 12):
        put(x, 2, "redstone_wire")
    for z in range(3):
        put(13, z, "redstone_wire")
    # Isolate both OR inputs: otherwise the resting !lower signal backfeeds the
    # high feedback counter. Matched diode delays also avoid an accepted glitch.
    put(12, 2, "repeater[facing=east]")
    put(13, 0, "repeater[facing=east]")
    put(13, 1, "air")
    for z in range(3):
        put(14, z, "redstone_wire")
    put(15, 1, "redstone_wire")
    put(16, 1, "stone_bricks")
    put(17, 1, "redstone_wall_torch[facing=east]")
    for x in range(18, 21):
        put(x, 1, "redstone_wire")
    put(18, 1, "repeater[facing=east]")
    for z in range(2, 9):
        put(20, z, "repeater[facing=south]" if z == 6 else "redstone_wire")
    for z in range(3, 6):
        put(11, z, "redstone_wire")

    # Equal native propagation delays avoid inventing a low hit at rest.
    for z in range(-1, -8, -1):
        put(0, z, "repeater[facing=north,delay=4]" if z in (-1, -4) else "redstone_wire")
    for x in range(1, 7):
        put(x, -7, "repeater[facing=east,delay=3]" if x == 3 else "redstone_wire")
    for z in (-6, -5):
        put(6, z, "redstone_wire")
    put(5, -5, "repeater[facing=west]")
    put(4, -5, "comparator[facing=west,mode=subtract]")
    put(11, -1, "repeater[facing=north]")
    for z in (-2, -3):
        put(11, z, "redstone_wire")
    for x in range(4, 11):
        put(x, -3, "redstone_wire")
    put(4, -4, "repeater[facing=north]")

    for z, start, category in ((-5, 3, "low"), (5, 10, "high"), (8, 19, "accepted")):
        height = y
        for x in range(start, 25-x0, -1):
            absolute = x0+x
            if category == "low" and x in (2, 1, 0):
                height -= 1
            if 30 <= absolute <= 35:
                height += (height < 73) - (height > 73)
            level_step = (category == "low" and x in (3, 2, 1, 0)) or 29 <= absolute <= 36
            relay = absolute == 38 or (not level_step and absolute % 12 == 0)
            put(x, z, "repeater[facing=west]" if relay else "redstone_wire", height)
            blocks[(absolute, height+1, z0+z)] = "air"
        put(26-x0, z, "repeater[facing=west]", 73)
        token = f'{{livequest_token:"target_{1 if z0 == 0 else 2}"}}' if category == "accepted" else "{}"
        count = 1 if category == "accepted" else 64
        # Original supplies stay beyond native reach even if the public chest
        # is broken through its one-block-high aperture.
        put(25-x0, z, 'dropper[facing=west]{Items:[{Slot:0b,id:"minecraft:paper",Count:'
            + str(count) + 'b,tag:' + token + '}]}' , 73)
        for x in range(18, 25):
            put(x-x0, z, "hopper[facing=west]", 73)
        put(17-x0, z, "chest", 73)
        put(17-x0, z+1, "comparator[facing=south]", 73)
        put(17-x0, z+2, "stone_bricks", 73)
        blocks[(17, 74, z0+z+2)] = "redstone_lamp"
    return blocks


def public_manifest():
    return {
        "kind": "native_hidden_analog_lock_prototype",
        "targets": [
            {"position": [18, 73, 0], "nominal_aim": [18.5, 74.4, .5],
             "feedback_chests": {"low": [17, 73, -5], "high": [17, 73, 5], "accepted": [17, 73, 8]}},
            {"position": [28, 77, 0], "nominal_aim": [28.5, 79.75, .5],
             "feedback_chests": {"low": [17, 73, 15], "high": [17, 73, 25], "accepted": [17, 73, 28]}},
        ],
        "mechanism": "One shared unknown four-strength native comparator window. Native low/high counters retain outcome history; an accepted pulse releases the original token into the accepted chest.",
        "feedback": "Count differences, not old nonempty counters, identify the latest hit. Misses release nothing.",
        "goal": "Retrieve both original released tokens and return alive to the starting marker.",
        "budgets": {"practice_arrows": 24, "application_arrows": 12},
        "limits": "Application-only mechanism proof; optional practice station and full phase accounting are not yet implemented.",
    }


def install(world: Path):
    install_archery(world)
    root = world / "datapacks/livequest_lock"
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native lock delivery evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_lock:tick"]},
        "data/minecraft/tags/functions/load.json": {"values": ["livequest_lock:load"]},
        "data/livequest_lock/functions/load.mcfunction": "scoreboard objectives add lq_lock_trace dummy\n",
    }
    tick = []
    for index, target in enumerate(public_manifest()["targets"]):
        for category, pos in target["feedback_chests"].items():
            xyz = " ".join(map(str, pos))
            key = f"target_{index+1}_{category}"
            tick += [f"data modify storage livequest:locks {key} set from block {xyz} Items"]
    for label, (x0,y,z0) in (("first",(50,73,0)),("second",(51,77,20))):
        for name,(x,z) in {"raw":(-1,0),"lower":(9,0),"upper":(9,2),"weak":(4,-5)}.items():
            if label == "second" and name == "raw":
                x,z = -1,0
            holder = f"#{label}_{name}"
            tick += [f"execute store result score #current lq_lock_trace run data get block {x0+x} {y} {z0+z} OutputSignal",
                     f"execute unless score {holder} lq_lock_trace matches 0.. run scoreboard players set {holder} lq_lock_trace 0",
                     f"execute if score #current lq_lock_trace > {holder} lq_lock_trace run scoreboard players operation {holder} lq_lock_trace = #current lq_lock_trace"]
        for name,pos,block in (
            ("accept_torch",(x0+17,y,z0+1),"redstone_wall_torch[lit=true]"),
            ("high_end",(26,73,z0+5),"repeater[powered=true]"),
            ("accept_end",(26,73,z0+8),"repeater[powered=true]"),
        ):
            tick.append(f"execute if block {' '.join(map(str,pos))} {block} run scoreboard players set #{label}_{name} lq_lock_trace 1")
    files["data/livequest_lock/functions/tick.mcfunction"] = "\n".join(tick) + "\n"
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value)
