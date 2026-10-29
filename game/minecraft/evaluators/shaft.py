"""An actual ascent, original service cargo and a final supported return route."""

from collections import deque
import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.cargo import evaluate_cargo, validate_cargo
from game.minecraft.evaluators.world import AIR, _chunk, read_blocks, region_bounds
from game.minecraft.fixtures.shaft import SCHEMA, expected_hashes


SUPPORT = {
    "minecraft:stone", "minecraft:cobblestone", "minecraft:dirt", "minecraft:grass_block",
    "minecraft:oak_planks", "minecraft:stone_bricks", "minecraft:yellow_wool", "minecraft:bedrock",
    "minecraft:cobblestone_stairs", "minecraft:stone_brick_stairs",
    "minecraft:andesite", "minecraft:diorite", "minecraft:granite",
    "minecraft:deepslate", "minecraft:cobbled_deepslate", "minecraft:glass",
    "minecraft:terracotta", "minecraft:bamboo_mosaic",
    "minecraft:crimson_stem", "minecraft:warped_stem",
}
SUPPORT_FAMILIES = (
    "_planks", "_log", "_wood", "_hyphae", "_bricks", "_stairs",
    "_wool", "_terracotta", "_concrete", "_ore", "_glass", "_leaves",
)
PASSABLE = AIR | {
    "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch",
    "minecraft:soul_wall_torch", "minecraft:redstone_torch",
    "minecraft:redstone_wall_torch", "minecraft:redstone_wire",
    "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
    "minecraft:large_fern", "minecraft:dead_bush", "minecraft:vine",
    "minecraft:glow_lichen",
}


def supports_feet(name):
    return name in SUPPORT or (
        isinstance(name, str) and name.startswith("minecraft:") and name.endswith(SUPPORT_FAMILIES)
    )


def ladder_support(world, point):
    x, y, z = point
    chunk = _chunk(world / "region", x // 16, z // 16)
    section = next(row for row in chunk["sections"] if int(row["Y"]) == y // 16)
    states = section["block_states"]
    palette = states["palette"]
    index = (y % 16) * 256 + (z % 16) * 16 + x % 16
    bits = max(4, (len(palette) - 1).bit_length())
    per_long = 64 // bits
    entry = palette[0 if len(palette) == 1 else
                    (int(states["data"][index // per_long]) >> ((index % per_long) * bits)) & ((1 << bits) - 1)]
    facing = str(entry["Properties"]["facing"])
    dx, dz = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}[facing]
    return x + dx, y, z + dz


def supported_route(blocks, ladders, start, end):
    def clear(point):
        return blocks.get(point) in PASSABLE or point in ladders

    def standing(point):
        x, y, z = point
        return clear(point) and clear((x, y+1, z)) and (
            point in ladders or supports_feet(blocks.get((x, y-1, z)))
        )

    if not standing(start) or not standing(end):
        return False
    seen, pending = {start}, deque([start])
    while pending:
        x, y, z = point = pending.popleft()
        if point == end:
            return True
        choices = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (-1, 0, 1):
                target = x+dx, y+dy, z+dz
                if dy == 1 and not clear((x, y+2, z)):
                    continue
                if dy == -1 and not clear((x+dx, y+1, z+dz)):
                    continue
                choices.append(target)
        if point in ladders:
            choices += [(x, y-1, z), (x, y+1, z)]
        for target in choices:
            if target not in seen and standing(target):
                seen.add(target)
                pending.append(target)
    return False


def visits(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-shaft.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Shaft observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_shaft" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Shaft observer changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Shaft evidence requires Minecraft 1.20.4")
    record = native["data"]["contents"]["shaft"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Shaft observer identity changed")
    return [{"player": list(map(int, row["player"])), "tick": int(row["tick"])} for row in record["visits"]]


def validate_shaft(*, cargo, position, route_region):
    validate_cargo(cargo=cargo, position=position)
    region_bounds(route_region, "minecraft:overworld")


def evaluate_shaft(before: Path, after: Path, player: UUID, *, cargo, position, route_region):
    validate_shaft(cargo=cargo, position=position, route_region=route_region)
    if visits(before):
        raise ValueError("Shaft ascent history must start empty")
    record = visits(after)
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if any(row["player"] != identity or not first <= row["tick"] <= last for row in record):
        raise ValueError("Invalid native shaft visit identity or clock")
    low, high = region_bounds(route_region, "minecraft:overworld")
    blocks = read_blocks(after, low, high, "minecraft:overworld")
    ladders = {point for point, name in blocks.items()
               if name == "minecraft:ladder" and supports_feet(blocks.get(ladder_support(after, point)))}
    route = supported_route(blocks, ladders, (0, 62, -3), (10, 69, 5))
    result = evaluate_cargo(before, after, player, cargo=cargo, position=position)
    result["checks"].extend([
        {"kind": "native_upper_landing_ascent", "passed": bool(record)},
        {"kind": "final_supported_two_way_route", "passed": route},
    ])
    result["success"] = all(row["passed"] for row in result["checks"])
    result["ascent_visits"] = record
    result["semantics"] += (
        " Final two-high clearance, supported ladders and one-block step connections must still connect "
        "the bottom and service passage. Earlier motion alone and subsequently removed pillaring do not pass."
    )
    return result
