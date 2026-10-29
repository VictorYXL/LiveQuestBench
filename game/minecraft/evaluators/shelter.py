"""Blueprint shelter scoring including a usable two-high entrance."""

from collections import deque
from pathlib import Path
from uuid import UUID

from game.minecraft.evaluators.state import evaluate_state, validate_state
from game.minecraft.evaluators.world import AIR, read_blocks


SUPPORT = {
    "minecraft:stone", "minecraft:cobblestone", "minecraft:oak_planks", "minecraft:grass_block",
    "minecraft:dirt", "minecraft:yellow_wool", "minecraft:blue_wool", "minecraft:white_wool",
    "minecraft:gold_block",
}


def connected(blocks: dict, start: tuple, targets: set[tuple]) -> bool:
    """Check a standing route with native one-block steps and body clearance."""
    def open_cell(point):
        return blocks.get(point) in AIR

    def standable(point):
        x, y, z = point
        support = blocks.get((x, y - 1, z))
        return (open_cell(point) and open_cell((x, y + 1, z))
                and support in SUPPORT)

    if not standable(start):
        return False
    pending, seen = deque([start]), {start}
    while pending:
        point = pending.popleft()
        if point in targets:
            return True
        x, y, z = point
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                next_point = x + dx, y + dy, z + dz
                if next_point in seen or not standable(next_point):
                    continue
                if dy == 1 and not open_cell((x, y + 2, z)):
                    continue
                if dy == -1 and not open_cell((x + dx, y + 1, z + dz)):
                    continue
                seen.add(next_point)
                pending.append(next_point)
    return False


def evaluate_shelter(before: Path, after: Path, player: UUID, *, structure: dict, position: dict) -> dict:
    validate_state(structure=structure, position=position)
    result = evaluate_state(before, after, player, structure=structure, position=position)
    x, y, z = structure["region"]["min"]
    blocks = read_blocks(after, (x - 4, y - 1, z - 5), (x + 7, y + 4, z + 7),
                         "minecraft:overworld")
    entrance = (x + 1, y + 1, z + 1)
    start = tuple(int(v // 1) for v in position["target"])
    usable = connected(blocks, start, {entrance})
    result["checks"].append({"kind": "accessible_entrance", "passed": usable})
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += " The finished shelter must have a two-high standing route from the outside marker."
    return result
