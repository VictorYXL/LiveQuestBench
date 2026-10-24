"""Author a discoverable expedition over the unchanged native resource island."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

import nbtlib

from game.minecraft.fixtures.forge_hunt import TARGET, pack_files, pack_hashes, uuid_parts
from game.minecraft.fixtures.trade_hunt import MERCHANTS as TRADE_MERCHANTS, offers
from game.minecraft.runtime.install import check_java, server_jar
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.runtime.session import WorldReadLock, validate_world


SCHEMA = "minecraft-lost-expedition/1"
FOLIOS = ("route_survey", "mineral_survey", "archive_ledger")
TARGETS = [{"role": "sentinel", "uuid": str(TARGET), "type": "minecraft:husk",
            "position": [76.5, 72, -51.5], "health": 20}]
MERCHANTS = [
    {**merchant, "position": [x, 72, 48.5]}
    for merchant, x in zip(TRADE_MERCHANTS, (-18.5, -24.5), strict=True)
]


def chest(x: int, y: int, z: int, entries: list[tuple[str, int, str, str]]) -> list[str]:
    items = []
    for slot, (item, count, title, folio) in enumerate(entries):
        tag = nbtlib.Compound()
        if title:
            tag["display"] = nbtlib.Compound({"Name": nbtlib.String(json.dumps({"text": title, "italic": False}))})
        if folio:
            tag["livequest_folio"] = nbtlib.String(folio)
        items.append(nbtlib.Compound({
            "Slot": nbtlib.Byte(slot), "id": nbtlib.String("minecraft:" + item),
            "Count": nbtlib.Byte(count), "tag": tag,
        }))
    data = nbtlib.Compound({"Items": nbtlib.List[nbtlib.Compound](items)})
    return [f"setblock {x} {y} {z} chest", f"data merge block {x} {y} {z} {data.snbt()}"]


def commands() -> list[str]:
    result = [
        "tick freeze", "gamerule doMobSpawning true", "gamerule doDaylightCycle true",
        "gamerule doWeatherCycle false", "gamerule doTraderSpawning false",
        "gamerule naturalRegeneration true", "gamerule keepInventory false",
        "gamerule commandBlockOutput false", "gamerule sendCommandFeedback false",
        "time set 0", "weather clear", "forceload add -80 -80 95 63",
        "scoreboard objectives add lq_stone minecraft.crafted:minecraft.stone_sword",
        "scoreboard objectives add lq_iron minecraft.crafted:minecraft.iron_sword",
        f'data modify storage livequest:expedition state set value {{schema:"{SCHEMA}",target:"{TARGET}"}}',
        "data modify storage livequest:expedition kills set value []",
        "setblock 0 71 0 yellow_wool",
    ]
    for x, z, color in ((-52, 48, "white"), (64, 40, "red"), (-60, -48, "green"), (76, -60, "black")):
        result.extend([
            f"fill {x-9} 64 {z-9} {x+9} 71 {z+9} stone",
            f"fill {x-9} 72 {z-9} {x+9} 86 {z+9} air",
            f"fill {x-9} 71 {z-9} {x+9} 71 {z+9} grass_block",
            f"fill {x-8} 72 {z-8} {x-8} 80 {z-8} oak_log",
            f"fill {x-9} 81 {z-9} {x-7} 81 {z-7} {color}_wool",
        ])
        for step in range(1, 9):
            result.extend([
                f"fill {x-1} {72-step} {z-9-step} {x+1} 78 {z-9-step} air",
                f"fill {x-1} {71-step} {z-9-step} {x+1} {71-step} {z-9-step} stone_bricks",
            ])
    result.extend([
        "fill -57 72 43 -47 76 53 oak_planks hollow",
        "fill -57 77 43 -47 77 53 white_wool",
        "fill -53 72 43 -52 73 43 air",
        "setblock -55 72 45 crafting_table", "setblock -54 72 45 furnace",
        "setblock -55 72 51 torch", "setblock -49 72 45 torch",
    ])
    result.extend(chest(-52, 72, 48, [
        ("paper", 1, "Route Survey", FOLIOS[0]),
        ("paper", 1, "Red quarry: east shore, X64 Z40", ""),
        ("paper", 1, "Green mine: northwest ridge, X-60 Z-48", ""),
        ("bread", 4, "", ""),
    ]))
    result.extend(chest(64, 72, 40, [
        ("paper", 1, "Archive relocated: black ridge X76 Z-60", ""),
        ("paper", 1, "Vault shell: obsidian, three blocks thick", ""),
        ("paper", 1, "Mineral Survey remains below green mine", ""),
        ("bread", 2, "", ""),
    ]))
    result.extend([
        "fill -64 72 -52 -56 74 -44 stone_bricks hollow",
        "fill -61 72 -44 -60 73 -44 air",
        "fill -62 20 -50 -58 22 -46 air",
        "fill -63 19 -51 -57 19 -45 stone_bricks",
    ])
    result.extend(chest(-60, 72, -47, [
        ("paper", 1, "Mine log: survey chamber directly below Y20", ""),
        ("paper", 1, "Hard-gem seams occur below Y-40", ""),
        ("torch", 12, "", ""),
    ]))
    result.extend(chest(-60, 20, -48, [
        ("paper", 1, "Mineral Survey", FOLIOS[1]),
        ("paper", 1, "Archive Sentinel roams outside the black vault", ""),
        ("paper", 1, "Blue market trades coal and wheat for emeralds", ""),
    ]))
    result.extend([
        "fill 72 69 -64 80 77 -56 obsidian",
        "fill 75 72 -61 77 74 -59 air",
        "fill 67 72 -69 85 74 -69 stone_bricks",
        "fill 67 72 -43 85 74 -43 stone_bricks",
        "fill 67 72 -68 67 74 -44 stone_bricks",
        "fill 85 72 -68 85 74 -44 stone_bricks",
        "fill 68 64 -55 84 71 -43 stone",
        "fill 74 72 -43 78 74 -43 air",
    ])
    result.extend(chest(76, 72, -60, [("paper", 1, "Archive Ledger", FOLIOS[2])]))
    for merchant in MERCHANTS:
        x, y, z = map(int, merchant["position"])
        result.extend([
            f"fill {x-2} 64 {z-2} {x+2} 71 {z+2} stone",
            f"fill {x-2} 72 {z-2} {x+2} 79 {z+2} air",
            f"fill {x-1} {y} {z-1} {x+1} {y+2} {z+1} stone_bricks hollow",
            f"setblock {x} {y} {z} air", f"setblock {x} {y+1} {z} air",
            f"setblock {x} {y+1} {z-1} air",
            f"fill {x-1} 75 {z-1} {x+1} 75 {z+1} blue_wool",
        ])
        for step in range(1, 9):
            result.extend([
                f"fill {x} {72-step} {z-2-step} {x} 77 {z-2-step} air",
                f"setblock {x} {71-step} {z-2-step} stone_bricks",
            ])
        data = nbtlib.Compound({
            "UUID": nbtlib.IntArray(uuid_parts(UUID(merchant["uuid"]))),
            "PersistenceRequired": nbtlib.Byte(1), "Xp": nbtlib.Int(1),
            "VillagerData": nbtlib.Compound({
                "profession": nbtlib.String("minecraft:" + merchant["role"]),
                "type": nbtlib.String("minecraft:plains"), "level": nbtlib.Int(1),
            }),
            "CustomName": nbtlib.String(json.dumps({"text": merchant["role"].title()})),
            "CustomNameVisible": nbtlib.Byte(1),
            "Offers": nbtlib.Compound({"Recipes": offers(merchant["role"])}),
        })
        result.append("summon minecraft:villager " + " ".join(map(str, merchant["position"])) + " " + data.snbt())
    enemy = TARGETS[0]
    result.append("summon minecraft:husk " + " ".join(map(str, enemy["position"])) + " "
                  + "{UUID:[I;" + ",".join(map(str, uuid_parts(TARGET)))
                  + '],PersistenceRequired:1b,CanPickUpLoot:0b,CustomName:\'{"text":"Archive Sentinel"}\',CustomNameVisible:1b}')
    result.append("save-all flush")
    return result


async def author(source: Path, output: Path) -> Path:
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    output.mkdir(parents=True, exist_ok=False)
    world = output / "world"
    with WorldReadLock(source):
        source_hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(source.rglob("*")) if p.is_file() and p.name != "session.lock"}
        shutil.copytree(source, world, ignore=shutil.ignore_patterns("session.lock", "level.dat_old"))
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
    receipts = []
    try:
        await server.start()
        for command in commands():
            lines = await server.command(command)
            if any(word in line for line in lines for word in ("Unknown", "Incorrect", "Error")):
                raise RuntimeError(f"Expedition authoring command rejected: {command}: {lines}")
            receipts.append({"command": command, "feedback": lines})
        for entity in TARGETS + MERCHANTS:
            lines = await server.command(f"data get entity {entity['uuid']}")
            values = [nbtlib.parse_nbt(line.split("has the following entity data: ", 1)[1])
                      for line in lines if "has the following entity data: " in line]
            if len(values) != 1 or float(values[0]["Health"]) != entity["health"]:
                raise RuntimeError(f"Authored native entity missing or injured: {entity['role']}")
    finally:
        await server.stop()
    level = world / "level.dat"
    data = nbtlib.load(level)
    if data["Data"].get("Player"):
        raise RuntimeError("Authoring unexpectedly created nonempty player data")
    data["Data"].pop("Player", None)
    data.save(level)
    registry = {
        "schema": SCHEMA, "target_uuid": str(TARGET), "target_type": "minecraft:husk",
        "target_position": TARGETS[0]["position"], "targets": TARGETS,
        "merchants": MERCHANTS, "folios": list(FOLIOS),
        "return_position": [.5, 72, .5], "pack_sha256": pack_hashes(world),
    }
    (world / "livequest-expedition.json").write_text(json.dumps(registry, indent=2) + "\n")
    manifest = {
        "schema": "livequest-lost-expedition-source/1", "minecraft_version": "1.20.4",
        "source": str(source), "source_sha256": source_hashes,
        "author": "game/minecraft/fixtures/lost_expedition.py",
        "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commands": commands(), "registry": registry,
        "scope": "Initial native blocks, named chest items and ordinary entities only. Passive kill evidence; no play-time assistance.",
        "clues": "Ordinary item display names, visible in container UI/hover and the existing ST item description.",
        "dynamics": "Native mob spawning, day cycle, hunger, durability and ordinary persistent enemy AI; no scripted map changes.",
        "trade_offers": "Reuses previously verified Java 1.20.4 novice weaponsmith/farmer offers; no new prices or restocking helpers.",
        "fixture_sha256": {str(p.relative_to(world)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(world.rglob("*")) if p.is_file() and p.name not in ("session.lock", "level.dat_old")},
        "export_exclusions": ["session.lock", "level.dat_old"],
    }
    (output / "source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "authoring-receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return world


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(asyncio.run(author(args.source, args.output)))
