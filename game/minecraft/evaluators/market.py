"""Alternative native procurement bundles and raw completed-trade diagnostics."""

from pathlib import Path
from uuid import UUID

from game.minecraft.evaluators.state import custom_statistics, evaluate_state, validate_state


def validate_market(*, bundles: list[list[dict]], position: dict) -> None:
    if not isinstance(bundles, list) or not bundles:
        raise ValueError("Procurement requires at least one complete inventory bundle")
    for bundle in bundles:
        if not isinstance(bundle, list) or not bundle:
            raise ValueError("An empty procurement bundle is not a goal")
        validate_state(inventory=bundle, position=position)


def evaluate_market(before: Path, after: Path, player: UUID, *, bundles: list[list[dict]], position: dict) -> dict:
    validate_market(bundles=bundles, position=position)
    results = [evaluate_state(before, after, player, inventory=bundle, position=position) for bundle in bundles]
    initial = custom_statistics(before, player).get("minecraft:traded_with_villager", 0)
    final = custom_statistics(after, player).get("minecraft:traded_with_villager", 0)
    if final < initial:
        raise ValueError("Native completed-trade count moved backwards")
    return {
        "success": any(row["success"] for row in results),
        "bundles": results, "completed_native_trades": final - initial,
        "semantics": "One whole procurement bundle, its reserve and arrival must hold together. "
        "Native trade counts are diagnostic, not a required purchase order or evidence of adaptation. "
        "Legal gathering and crafting alternatives remain valid.",
    }
