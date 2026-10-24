"""Add a crop plot, repairable crossing and passive action evidence to the forge save."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.expedition import registry
from game.minecraft.fixtures.forge_hunt import SCHEMA, uuid_parts
from game.minecraft.fixtures.lost_expedition import chest
from game.minecraft.runtime.install import check_java, server_jar
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.runtime.session import WorldReadLock, validate_world


ACTION_SCHEMA = "minecraft-action-sequence/1"
ARCHER = UUID("25779341-e6b1-4330-998f-a62372be8be6")


def action_pack() -> dict[str, str | dict]:
    files: dict[str, str | dict] = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native block and damage ordering"}},
    }
    for kind, trigger, conditions in (
        ("block", "entity_hurt_player", {"damage": {"blocked": True, "type": {
            "direct_entity": {"type": "minecraft:husk"},
        }}}),
        ("damage", "player_hurt_entity", {"damage": {"taken": {"min": 0.1}}, "entity": {"type": "minecraft:husk"}}),
    ):
        files[f"data/livequest_actions/advancements/{kind}.json"] = {
            "criteria": {"effect": {"trigger": "minecraft:" + trigger, "conditions": conditions}},
            "rewards": {"function": "livequest_actions:" + kind},
        }
        files[f"data/livequest_actions/functions/{kind}.mcfunction"] = "\n".join([
            f'data modify storage livequest:actions events append value {{kind:"{kind}"}}',
            "data modify storage livequest:actions events[-1].player set from entity @s UUID",
            "execute store result storage livequest:actions events[-1].tick long 1 run time query gametime",
            f"advancement revoke @s only livequest_actions:{kind}",
        ]) + "\n"
    return files


def action_hashes(world: Path) -> dict[str, str]:
    return {name: hashlib.sha256((world / "datapacks/livequest_actions" / name).read_bytes()).hexdigest()
            for name in action_pack()}


def commands() -> list[str]:
    result = [
        "tick freeze", "forceload add -16 -16 47 31",
        "fill -12 64 14 14 71 26 stone",
        "fill -12 72 14 14 82 26 air",
        "fill -12 71 14 14 71 26 grass_block",
        "fill 2 68 16 5 71 22 air",
        "fill 24 72 -4 32 74 -4 stone_bricks",
        "fill 24 72 4 32 74 4 stone_bricks",
        "fill 24 72 -3 24 74 3 stone_bricks",
        "fill 32 72 -3 32 74 3 stone_bricks",
        "setblock 0 71 19 yellow_wool", "setblock 7 71 19 white_wool",
        "setblock -9 71 5 water", "setblock -3 71 5 water",
        "setblock -9 71 2 white_wool", "setblock -3 71 2 white_wool",
        "setblock -9 71 8 white_wool", "setblock -3 71 8 white_wool",
        f'data modify storage livequest:actions schema set value "{ACTION_SCHEMA}"',
        "data modify storage livequest:actions events set value []",
    ]
    for x in range(-8, -3):
        for z in range(3, 8):
            result.extend([f"setblock {x} 71 {z} farmland[moisture=7]",
                           f"setblock {x} 72 {z} wheat[age=7]"])
    result.extend(chest(10, 72, 19, [("gold_nugget", 1, "Delivery token", "")]))
    result.append("save-all flush")
    return result


def planning_commands() -> list[str]:
    native_uuid = "[I;" + ",".join(map(str, uuid_parts(ARCHER))) + "]"
    return [
        "forceload add -16 16 79 79",
        "fill -12 64 12 16 71 68 stone",
        "fill -12 72 12 16 82 68 air",
        "fill -12 71 12 16 71 68 grass_block",
        "fill 2 64 14 9 71 64 air",
        "setblock 0 71 39 yellow_wool",
        "setblock -6 71 39 white_wool",
        "setblock 14 71 39 white_wool",
        *chest(12, 72, 39, [("gold_nugget", 1, "Crossing cargo", "")]),
        "fill 52 64 18 76 71 36 stone",
        "fill 52 72 18 76 82 36 air",
        "fill 52 71 18 76 71 36 grass_block",
        "fill 56 72 20 74 75 34 stone_bricks hollow",
        "fill 57 72 21 73 72 33 air",
        "fill 56 72 26 56 74 28 air",
        "fill 60 72 24 60 74 24 stone_bricks",
        "fill 60 72 30 60 74 30 stone_bricks",
        "setblock 54 71 27 yellow_wool",
        *chest(72, 72, 27, [("amethyst_shard", 1, "Guarded cargo", "")]),
        'summon minecraft:skeleton 66.5 72 27.5 {UUID:' + native_uuid
        + ',PersistenceRequired:1b,HandItems:[{id:"minecraft:bow",Count:1b},{}],'
        + 'CustomName:\'{"text":"Cache Archer"}\',CustomNameVisible:1b}',
    ]


async def author(source: Path, output: Path, *, planning: bool = False) -> Path:
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    if registry(source)["schema"] != SCHEMA:
        raise ValueError("Workshop author requires the published single-target forge world")
    output.mkdir(parents=True, exist_ok=False)
    world = output / "world"
    with WorldReadLock(source):
        source_hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(source.rglob("*")) if p.is_file() and p.name != "session.lock"}
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
    for name, value in action_pack().items():
        path = world / "datapacks/livequest_actions" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")
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
        enabled = await server.command("datapack list enabled")
        if not any("livequest_actions" in line for line in enabled):
            raise RuntimeError("Passive action datapack was not enabled")
        authored = commands()
        if planning:
            authored[-1:-1] = planning_commands()
        for command in authored:
            feedback = await server.command(command)
            if any(word in line for line in feedback for word in ("Unknown", "Incorrect", "Error")):
                raise RuntimeError(f"Workshop command rejected: {command}: {feedback}")
            receipts.append({"command": command, "feedback": feedback})
        if planning:
            command = f"data get entity {ARCHER}"
            feedback = await server.command(command)
            rows = [nbtlib.parse_nbt(line.split("has the following entity data: ", 1)[1])
                    for line in feedback if "has the following entity data: " in line]
            if (len(rows) != 1 or float(rows[0]["Health"]) != 20
                    or bool(rows[0].get("NoAI", False)) or bool(rows[0].get("Invulnerable", False))
                    or str(rows[0]["HandItems"][0]["id"]) != "minecraft:bow"):
                raise RuntimeError("Planning archer must have native health, AI and bow equipment")
            receipts.append({"command": command, "feedback": feedback})
    finally:
        await server.stop()
    for name in ("level.dat", "level.dat_old"):
        path = world / name
        if path.exists():
            native = nbtlib.load(path)
            if native["Data"].get("Player"):
                raise RuntimeError("Workshop authoring unexpectedly created player data")
            native["Data"].pop("Player", None)
            native.save(path)
    (world / "livequest-action-evidence.json").write_text(json.dumps({
        "schema": ACTION_SCHEMA, "pack_sha256": action_hashes(world),
    }, indent=2) + "\n")
    manifest = {
        "schema": "livequest-workshop-source/1", "minecraft_version": "1.20.4",
        "source": str(source), "source_sha256": source_hashes,
        "author": "game/minecraft/fixtures/workshop.py",
        "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commands": receipts,
        "scope": "Initial native farm/crossing/chest and sentinel-yard overlay, with passive action ordering. "
                 "Original target identity, AI, health and ordinary gameplay rules are unchanged.",
        "fixture_sha256": {str(p.relative_to(world)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(world.rglob("*"))
                           if p.is_file() and p.name not in ("session.lock", "level.dat_old")},
        "export_exclusions": ["session.lock", "level.dat_old"],
    }
    if planning:
        manifest["variant"] = "planning"
        manifest["scope"] = (
            "Workshop plus an eight-block-wide trench with ground detours and a separate roofed "
            "bow-equipped Skeleton cache. Native health, AI, prices and gameplay rules are unchanged."
        )
    (output / "source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validate_world(world)
    return world


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--planning", action="store_true")
    args = parser.parse_args()
    print(asyncio.run(author(args.source, args.output, planning=args.planning)))
