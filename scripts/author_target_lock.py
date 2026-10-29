"""Initial native comparator circuit and original token authoring."""
import json
import os
from pathlib import Path
import shutil
import nbtlib

from game.minecraft.fixtures.target_lock import circuit, install, public_manifest, diode_command


def prepare(world):
    shutil.rmtree(world / "datapacks", ignore_errors=True)
    shutil.rmtree(world / "data", ignore_errors=True)
    install(world)


def commands():
    lower = int(os.environ.get("LQ_NATIVE_LOWER", "4"))
    if lower not in (1, 4, 7, 10):
        raise ValueError("Unsupported native window")
    result = ["tick freeze", "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
              "gamerule doDaylightCycle false", "gamerule doWeatherCycle false", "time set noon",
              "kill @e[type=!minecraft:player]", "forceload add -16 -32 95 63"]
    for x in range(-4, 94, 7):
        result += [f"fill {x} 50 -26 {x+6} 71 60 bedrock",
                   f"fill {x} 72 -26 {x+6} 101 60 air"]
    result += ["fill 16 72 -25 90 100 -25 bedrock", "fill 16 72 60 90 100 60 bedrock",
               "fill 16 72 -25 16 100 60 bedrock", "fill 90 72 -25 90 100 60 bedrock",
               "fill 16 100 -25 90 100 60 bedrock",
               "setblock 16 73 0 air", "fill 16 76 0 16 78 0 air",
               "setblock 18 73 0 target", "setblock 28 77 0 target"]
    for x in range(19, 50):
        result += [f"setblock {x} 72 0 bedrock", f"setblock {x} 73 0 comparator[facing=east]"]
    for x in range(29, 49):
        result += [f"setblock {x} 76 0 bedrock", f"setblock {x} 77 0 comparator[facing=east]"]
    result += ["setblock 49 77 0 stone_bricks"]
    for z in range(1, 20):
        result += [f"setblock 49 76 {z} bedrock", f"setblock 49 77 {z} comparator[facing=south]"]
    result += ["setblock 49 77 20 stone_bricks", "setblock 50 76 20 bedrock",
               "setblock 50 77 20 comparator[facing=east]"]
    for x0, y, z0 in ((50, 73, 0), (51, 77, 20)):
        for pos, value in circuit(x0, y, z0, lower).items():
            result.append(f"setblock {' '.join(map(str, pos))} {value}")
        for z in (-5, 5, 8):
            result.append(f"setblock 16 73 {z0+z} air")
    result += ["tick step 160"]
    for index, z0 in enumerate((0, 20), 1):
        for z, category in ((-5, "low"), (5, "high"), (8, "accepted")):
            count = 1 if category == "accepted" else 64
            tag = f'{{livequest_token:"target_{index}"}}' if category == "accepted" else "{}"
            result += [f'data merge block 17 73 {z0+z} {{Items:[]}}',
                       f'data merge block 25 73 {z0+z} {{Items:[{{Slot:0b,id:"minecraft:paper",Count:{count}b,tag:{tag}}}]}}',
                       f"setblock 16 74 {z0+z+2} air"]
    # Initial-state hardware checks are explicitly not a legal player witness.
    for strength in (1, lower+1, 15):
        for label in ("first","second"):
            for name in ("raw","lower","upper","weak","accept_torch","high_end","accept_end"):
                result.append(f"scoreboard players set #{label}_{name} lq_lock_trace 0")
        for index, z0 in enumerate((0,20),1):
            for z, category in ((-5,"low"),(5,"high"),(8,"accepted")):
                count = 1 if category == "accepted" else 64
                tag = f'{{livequest_token:"target_{index}"}}' if category == "accepted" else "{}"
                result += [f'data merge block 17 73 {z0+z} {{Items:[]}}',
                           f'data merge block 25 73 {z0+z} {{Items:[{{Slot:0b,id:"minecraft:paper",Count:{count}b,tag:{tag}}}]}}']
        result += [f"setblock 18 73 0 target[power={strength}]", f"setblock 28 77 0 target[power={strength}]",
                   "tick step 20", "setblock 18 73 0 target[power=0]", "setblock 28 77 0 target[power=0]",
                   "tick step 240", f"data modify storage livequest:lock_preflight cases append value {{strength:{strength},deliveries:[]}}"]
        for z0 in (0,20):
            result += ["data modify storage livequest:lock_preflight cases[-1].deliveries append value {}"]
            for z, category in ((-5,"low"),(5,"high"),(8,"accepted")):
                result.append(f"data modify storage livequest:lock_preflight cases[-1].deliveries[-1].{category} set from block 17 73 {z0+z} Items")
        for label in ("first","second"):
            for name in ("raw","lower","upper","weak","accept_torch","high_end","accept_end"):
                result.append(f"execute store result storage livequest:lock_preflight cases[-1].{label}_{name} int 1 run scoreboard players get #{label}_{name} lq_lock_trace")
    for index,z0 in enumerate((0,20),1):
        for z,category in ((-5,"low"),(5,"high"),(8,"accepted")):
            count = 1 if category == "accepted" else 64
            tag = f'{{livequest_token:"target_{index}"}}' if category == "accepted" else "{}"
            result += [f'data merge block 17 73 {z0+z} {{Items:[]}}',
                       f'data merge block 25 73 {z0+z} {{Items:[{{Slot:0b,id:"minecraft:paper",Count:{count}b,tag:{tag}}}]}}']
    result += ["kill @e[type=!minecraft:player]", "save-all flush"]
    return [diode_command(command) for command in result]


def export(world):
    rows = nbtlib.load(world / "data/command_storage_livequest.dat")["data"]["contents"]["lock_preflight"]["cases"].unpack()
    lower = int(os.environ.get("LQ_NATIVE_LOWER","4"))
    passed = len(rows) == 3
    for row in rows:
        expected = "low" if row["strength"] < lower else "high" if row["strength"] >= lower+4 else "accepted"
        passed &= len(row["deliveries"]) == 2 and all(
            {name for name,items in delivery.items() if items} == {expected}
            for delivery in row["deliveries"])
    (world.parent / "hardware-preflight.json").write_text(json.dumps(
        {"kind":"authoring_only_native_hardware_preflight_not_player_witness",
         "input_pulse_ticks":20,"passed":bool(passed),"cases":rows},
        indent=2,default=lambda x:x.tolist())+"\n")
    if not passed:
        raise RuntimeError("Native analog lock hardware preflight failed")
    (world / "livequest-lock-public.json").write_text(json.dumps(public_manifest(), indent=2) + "\n")
    shutil.copytree(world, Path(os.environ["LQ_PROTOTYPE_FIXTURE"]),
                    ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
