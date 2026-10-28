"""Connectivity of a declared level full-block deck with two blocks of headroom."""

from collections import deque
from pathlib import Path

from game.minecraft.evaluators.world import AIR, read_blocks, region_bounds


DECK_BLOCKS = frozenset({"minecraft:oak_planks", "minecraft:cobblestone", "minecraft:stone",
                         "minecraft:stone_bricks", "minecraft:yellow_wool", "minecraft:grass_block"})


def validate_crossing(*, region: dict, start: list[int], end: list[int]) -> None:
    low, high = region_bounds(region, "minecraft:overworld")
    if high[1] != low[1] + 2:
        raise ValueError("Crossing region must include one deck level and two headroom levels")
    for point in (start, end):
        if (not isinstance(point, list) or len(point) != 3 or any(type(v) is not int for v in point)
                or point[1] != low[1] or any(not low[i] <= point[i] <= high[i] for i in range(3))):
            raise ValueError("Crossing endpoints must be deck cells inside the declared region")
    if start == end:
        raise ValueError("Crossing endpoints must differ")


def connected(blocks: dict, *, region: dict, start: list[int], end: list[int]) -> bool:
    low, high = region["min"], region["max"]
    y = low[1]
    walkable = {
        (x, y, z) for x in range(low[0], high[0] + 1) for z in range(low[2], high[2] + 1)
        if blocks[x, y, z] in DECK_BLOCKS
        and all(blocks[x, y + dy, z] in AIR for dy in (1, 2))
    }
    if tuple(start) not in walkable or tuple(end) not in walkable:
        return False
    reached, queue = {tuple(start)}, deque([tuple(start)])
    while queue:
        x, y, z = queue.popleft()
        for point in ((x - 1, y, z), (x + 1, y, z), (x, y, z - 1), (x, y, z + 1)):
            if point in walkable and point not in reached:
                reached.add(point)
                queue.append(point)
    return tuple(end) in reached


def evaluate_crossing(before: Path, after: Path, **goal) -> dict:
    validate_crossing(**goal)
    low, high = region_bounds(goal["region"], "minecraft:overworld")
    initial = read_blocks(before, low, high, "minecraft:overworld")
    final = read_blocks(after, low, high, "minecraft:overworld")
    was_connected = connected(initial, **goal)
    is_connected = connected(final, **goal)
    return {
        "success": is_connected and not was_connected,
        "initially_connected": was_connected, "finally_connected": is_connected,
        "semantics": "A new cardinally connected level deck of declared full blocks, with two air "
                     "blocks above every path cell. Any path within the public construction area "
                     "is accepted; no canonical bridge or contributor quota.",
    }
