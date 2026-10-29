"""Native hopper countdowns, protected rails and lower one-way capture docks."""
import json
import os
from pathlib import Path
import shutil

from game.minecraft.fixtures.timed_routing import install, item_list, public_manifest, diode_command


def prepare(world):
    shutil.rmtree(world / "datapacks", ignore_errors=True)
    shutil.rmtree(world / "data", ignore_errors=True)
    install(world)


def commands():
    offset = int(os.environ.get("LQ_NATIVE_PHASE_ITEMS", "0"))
    if not 0 <= offset <= 160:
        raise ValueError("Unsupported native phase")
    result = ["tick freeze", "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
              "gamerule doDaylightCycle false", "gamerule doWeatherCycle false", "time set noon",
              "kill @e[type=!minecraft:player]", "forceload add -32 -16 31 47"]
    for x in range(-28, 29, 7):
        result += [f"fill {x} 50 -12 {x+6} 71 43 bedrock",
                   f"fill {x} 72 -12 {x+6} 90 43 air"]
    result += ["fill -23 72 -5 23 90 -5 bedrock", "fill -23 72 42 23 90 42 bedrock",
               "fill -23 72 -5 -23 90 42 bedrock", "fill 23 72 -5 23 90 42 bedrock",
               "fill -23 90 -5 23 90 42 bedrock",
               "fill -22 73 -5 22 73 -5 air", "fill -22 75 -5 22 75 -5 air",
               "fill -1 71 -11 1 71 -9 yellow_wool"]
    for z in range(1, 36):
        y = 75 if z <= 20 else 76
        special = z in (20, 35)
        powered = not special and z not in (1, 2, 3, 18, 19, 21, 22, 33, 34)
        result += [f"setblock 0 {y-1} {z} " + ("redstone_block" if powered else "bedrock"),
                   f"setblock 0 {y} {z} " + (
                       "powered_rail[shape=ascending_south]" if special else
                       "powered_rail[shape=north_south]" if powered else "rail[shape=north_south]")]
    result += ["setblock 0 76 36 bedrock", "setblock 0 77 36 rail[shape=north_south]"]
    for side in (-1, 1):
        for x in range(1, 11):
            powered = x >= 4
            result += [f"setblock {x*side} 74 0 " + ("redstone_block" if powered else "bedrock"),
                       f"setblock {x*side} 75 0 " + ("powered_rail[shape=east_west]" if powered else "rail[shape=east_west]")]
        for x in range(12, 24):
            direction = "east" if side == 1 else "west"
            result.append(f"setblock {x*side} 71 0 hopper[facing={direction}]")
            if x < 23:
                result.append(f"setblock {x*side} 72 0 powered_rail[shape=east_west,powered=false]")
        result.append(f"setblock {24*side} 71 0 chest")
    result += ["setblock 0 74 0 bedrock", "setblock 0 75 0 rail[shape=south_east]",
               "setblock 0 72 -8 lever[face=floor,powered=false]"]
    for z, y in ((-7, 72), (-6, 73), (-5, 74), (-4, 75), (-3, 75), (-2, 75), (-1, 75)):
        result += [f"setblock 0 {y-1} {z} bedrock", f"setblock 0 {y} {z} redstone_wire"]
    clocks = []
    for z, y, count in ((20, 75, 80+offset), (35, 76, 160+offset)):
        result += [f"setblock 4 {y-1} {z} chest", f"setblock 4 {y} {z} hopper[facing=down]",
                   f"setblock 3 {y-1} {z} bedrock", f"setblock 3 {y} {z} comparator[facing=west]",
                   f"setblock 2 {y} {z} stone_bricks", f"setblock 1 {y} {z} redstone_wall_torch[facing=west]"]
        clocks.append((4, y, z, count))
    for x, count in ((-4, 40+offset), (8, 120+offset)):
        result += [f"setblock {x} 68 -8 chest", f"setblock {x} 69 -8 hopper[facing=down]",
                   f"setblock {x-1} 68 -8 bedrock", f"setblock {x-1} 69 -8 comparator[facing=west]",
                   f"setblock {x-2} 69 -8 stone_bricks", f"setblock {x-2} 70 -8 redstone_torch",
                   f"setblock {x-2} 72 -8 redstone_lamp", f"setblock {x-1} 71 -8 piston[facing=up]"]
        clocks.append((x, 69, -8, count))
    # Settle powered rails before originals and the final initial clock inventory exist.
    for x, y, z, count in clocks:
        result.append(f"data merge block {x} {y} {z} {{Items:{item_list(count)},TransferCooldown:8}}")
    result += ["tick step 60", "kill @e[type=!minecraft:player]"]
    for x, y, z, count in clocks:
        result += [f"data merge block {x} {y-1} {z} {{Items:[]}}",
                   f"data merge block {x} {y} {z} {{Items:{item_list(count)},TransferCooldown:8}}"]
    for name, z, y in (("east", 20, 75), ("west", 35, 76)):
        result.append(f'summon chest_minecart 0.5 {y+.5} {z+.5} {{Tags:["original_cart_{name}"],'
                      f'CustomName:\'{{"text":"{name.title()} Cart"}}\',CustomNameVisible:1b,'
                      f'Items:[{{Slot:0b,id:"minecraft:paper",Count:1b,tag:{{livequest_cargo:"{name}_consignment"}}}}]}}')
    return [diode_command(command) for command in result + ["save-all flush"]]


def export(world):
    (world / "livequest-routing-public.json").write_text(json.dumps(
        public_manifest(int(os.environ.get("LQ_NATIVE_PHASE_ITEMS", "0"))), indent=2) + "\n")
    shutil.copytree(world, Path(os.environ["LQ_PROTOTYPE_FIXTURE"]),
                    ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
