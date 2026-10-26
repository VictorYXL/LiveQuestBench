"""Original native chest cargo and settled return, without prescribed routes."""

from pathlib import Path
import re
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state, validate_state
from game.minecraft.evaluators.world import read_block_entity


def validate_cargo(*, cargo: list[dict], position: dict) -> None:
    validate_state(position=position)
    if not isinstance(cargo, list) or not cargo:
        raise ValueError("Cargo must be a nonempty list")
    identifiers, chests = set(), set()
    for row in cargo:
        if not isinstance(row, dict) or set(row) != {"id", "item", "chest"}:
            raise ValueError("Cargo requires id, item and initial chest coordinates")
        if not isinstance(row["id"], str) or not re.fullmatch(r"[a-z0-9_]+", row["id"]):
            raise ValueError("Invalid cargo identity")
        if not isinstance(row["item"], str) or not re.fullmatch(r"minecraft:[a-z0-9_]+", row["item"]):
            raise ValueError("Cargo requires a namespaced native item")
        point = row["chest"]
        if not isinstance(point, list) or len(point) != 3 or any(type(v) is not int for v in point):
            raise ValueError("Cargo chest requires integer XYZ")
        if not -64 <= point[1] < 320 or any(abs(point[i]) >= 30000000 for i in (0, 2)):
            raise ValueError("Cargo chest is outside the Overworld bounds")
        if row["id"] in identifiers or tuple(point) in chests:
            raise ValueError("Cargo identities and initial chests must be distinct")
        identifiers.add(row["id"])
        chests.add(tuple(point))


def cargo_count(stacks: nbtlib.List, row: dict) -> int:
    count = 0
    for stack in stacks:
        if str(stack.get("tag", {}).get("livequest_cargo", "")) == row["id"]:
            if str(stack["id"]) != row["item"] or int(stack["Count"]) <= 0:
                raise ValueError("Native cargo item or count disagrees with its identity")
            count += int(stack["Count"])
    return count


def player_inventory(world: Path, player: UUID) -> nbtlib.List:
    native = nbtlib.load(world / "playerdata" / f"{player}.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Cargo scoring requires Minecraft Java 1.20.4")
    return native["Inventory"]


def verify_initial_cargo(before: Path, player: UUID, *, cargo: list[dict], position: dict) -> None:
    validate_cargo(cargo=cargo, position=position)
    stacks = player_inventory(before, player)
    for row in cargo:
        chest = read_block_entity(before, tuple(row["chest"]))
        if str(chest["id"]) != "minecraft:chest" or cargo_count(chest["Items"], row) != 1:
            raise ValueError(f"Original cargo is missing or duplicated at its initial chest: {row['id']}")
        if cargo_count(stacks, row):
            raise ValueError("Task cargo must not be supplied in the initial player inventory")


def evaluate_cargo(before: Path, after: Path, player: UUID, *, cargo: list[dict], position: dict) -> dict:
    verify_initial_cargo(before, player, cargo=cargo, position=position)
    result = evaluate_state(before, after, player, position=position)
    stacks = player_inventory(after, player)
    checks = [
        {"kind": "original_cargo", "id": row["id"], "item": row["item"],
         "count": count, "passed": count >= 1}
        for row in cargo
        for count in [cargo_count(stacks, row)]
    ]
    checks.extend(result["checks"])
    return {
        "success": all(check["passed"] for check in checks), "checks": checks,
        "semantics": "Original tagged chest items and a living, grounded, settled return. "
        "Any legal route, construction, digging, chest breaking or native recovery is allowed. "
        "Death is measured separately, not an automatic failure.",
    }
