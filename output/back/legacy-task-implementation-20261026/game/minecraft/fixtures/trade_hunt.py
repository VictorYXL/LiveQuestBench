"""Author a native villager economy over the isolated two-outpost fixture."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

import nbtlib

from game.minecraft.fixtures.forge_hunt import OUTPOST_SCHEMA, pack_files as combat_files, uuid_parts
from game.minecraft.runtime.install import check_java, server_jar
from game.minecraft.runtime.server import MinecraftServer
from game.minecraft.runtime.session import WorldReadLock, validate_world


SCHEMA = "minecraft-trade-hunt/1"
SMITH = "624fda3c-ac53-4693-9bdc-28b2e310ed88"
FARMER = "250641fc-09bf-4342-a8b3-42bf6d7f7ed1"
MERCHANTS = [
    {"role": "weaponsmith", "uuid": SMITH, "type": "minecraft:villager", "position": [8.5, 72, 4.5], "health": 20},
    {"role": "farmer", "uuid": FARMER, "type": "minecraft:villager", "position": [4.5, 72, 4.5], "health": 20},
]


def offers(role: str) -> nbtlib.List:
    specs = {
        "weaponsmith": [("coal", 15, "emerald", 1, 16, 2, .05),
                       ("emerald", 3, "iron_axe", 1, 12, 1, .2)],
        "farmer": [("wheat", 20, "emerald", 1, 16, 2, .05),
                   ("emerald", 1, "bread", 6, 16, 1, .05)],
    }[role]
    result = nbtlib.List[nbtlib.Compound]([
        nbtlib.Compound({
            "buy": nbtlib.Compound({"id": nbtlib.String("minecraft:" + buy), "Count": nbtlib.Byte(cost)}),
            "sell": nbtlib.Compound({"id": nbtlib.String("minecraft:" + sell), "Count": nbtlib.Byte(amount)}),
            "uses": nbtlib.Int(0), "maxUses": nbtlib.Int(stock), "xp": nbtlib.Int(xp),
            "priceMultiplier": nbtlib.Float(multiplier),
            "rewardExp": nbtlib.Byte(1),
            "demand": nbtlib.Int(0), "specialPrice": nbtlib.Int(0),
        }) for buy, cost, sell, amount, stock, xp, multiplier in specs
    ])
    for offer in result:
        if str(offer["sell"]["id"]) == "minecraft:iron_axe":
            offer["sell"]["tag"] = nbtlib.Compound({"Damage": nbtlib.Int(0)})
    return result


def pack_files() -> dict[str, object]:
    files = combat_files(2)
    for role in ("sentinel", "spider"):
        key = f"data/livequest/functions/{role}.mcfunction"
        function = files[key]
        assert isinstance(function, str)
        files[key] = ("scoreboard players add #sequence lq_event 1\n" + function
                      + "execute store result storage livequest:expedition kills[-1].sequence int 1 "
                      "run scoreboard players get #sequence lq_event\n")
    native_uuid = "[I;" + ",".join(map(str, uuid_parts(UUID(SMITH)))) + "]"
    files["data/livequest/advancements/weapon_purchase.json"] = {
        "criteria": {"purchase": {"trigger": "minecraft:villager_trade", "conditions": {
            "villager": {"type": "minecraft:villager", "nbt": "{UUID:" + native_uuid + "}"},
            "item": {"items": ["minecraft:iron_axe"]},
        }}},
        "rewards": {"function": "livequest:weapon_purchase"},
    }
    files["data/livequest/functions/weapon_purchase.mcfunction"] = "\n".join([
        "scoreboard players add #sequence lq_event 1",
        'data modify storage livequest:expedition purchases append value {item:"minecraft:iron_axe",merchant:"' + SMITH + '"}',
        "data modify storage livequest:expedition purchases[-1].player set from entity @s UUID",
        "execute store result storage livequest:expedition purchases[-1].tick long 1 run time query gametime",
        "execute store result storage livequest:expedition purchases[-1].sequence int 1 run scoreboard players get #sequence lq_event",
    ]) + "\n"
    return files


def pack_hashes(world: Path) -> dict[str, str]:
    return {name: hashlib.sha256((world / "datapacks/livequest_forge" / name).read_bytes()).hexdigest()
            for name in pack_files()}


async def author(source: Path, output: Path) -> Path:
    if os.environ.get("MINECRAFT_EULA_ACCEPTED") != "true":
        raise PermissionError("Explicit Minecraft EULA acceptance is required")
    validate_world(source)
    registry = json.loads((source / "livequest-expedition.json").read_text())
    from game.minecraft.fixtures.forge_hunt import pack_hashes as combat_hashes
    if registry["schema"] != OUTPOST_SCHEMA or registry["pack_sha256"] != combat_hashes(source, 2):
        raise ValueError("Trade authoring requires the unchanged two-outpost source fixture")
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
        "difficulty=easy\nenable-rcon=false\nenable-query=false\n"
    )
    commands = [
        "tick freeze",
        "scoreboard objectives add lq_event dummy",
        "scoreboard players set #sequence lq_event 0",
        f'data modify storage livequest:expedition state.schema set value "{SCHEMA}"',
        "data modify storage livequest:expedition purchases set value []",
        "setblock 50 72 5 air",
    ]
    for merchant in MERCHANTS:
        x, y, z = map(int, merchant["position"])
        commands.extend([
            f"fill {x-1} {y} {z-1} {x+1} {y+2} {z+1} stone_bricks hollow",
            f"setblock {x} {y} {z} air",
            f"setblock {x} {y+1} {z} air",
            f"setblock {x} {y+1} {z-1} air",
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
        commands.append("summon minecraft:villager " + " ".join(map(str, merchant["position"])) + " " + data.snbt())
    commands.append("save-all flush")
    server = MinecraftServer(output, server_jar(), check_java(), 2048, 0, 120, 30)
    receipts = []
    try:
        await server.start()
        for command in commands:
            lines = await server.command(command)
            if any("Unknown" in line or "Incorrect" in line or "Error" in line for line in lines):
                raise RuntimeError(f"Trade fixture command rejected: {command}: {lines}")
            receipts.append({"command": command, "feedback": lines})
        for merchant in MERCHANTS:
            lines = await server.command(f"data get entity {merchant['uuid']}")
            rows = [nbtlib.parse_nbt(line.split("has the following entity data: ", 1)[1])
                    for line in lines if "has the following entity data: " in line]
            if len(rows) != 1 or float(rows[0]["Health"]) != 20:
                raise RuntimeError("Authored native merchant is missing or injured")
            for actual, required in zip(rows[0]["Offers"]["Recipes"], offers(merchant["role"]), strict=True):
                if any(actual[key] != value for key, value in required.items()):
                    raise RuntimeError("Native merchant readback differs from the selected vanilla offer")
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
    registry.update(schema=SCHEMA, merchants=MERCHANTS, pack_sha256=pack_hashes(world))
    (world / "livequest-expedition.json").write_text(json.dumps(registry, indent=2) + "\n")
    manifest = {
        "schema": "livequest-trade-hunt-source/1", "minecraft_version": "1.20.4",
        "source": str(source), "source_sha256": source_hashes,
        "author": "game/minecraft/fixtures/trade_hunt.py",
        "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commands": commands, "registry": registry,
        "scope": "Selected vanilla novice offers, native transactions, physical stalls; no AI disabling or invulnerability.",
        "restocking": "No reachable job sites; initial stock and funding are finite. Xp=1 retains professions.",
        "offer_basis": "Pinned 1.20.4 TradeOffers factories: weaponsmith coal 15:1 and axe 3:1; farmer wheat 20:1 and bread 1:6.",
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
