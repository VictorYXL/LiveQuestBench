"""Original chest cargo across independent native peers, without action quotas."""

from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.cargo import cargo_count, player_inventory, verify_initial_cargo
from game.minecraft.evaluators.state import custom_statistics


def verify_team_cargo(before: Path, players: dict[str, UUID], *, cargo: list[dict], position: dict) -> None:
    for role, player in players.items():
        verify_initial_cargo(before / role, player, cargo=cargo, position=position)


def evaluate_team_cargo(
    before: Path, after: Path, players: dict[str, UUID], *, cargo: list[dict], position: dict,
) -> dict:
    verify_team_cargo(before, players, cargo=cargo, position=position)
    inventories = {role: player_inventory(after / role, player) for role, player in players.items()}
    checks = []
    for row in cargo:
        counts = {role: cargo_count(stacks, row) for role, stacks in inventories.items()}
        if sum(counts.values()) > 1:
            raise ValueError("Original team cargo was duplicated")
        checks.append({"kind": "original_team_cargo", "id": row["id"], "item": row["item"],
                       "counts": counts, "passed": sum(counts.values()) == 1})
    return {
        "success": all(row["passed"] for row in checks), "checks": checks,
        "semantics": "Original tagged chest items held across independently controlled peers. "
                     "Any legal allocation, solo retrieval, handoff or native recovery is allowed.",
    }


def team_efficiency(before: Path, after: Path, players: dict[str, UUID]) -> dict:
    result = {}
    for role, player in players.items():
        first = custom_statistics(before / role, player)
        last = custom_statistics(after / role, player)
        names = (
            "walk_one_cm", "sprint_one_cm", "crouch_one_cm", "swim_one_cm", "walk_on_water_one_cm",
            "walk_under_water_one_cm", "climb_one_cm", "fall_one_cm", "fly_one_cm",
            "damage_taken", "damage_dealt", "damage_blocked_by_shield", "deaths",
        )
        deltas = {}
        for name in names:
            key = "minecraft:" + name
            delta = last.get(key, 0) - first.get(key, 0)
            if delta < 0:
                raise ValueError("Team efficiency statistic moved backwards")
            deltas[name] = delta
        opening = int(nbtlib.load(before / role / "level.dat")["Data"]["Time"])
        closing = int(nbtlib.load(after / role / "level.dat")["Data"]["Time"])
        if closing < opening:
            raise ValueError("Team native clock moved backwards")
        result[role] = {
            "native_elapsed_ticks": closing - opening,
            "native_statistic_deltas": deltas,
            "on_foot_distance_m": sum(deltas[name] for name in names if name.endswith("_one_cm")) / 100,
            "damage_taken_health_points": deltas["damage_taken"] / 10,
        }
    return {
        "participants": result,
        "semantics": "Raw native elapsed ticks, travel and health-loss statistics. "
                     "Time includes deliberation and finalization; not first goal-achievement time. "
                     "Distance is native movement-category distance, not cargo-weighted transport. "
                     "Compare conditional on success and report failures separately. "
                     "Team endpoint success alone does not establish communication benefit or dependence.",
    }
