"""Fresh native raid victory, without relying on a raid record remaining loaded."""

import json
from pathlib import Path
from uuid import UUID

from game.minecraft.evaluators.state import custom_statistics, evaluate_state, validate_state


HERO = "minecraft:adventure/hero_of_the_village"


def hero_completed(world: Path, player: UUID) -> bool:
    path = world / "advancements" / f"{player}.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text())
    if data["DataVersion"] != 3700:
        raise ValueError("Raid advancement evidence requires Minecraft Java 1.20.4")
    row = data.get(HERO)
    if row is None:
        return False
    if type(row["done"]) is not bool or not isinstance(row["criteria"], dict):
        raise ValueError("Malformed native Hero of the Village advancement")
    return row["done"] and "hero_of_the_village" in row["criteria"]


def verify_initial_raid(world: Path, player: UUID) -> None:
    if hero_completed(world, player) or custom_statistics(world, player).get("minecraft:raid_win", 0):
        raise ValueError("Village defense requires a player without an earlier raid victory")


def evaluate_raid(before: Path, after: Path, player: UUID, **state) -> dict:
    validate_state(**state)
    verify_initial_raid(before, player)
    result = evaluate_state(before, after, player, **state)
    wins = custom_statistics(after, player).get("minecraft:raid_win", 0)
    result["checks"].append({
        "kind": "native_raid_victory", "raid_wins": wins,
        "fresh_hero_advancement": hero_completed(after, player),
        "passed": wins >= 1 and hero_completed(after, player),
    })
    result["success"] = all(row["passed"] for row in result["checks"])
    result["semantics"] += (
        " Fresh vanilla Hero of the Village advancement and raid_win statistic for the initialized "
        "player. No bossbar/disappearance proxy, mandatory last hit, all-residents-survive condition, "
        "or dependence on the temporary raid record. This proves a native raid victory, not a raid ID."
    )
    return result
