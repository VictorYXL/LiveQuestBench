"""Native extraction endpoints with a serviceable iron pickaxe."""

from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state, validate_state


IRON_PICKAXE_DURABILITY = 250


def remaining_pickaxe_uses(stacks) -> list[int]:
    uses = []
    for stack in stacks:
        if str(stack["id"]) != "minecraft:iron_pickaxe":
            continue
        damage = int(stack.get("tag", {}).get("Damage", 0))
        if int(stack["Count"]) != 1 or not 0 <= damage < IRON_PICKAXE_DURABILITY:
            raise ValueError("Invalid native iron-pickaxe wear")
        uses.append(IRON_PICKAXE_DURABILITY - damage)
    return uses


def validate_extraction(*, inventory: list[dict], position: dict, minimum_pickaxe_uses: int) -> None:
    validate_state(inventory=inventory, position=position)
    if type(minimum_pickaxe_uses) is not int or not 1 <= minimum_pickaxe_uses <= IRON_PICKAXE_DURABILITY:
        raise ValueError("Minimum iron-pickaxe uses must be in [1, 250]")


def evaluate_extraction(before: Path, after: Path, player: UUID, *, inventory: list[dict],
                        position: dict, minimum_pickaxe_uses: int) -> dict:
    validate_extraction(inventory=inventory, position=position, minimum_pickaxe_uses=minimum_pickaxe_uses)
    result = evaluate_state(before, after, player, inventory=inventory, position=position)
    stacks = nbtlib.load(after / "playerdata" / f"{player}.dat")["Inventory"]
    uses = remaining_pickaxe_uses(stacks)
    result["checks"].append({"kind": "serviceable_iron_pickaxe", "remaining_uses": uses,
                            "minimum": minimum_pickaxe_uses,
                            "passed": any(n >= minimum_pickaxe_uses for n in uses)})
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += " Tool replacement, repair and extra legal gathering are all accepted."
    return result
