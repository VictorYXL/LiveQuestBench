"""Initial-state authoring only; hidden choice is a real native wire connection."""
import json
import os
from pathlib import Path
import shutil
import nbtlib

from game.minecraft.fixtures.function_replication import PANELS, module, install_recorder, public_manifest, diode_command


def prepare(world):
    shutil.rmtree(world / "datapacks", ignore_errors=True)
    shutil.rmtree(world / "data", ignore_errors=True)
    install_recorder(world)


def commands():
    choice = os.environ.get("LQ_NATIVE_FUNCTION", "AND")
    if choice not in ("AND", "OR"):
        raise ValueError("The bounded native prototype implements AND/OR only")
    result = ["tick freeze", "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
              "gamerule doDaylightCycle false", "gamerule doWeatherCycle false", "time set noon",
              "weather clear", "kill @e[type=!minecraft:player]", "forceload add -48 -32 111 47"]
    for x in range(-36, 100, 8):
        result += [f"fill {x} 50 -24 {x+7} 71 44 bedrock",
                   f"fill {x} 72 -24 {x+7} 95 44 air"]
    result += ["fill 5 72 -20 95 94 -20 bedrock", "fill 5 72 30 95 94 30 bedrock",
               "fill 5 72 -20 5 94 30 bedrock", "fill 95 72 -20 95 94 30 bedrock",
               "fill 5 94 -20 95 94 30 bedrock"]
    for panel in PANELS:
        result += [f"setblock {' '.join(map(str, pos))} {block}" for pos, block in module(panel).items()]
    result += [f"setblock {' '.join(map(str, pos))} {block}" for pos, block in module((60, 0, 1), remote=True).items()]
    for z in (0, 6):
        result.append(f"setblock 0 72 {z} lever[face=floor]")
        for x in range(1, 60):
            result.append(f"setblock {x} 72 {z} " + ("repeater[facing=east]" if x % 12 == 0 else "redstone_wire"))
    # Input B crosses the OR return column at x55: a real raised wire bridge
    # prevents B from directly powering the output independently of the gate.
    for x in range(50,58):
        if x != 55:
            result.append(f"setblock {x} 72 6 air")
        y = 73 if x in (50,57) else 74
        support = "glass" if x == 55 else "bedrock"
        result += [f"setblock {x} {y-1} 6 {support}", f"setblock {x} {y} 6 redstone_wire"]
    for z in range(12, 15):
        result.append(f"setblock 64 72 {z} redstone_wire")
    result.append("setblock 64 72 12 repeater[facing=south]")
    for x in range(1, 64):
        result.append(f"setblock {x} 72 14 " + ("repeater[facing=west]" if x % 12 == 0 else "redstone_wire"))
    result += ["setblock 1 72 14 repeater[facing=west]", "setblock 0 72 14 stone_bricks",
               "setblock 0 73 14 redstone_lamp", "setblock 0 72 15 piston[facing=up]",
               f"setblock {71 if choice == 'AND' else 57} 72 3 cobblestone"]
    # Transmit through solid native blocks, not crawlable cable holes.
    for z in (0, 6):
        result += [f"setblock 4 72 {z} repeater[facing=east]",
                   f"setblock 5 72 {z} bedrock", f"setblock 6 72 {z} repeater[facing=east]"]
    result += ["setblock 6 72 14 repeater[facing=west]", "setblock 5 72 14 bedrock",
               "setblock 4 72 14 repeater[facing=west]", "tick step 100"]
    public = public_manifest()
    for panel in public["panels"]:
        result.append(f"setblock {' '.join(map(str,panel['sockets'][choice]))} cobblestone")
    for a, b in ((0, 0), (1, 0), (1, 1), (0, 1)):
        for station in [public["reference"], *public["panels"]]:
            for value, pos in zip((a, b), station["inputs"]):
                result.append(f"setblock {' '.join(map(str,pos))} lever[face=floor,powered={str(bool(value)).lower()}]")
        result += ["tick step 200", f"data modify storage livequest:function_preflight cases append value {{a:{a},b:{b},outputs:[],native_inputs:[0,0],native_gate:0}}",
                   "execute store result storage livequest:function_preflight cases[-1].tick long 1 run time query gametime",
                   "execute if block 65 72 0 redstone_wall_torch[lit=false] run data modify storage livequest:function_preflight cases[-1].native_inputs[0] set value 1",
                   "execute if block 65 72 6 redstone_wall_torch[lit=false] run data modify storage livequest:function_preflight cases[-1].native_inputs[1] set value 1",
                   "execute if block 69 72 3 redstone_wall_torch[lit=true] run data modify storage livequest:function_preflight cases[-1].native_gate set value 1"]
        for station in [public["reference"], *public["panels"]]:
            xyz = " ".join(map(str,station["output"]))
            result += ["data modify storage livequest:function_preflight cases[-1].outputs append value 0",
                       f"execute if block {xyz} redstone_lamp[lit=true] run data modify storage livequest:function_preflight cases[-1].outputs[-1] set value 1"]
    for station in [public["reference"], *public["panels"]]:
        for pos in station["inputs"]:
            result.append(f"setblock {' '.join(map(str,pos))} lever[face=floor,powered=false]")
    for panel in public["panels"]:
        result.append(f"setblock {' '.join(map(str,panel['sockets'][choice]))} air")
    result += ["tick step 100", "kill @e[type=!minecraft:player]",
               "data modify storage livequest:function events set value []", "save-all flush"]
    return [diode_command(command) for command in result]


def export(world):
    rows = nbtlib.load(world / "data/command_storage_livequest.dat")["data"]["contents"]["function_preflight"]["cases"].unpack()
    choice = os.environ.get("LQ_NATIVE_FUNCTION", "AND")
    expected = [int(bool(row["a"] and row["b"]) if choice == "AND" else bool(row["a"] or row["b"])) for row in rows]
    evidence = {"kind": "authoring_only_native_hardware_preflight_not_player_witness", "function": choice, "cases": rows,
                "passed": len(rows) == 4 and all(list(row["outputs"]) == [value]*3 for row,value in zip(rows,expected))}
    (world.parent / "hardware-preflight.json").write_text(json.dumps(evidence,indent=2,default=lambda x:x.tolist())+"\n")
    if not evidence["passed"]:
        raise RuntimeError("Native reference/panel circuit truth-table preflight failed")
    (world / "livequest-function-public.json").write_text(json.dumps(public_manifest(), indent=2) + "\n")
    shutil.copytree(world, Path(os.environ["LQ_PROTOTYPE_FIXTURE"]),
                    ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
