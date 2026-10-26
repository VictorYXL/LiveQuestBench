"""Author the MC-S native mine; generation commands never run during an Episode."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil

import nbtlib
import yaml

from game.minecraft.runtime.install import check_java, server_jar
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.runtime.session import WorldReadLock, validate_world


CARGO = [
    {"id": "upper_gallery", "item": "minecraft:raw_iron", "chest": [52, 80, 7]},
    {"id": "lower_excavation", "item": "minecraft:lapis_lazuli", "chest": [0, 57, 38]},
    {"id": "service_chamber", "item": "minecraft:copper_ingot", "chest": [32, 70, 27]},
]
RETURN = {"target": [0.5, 72, 0.5], "horizontal_tolerance": 1.5,
          "vertical_tolerance": 0.5, "max_speed": 0.1}
TASK = """Recover the three original named cargo samples from the abandoned mine
and return with them to the yellow entrance marker.

Approximate target areas, relative to the entrance and your initial facing:
- Upper Gallery Cargo: about 50 blocks forward, on a higher level.
- Lower Excavation Cargo: about 40 blocks to the right, deep below the entrance.
- Service Chamber Cargo: about 30 blocks forward and 30 blocks right,
  slightly below the entrance.

Finish alive and standing still on the ground at the marker.
Release held controls and finish with a text response."""
TOOLS = ["MoveTool", "LookAtPositionTool", "SelectTool", "StopTool", "JumpTool",
         "DigTool", "PlaceTool", "UseHeldItemTool", "InspectContainerTool",
         "TakeContainerItemTool", "QueryCraftRecipeTool", "CraftItemTool", "RespawnTool"]


def chest_commands(row: dict) -> list[str]:
    x, y, z = row["chest"]
    stack = nbtlib.Compound({
        "Slot": nbtlib.Byte(0), "id": nbtlib.String(row["item"]), "Count": nbtlib.Byte(1),
        "tag": nbtlib.Compound({
            "livequest_cargo": nbtlib.String(row["id"]),
            "display": nbtlib.Compound({"Name": nbtlib.String(json.dumps({
                "text": row["id"].replace("_", " ").title() + " Cargo", "italic": False,
            }))}),
        }),
    })
    contents = nbtlib.Compound({"Items": nbtlib.List[nbtlib.Compound]([stack])})
    return [f"setblock {x} {y} {z} chest[facing=west]",
            f"data merge block {x} {y} {z} {contents.snbt()}"]


def commands(pit_floor: int = 62) -> list[str]:
    if pit_floor not in (62, 74):
        raise ValueError("Only the original or shallow-pit development condition is supported")
    result = [
        "tick freeze", "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
        "gamerule doDaylightCycle true", "gamerule doWeatherCycle true",
        "gamerule naturalRegeneration true", "gamerule keepInventory false",
        "gamerule commandBlockOutput false", "gamerule sendCommandFeedback false",
        "time set noon", "weather clear", "forceload add -16 -16 63 47",
        "setworldspawn 0 72 0", "gamerule spawnRadius 0",
    ]
    for x in range(-12, 61, 24):
        for y in range(48, 92, 8):
            result.append(f"fill {x} {y} -12 {min(x+23,60)} {min(y+7,91)} 46 stone")
    result += [
        "fill -5 72 -4 7 77 4 air",
        "fill -3 72 5 3 79 12 air",
        "setblock 0 71 0 yellow_wool",
        "fill 8 72 -2 15 88 2 air",
        f"fill 16 {pit_floor} -7 56 88 14 air",
        "fill 16 79 -2 23 79 2 oak_planks",
        "fill 31 79 5 55 79 9 oak_planks",
        "fill -4 57 13 4 80 40 air",
        "fill -5 57 33 5 64 41 air",
        "fill 5 66 18 13 70 22 air",
        "fill 14 66 17 29 75 31 air",
        "fill 25 66 25 28 67 29 stone_bricks",
        "fill 29 66 25 34 69 29 stone_bricks",
        "fill 30 70 25 34 72 29 air",
    ]
    for step in range(8):
        x, y = 8 + step, 72 + step
        result.extend([
            f"fill {x} 71 -2 {x} {y-1} 2 stone_bricks",
            f"fill {x} {y} -2 {x} {y} 2 stone_brick_stairs[facing=east]",
        ])
    for start, floor in ((13, 68), (18, 65), (23, 62), (28, 59)):
        result.append(f"fill -4 57 {start} 4 {floor} {start+4} stone")
    for x, y, z in [(-3, 72, -3), (4, 72, 3), (0, 72, 10), (18, 80, -1),
                    (35, 80, 8), (47, 80, 8), (20, pit_floor, 0), (34, pit_floor, 7),
                    (48, pit_floor, 7), (-3, 69, 15), (-3, 66, 20), (-3, 63, 25),
                    (-3, 60, 30), (-3, 57, 36), (9, 66, 19), (16, 66, 19),
                    (27, 66, 30), (30, 70, 26)]:
        result.append(f"setblock {x} {y} {z} torch")
    for x in (17, 37, 49):
        low, high = (-2, 2) if x == 17 else (5, 9)
        for z in (low, high):
            result.append(f"fill {x} 80 {z} {x} 84 {z} oak_log")
        result.append(f"fill {x} 85 {low} {x} 85 {high} oak_log[axis=z]")
    for row in CARGO:
        result.extend(chest_commands(row))
    result.extend(["setblock 32 71 27 stone", "save-all flush"])
    return result


async def author(source: Path, output: Path, *, pit_floor: int = 62) -> None:
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    output.mkdir(parents=True, exist_ok=False)
    world = output / "world"
    with WorldReadLock(source):
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
    (output / "eula.txt").write_text("eula=true\n")
    (output / "server.properties").write_text(
        "level-name=world\nonline-mode=false\nserver-ip=127.0.0.1\nserver-port=0\n"
        "spawn-protection=0\nview-distance=6\nsimulation-distance=6\nmax-players=1\n"
        "difficulty=normal\nenable-rcon=false\nenable-query=false\n"
    )
    server = MinecraftServer(output, server_jar(), check_java(), 2048, 0, 120, 30)
    receipts = []
    try:
        await server.start()
        for command in commands(pit_floor):
            lines = await server.command(command)
            if any(word in line for line in lines for word in
                   ("Unknown", "Incorrect", "Error", "too many blocks", "not loaded")):
                raise RuntimeError(f"Mine authoring command rejected: {command}: {lines}")
            receipts.append({"command": command, "feedback": lines})
        for row in CARGO:
            coordinate = " ".join(map(str, row["chest"]))
            lines = await server.command(f"data get block {coordinate} Items")
            if not any(row["id"] in line for line in lines):
                raise RuntimeError(f"Initial native cargo was not saved: {row['id']}")
    finally:
        await server.stop()
    level = nbtlib.load(world / "level.dat")
    if level["Data"].get("Player"):
        raise RuntimeError("Unexpected authoring player data")
    level["Data"].pop("Player", None)
    level.save(world / "level.dat")
    validate_world(world)
    (output / "authoring.json").write_text(json.dumps({
        "source": str(source.resolve()), "commands": receipts, "cargo": CARGO,
        "return": RETURN, "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pit_floor": pit_floor,
        "scope": "Native initial blocks and named items only; no play-time commands or assistance.",
    }, indent=2) + "\n")


def export(output: Path) -> None:
    target = Path("config/minecraft/fixtures/abandoned_mine_v1")
    if target.exists():
        raise FileExistsError("Refusing to replace an existing mine fixture")
    shutil.copytree(output / "world", target,
                    ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
    (output / "fixture-hashes.json").write_text(json.dumps({
        str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(target.rglob("*")) if p.is_file()
    }, indent=2) + "\n")
    for track, folder in (("structured_tool", "structured_tools"), ("visual_motor", "visual_motor")):
        config = {
            "id": "abandoned_mine_cargo_v1", "game": "minecraft", "task_type": track,
            "capabilities": {"primary": ["spatial_interaction"], "secondary": ["planning_resources"]},
            "task": TASK, "time_limit_seconds": 2700,
            "fixture": {
                "world_path": "../../fixtures/abandoned_mine_v1", "instance": "1.20.4",
                "difficulty": "normal",
                "player_state": {
                    "position": [0.5, 72, 0.5], "dimension": "minecraft:overworld",
                    "yaw": -90, "pitch": 0, "gamemode": "survival",
                    "health": 20, "food": 20, "saturation": 5, "experience_level": 0,
                    "inventory": [
                        {"slot": slot, "item": item, "count": count}
                        for slot, (item, count) in enumerate([
                            ("iron_pickaxe", 1), ("oak_planks", 64), ("ladder", 24),
                            ("stone_brick_stairs", 32), ("bread", 16), ("torch", 32), ("iron_axe", 1),
                        ])
                    ],
                },
            },
            "evaluator": {"name": "cargo", "parameters": {"cargo": CARGO, "position": RETURN}},
        }
        if track == "structured_tool":
            config["tools"] = TOOLS
        path = Path(f"config/minecraft/tasks/{folder}/abandoned_mine_cargo_v1.yaml")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            yaml.safe_dump(config, stream, sort_keys=False, width=100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pit-floor", type=int, choices=(62, 74), default=62)
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()
    asyncio.run(author(args.source, args.output, pit_floor=args.pit_floor))
    if not args.no_export:
        export(args.output)
