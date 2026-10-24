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


def uuid_parts(value: UUID) -> list[int]:
    values = [(value.int >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
    return [part if part < 2**31 else part - 2**32 for part in values]


def pack_files() -> dict[str, object]:
    target = "[I;" + ",".join(map(str, uuid_parts(TARGET))) + "]"
    return {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive forge/hunt native kill evidence"}},
        "data/livequest/advancements/sentinel.json": {
            "criteria": {"kill": {"trigger": "minecraft:player_killed_entity", "conditions": {
                "entity": {"type": "minecraft:husk", "nbt": "{UUID:" + target + "}"},
            }}},
            "rewards": {"function": "livequest:sentinel"},
        },
        "data/livequest/functions/sentinel.mcfunction": "\n".join([
            "scoreboard players add @s lq_stone 0",
            "scoreboard players add @s lq_iron 0",
            'data modify storage livequest:expedition kills append value {role:"sentinel",stone:0,iron:0,hand:""}',
            "data modify storage livequest:expedition kills[-1].player set from entity @s UUID",
            "data modify storage livequest:expedition kills[-1].hand set from entity @s SelectedItem.id",
            "execute store result storage livequest:expedition kills[-1].tick long 1 run time query gametime",
            "execute store result storage livequest:expedition kills[-1].stone int 1 run scoreboard players get @s lq_stone",
            "execute store result storage livequest:expedition kills[-1].iron int 1 run scoreboard players get @s lq_iron",
        ]) + "\n",
    }


def pack_hashes(world: Path) -> dict[str, str]:
    root = world / "datapacks/livequest_forge"
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in pack_files()}


async def author(source: Path, output: Path) -> Path:
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    output.mkdir(parents=True, exist_ok=False)
    world = output / "world"
    with WorldReadLock(source):
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock"))
    for name, value in pack_files().items():
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
        f'data modify storage livequest:expedition state set value {{schema:"{SCHEMA}",target:"{TARGET}"}}',
        "data modify storage livequest:expedition kills set value []",
        "kill @e[type=minecraft:husk]",
        'summon minecraft:husk 28.5 72 0.5 {UUID:[I;'
        + ",".join(map(str, uuid_parts(TARGET)))
        + '],PersistenceRequired:1b,CanPickUpLoot:0b,CustomName:\'{"text":"Sentinel"}\',CustomNameVisible:1b}',
        "save-all flush",
    ]
    receipts = []
    try:
        await server.start()
        for command in commands:
            lines = await server.command(command)
            if any("Unknown" in line or "Incorrect" in line or "Error" in line for line in lines):
                raise RuntimeError(f"Fixture command rejected: {command}: {lines}")
            receipts.append({"command": command, "feedback": lines})
        lines = await server.command(f"data get entity {TARGET}")
        if not any("has the following entity data:" in line for line in lines):
            raise RuntimeError("Authored sentinel is not loaded")
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
    registry = {"schema": SCHEMA, "target_uuid": str(TARGET), "target_type": "minecraft:husk",
                "target_position": [28.5, 72, 0.5], "return_position": [0.5, 72, 0.5],
                "pack_sha256": pack_hashes(world)}
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
    arguments = parser.parse_args()
    print(asyncio.run(author(arguments.source, arguments.output)))
