"""Passive timing evidence for two original carts; no scheduled gameplay commands."""
import json
from pathlib import Path
import re


WARNINGS = {"east": (-5, 72, -8), "west": (7, 72, -8)}


def diode_command(command):
    # Native diode FACING points toward the input, not the outgoing clock signal.
    opposite = {"north": "south", "south": "north", "east": "west", "west": "east"}
    return re.sub(r"\b(repeater|comparator)\[facing=(north|south|east|west)",
                  lambda match: f"{match[1]}[facing={opposite[match[2]]}", command)


def public_manifest(offset=0):
    return {
        "kind": "native_timed_one_way_routing",
        "control": [0, 72, -8], "initial_route": "east",
        "destinations": {"east": [12, 22], "west": [-22, -12]},
        "warning_indicators": WARNINGS,
        "goal": "Both original carts at their designated opposite docks, both original consignments carried, living return to yellow marker.",
        "native_timing": {
            "hopper_transfer_ticks": 8, "tick_rate": 20,
            "east_warning_ticks": (40+offset)*8, "east_departure_ticks": (80+offset)*8,
            "west_warning_ticks": (120+offset)*8, "west_departure_ticks": (160+offset)*8,
            "warning_lead_ticks": 320,
            "disclosure": "Nominal initial-state timings; proof reports actual elapsed native ticks. These are native hopper transfers, not wall-clock callbacks.",
        },
        "controls": "Lever off selects east, on selects west. Protected elevated approaches drop into lower capture docks. Cargo leaves through ordinary hoppers. No mining/pushing tool is disabled.",
        "irreversibility_limit": "One-way capture and route selection require native verification; no qualification inferred from geometry alone.",
    }


def install(world: Path):
    root = world / "datapacks/livequest_routing"
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive original-cart and warning samples"}},
        "data/minecraft/tags/functions/load.json": {"values": ["livequest_routing:load"]},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_routing:tick"]},
        "data/livequest_routing/functions/load.mcfunction": "scoreboard objectives add lq_route dummy\n",
        "data/livequest_routing/functions/tick.mcfunction":
            "scoreboard players add #sample lq_route 1\n"
            "execute if score #sample lq_route matches 10.. run function livequest_routing:sample\n"
            "execute if score #sample lq_route matches 10.. run scoreboard players set #sample lq_route 0\n",
    }
    sample = [
        "data modify storage livequest:routing samples append value {east_warning:0,west_warning:0}",
        "execute store result storage livequest:routing samples[-1].tick long 1 run time query gametime",
    ]
    for name, pos in WARNINGS.items():
        sample += [
            f"data modify storage livequest:routing samples[-1].{name}_pos set from entity @e[type=chest_minecart,tag=original_cart_{name},limit=1] Pos",
            f"execute if block {' '.join(map(str,pos))} piston_head run data modify storage livequest:routing samples[-1].{name}_warning set value 1",
        ]
    files["data/livequest_routing/functions/sample.mcfunction"] = "\n".join(sample) + "\n"
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value)


def item_list(count):
    if not 1 <= count <= 320:
        raise ValueError("Native hopper capacity exceeded")
    result = []
    for slot in range(5):
        size = min(64, count)
        if size:
            result.append(f'{{Slot:{slot}b,id:"minecraft:paper",Count:{size}b}}')
        count -= size
    return "[" + ",".join(result) + "]"


def timing(samples, start_tick):
    evidence = {}
    for name in WARNINGS:
        rows = [row for row in samples if int(row["tick"]) >= start_tick and name+"_pos" in row]
        initial = rows[0][name+"_pos"] if rows else None
        warning = next((int(row["tick"])-start_tick for row in rows if row[name+"_warning"]), None)
        moved = next((int(row["tick"])-start_tick for row in rows
                      if sum((float(a)-float(b))**2 for a, b in zip(row[name+"_pos"], initial)) > .25), None)
        evidence[name] = {"warning_tick": warning, "first_movement_tick": moved}
    return evidence
