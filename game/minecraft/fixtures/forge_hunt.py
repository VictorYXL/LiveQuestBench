"""Author an isolated native forge/hunt world and passive vanilla event datapack."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

import nbtlib

from game.minecraft.runtime.install import check_java, server_jar
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.runtime.session import WorldReadLock, validate_world


TARGET = UUID("744c20a7-27b3-4f66-a269-65bfe6479bd1")
SCHEMA = "minecraft-forge-hunt/1"
OUTPOST_SCHEMA = "minecraft-two-outposts/1"


def targets_for(encounters: int = 1) -> list[dict]:
    if encounters not in (1, 2):
        raise ValueError("Only one or two authored encounters are supported")
    targets = [{"role": "sentinel", "uuid": str(TARGET), "type": "minecraft:husk",
                "position": [28.5, 72, .5], "health": 20}]
    if encounters == 2:
        targets.append({"role": "spider", "uuid": "b2520b61-8001-4e04-a777-e01a71e881fa",
                        "type": "minecraft:spider", "position": [62.5, 72, .5], "health": 16})
    return targets


def uuid_parts(value: UUID) -> list[int]:
    values = [(value.int >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
    return [part if part < 2**31 else part - 2**32 for part in values]


def pack_files(encounters: int = 1) -> dict[str, object]:
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive forge/hunt native kill evidence"}},
    }
    for enemy in targets_for(encounters):
        role = enemy["role"]
        target = "[I;" + ",".join(map(str, uuid_parts(UUID(enemy["uuid"])))) + "]"
        files[f"data/livequest/advancements/{role}.json"] = {
            "criteria": {"kill": {"trigger": "minecraft:player_killed_entity", "conditions": {
                "entity": {"type": enemy["type"], "nbt": "{UUID:" + target + "}"},
            }}},
            "rewards": {"function": f"livequest:{role}"},
        }
        files[f"data/livequest/functions/{role}.mcfunction"] = "\n".join([
            "scoreboard players add @s lq_stone 0",
            "scoreboard players add @s lq_iron 0",
            'data modify storage livequest:expedition kills append value {role:"' + role + '",stone:0,iron:0,hand:""}',
            "data modify storage livequest:expedition kills[-1].player set from entity @s UUID",
            "data modify storage livequest:expedition kills[-1].hand set from entity @s SelectedItem.id",
            "execute store result storage livequest:expedition kills[-1].tick long 1 run time query gametime",
            "execute store result storage livequest:expedition kills[-1].stone int 1 run scoreboard players get @s lq_stone",
            "execute store result storage livequest:expedition kills[-1].iron int 1 run scoreboard players get @s lq_iron",
        ]) + "\n"
    return files


def pack_hashes(world: Path, encounters: int = 1) -> dict[str, str]:
    root = world / "datapacks/livequest_forge"
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in pack_files(encounters)}


def route_gates(condition: int) -> list[dict]:
    if type(condition) is not int or condition not in (0, 1):
        raise ValueError("Reconnaissance condition must be 0 or 1")
    return [{"x": x, "open_z": z, "closed_z": -z - 1}
            for x, z in zip((20, 45), ((-8, 7) if condition == 0 else (7, -8)))]


async def author(source: Path, output: Path, encounters: int = 1, *, route_condition: int | None = None) -> Path:
    targets = targets_for(encounters)
    gates = route_gates(route_condition) if route_condition is not None else None
    if gates is not None and encounters != 2:
        raise ValueError("Reconnaissance requires two outposts")
    schema = SCHEMA if encounters == 1 else OUTPOST_SCHEMA
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    output.mkdir(parents=True, exist_ok=False)
    world = output / "world"
    with WorldReadLock(source):
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock"))
    for name, value in pack_files(encounters).items():
        path = world / "datapacks/livequest_forge" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")
    (output / "eula.txt").write_text("eula=true\n")
    (output / "server.properties").write_text(
        "level-name=world\nonline-mode=false\nserver-ip=127.0.0.1\nserver-port=0\n"
        "spawn-protection=0\nview-distance=6\nsimulation-distance=6\nmax-players=1\n"
        "difficulty=normal\nenable-rcon=false\nenable-query=false\n"
    )
    server = MinecraftServer(output, server_jar(), check_java(), 2048, 0, 120, 30)
    commands = [
        "tick freeze", "gamerule doMobSpawning false", "gamerule doDaylightCycle false",
        "gamerule doWeatherCycle false", "gamerule doTraderSpawning false",
        "gamerule naturalRegeneration true", "gamerule keepInventory false",
        "gamerule commandBlockOutput false", "gamerule sendCommandFeedback false",
        "time set noon", "weather clear",
        "forceload add -16 -16 47 15",
        "fill -12 72 -12 38 82 12 air",
        "fill -12 71 -12 38 71 12 grass_block",
        "fill 12 72 -8 12 74 8 stone_bricks",
        "setblock 0 71 0 yellow_wool",
        "setblock -1 72 2 crafting_table",
        "setblock 1 72 2 furnace",
        "scoreboard objectives add lq_stone minecraft.crafted:minecraft.stone_sword",
        "scoreboard objectives add lq_iron minecraft.crafted:minecraft.iron_sword",
        f'data modify storage livequest:expedition state set value {{schema:"{schema}",target:"{TARGET}"}}',
        "data modify storage livequest:expedition kills set value []",
        "kill @e[type=minecraft:husk]",
        'summon minecraft:husk 28.5 72 0.5 {UUID:[I;'
        + ",".join(map(str, uuid_parts(TARGET)))
        + '],PersistenceRequired:1b,CanPickUpLoot:0b,CustomName:\'{"text":"Sentinel"}\',CustomNameVisible:1b}',
        "save-all flush",
    ]
    if encounters == 2:
        spider = targets[1]
        commands[-1:-1] = [
            "forceload add 32 -16 79 15",
            "fill 39 72 -12 74 82 12 air",
            "fill -12 64 -12 74 70 12 stone",
            "fill 39 71 -12 74 71 12 grass_block",
            "fill -12 72 -12 74 74 -12 stone_bricks",
            "fill -12 72 12 74 74 12 stone_bricks",
            "fill -12 72 -11 -12 74 11 stone_bricks",
            "fill 74 72 -11 74 74 11 stone_bricks",
            "fill -12 75 -12 74 75 -11 stone_bricks",
            "fill -12 75 11 74 75 12 stone_bricks",
            "fill -12 75 -10 -11 75 10 stone_bricks",
            "fill 73 75 -10 74 75 10 stone_bricks",
            "fill 45 72 -8 45 74 8 stone_bricks",
            "setblock 50 72 5 chest",
            'data merge block 50 72 5 {Items:[{Slot:0b,id:"minecraft:bread",Count:4b}]}',
            "setblock 68 72 0 chest",
            'data merge block 68 72 0 {Items:[{Slot:0b,id:"minecraft:paper",Count:1b,'
            'tag:{livequest_cargo:"outpost_records",display:{Name:\'{"text":"Outpost Records"}\'}}}]}',
            'summon minecraft:spider 62.5 72 0.5 {UUID:[I;'
            + ",".join(map(str, uuid_parts(UUID(spider["uuid"]))))
            + '],PersistenceRequired:1b,CustomName:\'{"text":"Outpost Spider"}\',CustomNameVisible:1b}',
        ]
    if gates is not None:
        geometry = [
            "fill 12 72 -8 12 74 8 air",
            "fill -12 76 -12 74 79 -12 stone_bricks",
            "fill -12 76 12 74 79 12 stone_bricks",
            "fill -12 76 -11 -12 79 11 stone_bricks",
            "fill 74 76 -11 74 79 11 stone_bricks",
            "fill -12 80 -12 74 80 -11 stone_bricks",
            "fill -12 80 11 74 80 12 stone_bricks",
            "fill -12 80 -10 -11 80 10 stone_bricks",
            "fill 73 80 -10 74 80 10 stone_bricks",
        ]
        for gate in gates:
            x, z = gate["x"], gate["open_z"]
            geometry.extend([
                f"fill {x} 72 -11 {x} 79 11 stone_bricks",
                f"fill {x} 72 {z - 1} {x} 75 {z + 2} air",
            ])
        commands[-1:-1] = geometry
    receipts = []
    try:
        await server.start()
        for command in commands:
            lines = await server.command(command)
            if any("Unknown" in line or "Incorrect" in line or "Error" in line for line in lines):
                raise RuntimeError(f"Fixture command rejected: {command}: {lines}")
            receipts.append({"command": command, "feedback": lines})
        for enemy in targets:
            lines = await server.command(f"data get entity {enemy['uuid']}")
            if not any("has the following entity data:" in line for line in lines):
                raise RuntimeError(f"Authored target is not loaded: {enemy['role']}")
    finally:
        await server.stop()
    for name in ("level.dat", "level.dat_old"):
        path = world / name
        if path.exists():
            data = nbtlib.load(path)
            if data["Data"].get("Player"):
                raise RuntimeError("Authoring unexpectedly created nonempty player data")
            data["Data"].pop("Player", None)
            data.save(path)
    registry = {"schema": schema, "target_uuid": str(TARGET), "target_type": "minecraft:husk",
                "target_position": [28.5, 72, 0.5], "return_position": [0.5, 72, 0.5],
                "pack_sha256": pack_hashes(world, encounters)}
    if encounters == 2:
        registry["targets"] = targets
        registry["cargo"] = "outpost_records"
    if gates is not None:
        registry["route_condition"] = route_condition
        registry["route_gates"] = gates
    (world / "livequest-expedition.json").write_text(json.dumps(registry, indent=2) + "\n")
    (output / "authoring.json").write_text(json.dumps({
        "source": str(source.resolve()), "registry": registry, "commands": receipts,
        "scope": "Native vanilla fixture authoring; passive kill evidence, no combat assistance.",
    }, indent=2) + "\n")
    validate_world(world)
    return world


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--encounters", type=int, choices=(1, 2), default=1)
    parser.add_argument("--route-condition", type=int, choices=(0, 1))
    arguments = parser.parse_args()
    print(asyncio.run(author(arguments.source, arguments.output, arguments.encounters,
                           route_condition=arguments.route_condition)))
