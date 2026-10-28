"""Author reproducible native route-transfer fixtures from an explicit source world."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil

import yaml

from game import route_transfer
from game.route_transfer import build_layout, cuboids


def prompt(layout):
    return (
        "Explore the first three-module wing, then traverse two application wings and finish "
        "alive and stationary at the centre of the final enlarged chamber. "
        "Complete the route without dying or respawning.\n"
        "Each module has one, two or three shallow niches in the wall beside its entrance. "
        "Within this instance, a given niche pattern always has the same continuing exit "
        "side relative to the direction in which you enter. One branch continues; the other "
        "ends at a solid wall. Learn the architecture through ordinary exploration.\n"
        "After the first wing, descend the connecting staircase. Later wings rearrange the "
        "module order and rotate their orientation. Reuse what you discovered; an absolute "
        "compass direction or blindly replaying the first turn sequence will not suffice.\n"
        f"The two application wings together allow at most {layout['application_distance_limit']} "
        "metres of sampled native travel, including detours and backtracking. Practice travel "
        "and connecting stairs are outside that distance allowance, but still consume episode "
        "time. All movement remains ordinary native movement; there are no modified controls, "
        "recipes or physics. Complete the application wings in order and remain in the final chamber."
    )


def task(game, layout, fixture, track):
    tools = (["MoveTool", "LookAtPositionTool", "StopTool", "JumpTool", "RespawnTool"]
             if game == "minecraft"
             else ["MoveTool", "LookTool", "TurnTool", "StopTool", "JumpTool", "RespawnTool"])
    row = {
        "id": "route_schema_transfer", "game": game, "task_type": track,
        "task": prompt(layout), "time_limit_seconds": 2700, "fixture": fixture,
        "evaluator": {"name": "route_transfer", "parameters": {
            "variant": layout["variant"], "origin": layout["origin"],
        }},
        "capabilities": {
            "primary": ["within_episode_learning"], "secondary": ["spatial_interaction"],
        },
    }
    if track == "structured_tool":
        row["tools"] = tools
    return row


async def minecraft(output, variant, source):
    import nbtlib

    from game.minecraft.fixtures.route_transfer import SCHEMA, expected_hashes, pack_text, route_pack
    from game.minecraft.runtime.install import check_java, server_jar
    from game.minecraft.runtime.server import MinecraftServer
    from game.minecraft.runtime.session import WorldReadLock, validate_world

    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Minecraft EULA acceptance is required")
    output.mkdir(parents=True, exist_ok=False)
    origin = (0, 0, 201)
    layout = build_layout(variant, origin)
    layout["origin"] = list(origin)
    world = output / "world"
    validate_world(source)
    with WorldReadLock(source):
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
    for name, value in route_pack().items():
        path = world / "datapacks/livequest_route" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pack_text(value))
    (world / "livequest-route-evidence.json").write_text(json.dumps({
        "schema": SCHEMA, "pack_sha256": expected_hashes(),
    }, indent=2) + "\n")
    (output / "eula.txt").write_text("eula=true\n")
    (output / "server.properties").write_text(
        "level-name=world\nonline-mode=false\nserver-ip=127.0.0.1\nserver-port=0\n"
        "spawn-protection=0\nview-distance=6\nsimulation-distance=6\nmax-players=1\n"
        "difficulty=peaceful\nenable-rcon=false\nenable-query=false\n"
    )
    commands = [
        "tick freeze", "kill @e[type=!minecraft:player]",
        "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
        "gamerule commandBlockOutput false", "gamerule sendCommandFeedback false",
        "setworldspawn 0 201 0", "gamerule spawnRadius 0", "time set noon", "weather clear",
        "scoreboard objectives add lq_route dummy",
        f'data modify storage livequest:route schema set value "{SCHEMA}"',
        "data modify storage livequest:route overflow set value 0b",
        "data modify storage livequest:route samples set value []",
    ]
    chunks = sorted({(x // 16, y // 16) for x, y, _ in layout["solid"]})
    for x, y in chunks:
        commands.append(f"forceload add {x * 16} {y * 16}")
    air = {(x, y, z + dz) for x, y, z in layout["walking"] for dz in range(3)}
    for material, voxels in (("air", air), ("bedrock", layout["solid"])):
        for box in cuboids(voxels):
            x, y, z = box["origin"]
            sx, sy, sz = box["size"]
            commands.append(f"fill {x} {z} {y} {x + sx - 1} {z + sz - 1} {y + sy - 1} {material}")
    lights = {(x, y, z + 1) for x, y, z in layout["walking"]}
    for box in cuboids(lights):
        x, y, z = box["origin"]
        sx, sy, sz = box["size"]
        commands.append(
            f"fill {x} {z} {y} {x + sx - 1} {z + sz - 1} {y + sy - 1} light[level=15]"
        )
    commands.extend(["save-all flush"])
    (output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    server = MinecraftServer(output, server_jar(), check_java(), 2048, 0, 120, 30)
    receipts = []
    try:
        await server.start()
        for command in commands:
            feedback = await server.command(command)
            receipts.append({"command": command, "feedback": feedback})
    finally:
        await server.stop()
        (output / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    level = nbtlib.load(world / "level.dat")
    if "Player" in level["Data"] and not level["Data"]["Player"]:
        del level["Data"]["Player"]
        level.save(world / "level.dat")
    validate_world(world)
    fixture = {
        "world_path": str(world), "instance": "1.20.4", "difficulty": "peaceful",
        "player_state": {
            "position": [0.5, 201, 0.5], "dimension": "minecraft:overworld",
            "yaw": 0, "pitch": 0, "gamemode": "survival", "health": 20,
            "food": 20, "saturation": 5, "experience_level": 0, "inventory": [],
        },
    }
    save_tasks(output, "minecraft", layout, fixture)


def veloren(output, variant, source):
    if not source.is_file():
        raise FileNotFoundError(f"Native Veloren source map is missing: {source}")
    output.mkdir(parents=True, exist_ok=False)
    origin = (18702, 10802, 701)
    layout = build_layout(variant, origin, headroom=3)
    layout["origin"] = list(origin)
    fixture = {
        "world_path": str(source), "world_seed": 130626853, "time_of_day": "12:00",
        "day_length": 30, "calendar": "none", "route_evidence": True, "respawn_at_start": True,
        "platform": {"origin": [18700, 10800, 700], "size": [8, 8], "block": "Rock"},
        "blocks": cuboids(layout["solid"]),
        "player_state": {
            "position": [18702.5, 10802.5, 701], "look": [0, 1, 0], "health": 100,
            "inventory": {}, "equipment": {
                "active_mainhand": "common.items.weapons.sword.starter",
                "chest": "common.items.armor.misc.chest.worker_purple_brown",
                "feet": "common.items.armor.misc.foot.sandals",
                "glider": "common.items.glider.basic_white",
                "lantern": "common.items.lantern.black_0",
                "legs": "common.items.armor.misc.pants.worker_brown",
            },
        },
    }
    save_tasks(output, "veloren", layout, fixture)


def save_tasks(output, game, layout, fixture):
    (output / "authoring.json").write_text(json.dumps({
        "schema": layout["schema"],
        "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "layout_source_sha256": hashlib.sha256(Path(route_transfer.__file__).read_bytes()).hexdigest(),
        "status": "authored_not_qualified",
    }, indent=2) + "\n")
    (output / "layout.json").write_text(json.dumps({
        k: v for k, v in layout.items() if k not in ("walking", "solid")
    }, indent=2) + "\n")
    for track in ("structured_tool", "visual_motor"):
        (output / f"{track}.yaml").write_text(yaml.safe_dump(
            task(game, layout, fixture, track), sort_keys=False,
        ))
    print(json.dumps({"game": game, "variant": layout["variant"], "voxels": len(layout["solid"]),
                      "output": str(output), "status": "authored_not_qualified"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=["minecraft", "veloren"], required=True)
    parser.add_argument("--variant", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-world", type=Path, required=True)
    args = parser.parse_args()
    if args.game == "minecraft":
        asyncio.run(minecraft(args.output.resolve(), args.variant, args.source_world.resolve()))
    else:
        veloren(args.output.resolve(), args.variant, args.source_world.resolve())


if __name__ == "__main__":
    main()
