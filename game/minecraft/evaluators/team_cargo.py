"""Original chest cargo across independent native peers, without action quotas."""

from collections import Counter
import hashlib
import json
import math
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


def _inventory_counts(stacks) -> dict[str, int]:
    result = Counter()
    for stack in stacks:
        count = int(stack["Count"])
        if count <= 0:
            raise ValueError("Invalid native inventory count in participant trace")
        result[str(stack["id"])] += count
    return dict(result)


def _transport_estimate(samples: list[dict]) -> dict:
    distance, largest_gap = 0.0, 0
    carried = Counter()
    for first, last in zip(samples, samples[1:]):
        gap = last["tick"] - first["tick"]
        if gap <= 0:
            raise ValueError("Participant trace clock is not strictly increasing")
        length = math.dist(first["position"], last["position"])
        if not math.isfinite(length):
            raise ValueError("Nonfinite native participant position")
        distance += length
        largest_gap = max(largest_gap, gap)
        for item in first["inventory"].keys() | last["inventory"].keys():
            count = (first["inventory"].get(item, 0) + last["inventory"].get(item, 0)) / 2
            if count < 0:
                raise ValueError("Negative participant inventory count")
            carried[item] += length * count
    return {
        "status": "approximate_passive_trace",
        "sampled_path_metres": distance,
        "carried_item_metres": {item: value for item, value in sorted(carried.items()) if value > 0},
        "maximum_sample_gap_ticks": largest_gap,
        "semantics": "Straight-line sample chords weighted by mean endpoint stack counts, including "
                     "initial/final native snapshots. Not exact transport distance: turns and inventory "
                     "changes between samples are unresolved. Item types are reported separately, "
                     "not combined into a mass, material-equivalence or cooperation score.",
    }


def _trace_transport(before: Path, after: Path, player: UUID, opening: int, closing: int) -> dict:
    manifest = "livequest-trace.json"
    if not (before / manifest).exists() and not (after / manifest).exists():
        return {"status": "unavailable", "reason": "No optional passive participant trace."}
    registries = []
    for world in (before, after):
        record = json.loads((world / manifest).read_text())
        if record["schema"] != "minecraft-passive-player-trace/1":
            raise ValueError("Unknown passive participant trace schema")
        base = world / "datapacks/livequest_trace"
        for name, expected in record["pack_sha256"].items():
            path = base / name
            if not path.resolve().is_relative_to(base.resolve()):
                raise ValueError("Invalid participant trace observer path")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Participant trace observer changed")
        registries.append(record)
    if registries[0] != registries[1]:
        raise ValueError("Participant trace registry changed")
    stored = nbtlib.load(after / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Participant trace requires Minecraft Java 1.20.4")
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
    samples = []
    for row in stored["data"]["contents"]["trace"]["samples"]:
        if list(map(int, row["UUID"])) != identity:
            continue
        tick = int(row["tick"])
        if tick > closing:
            raise ValueError("Participant trace extends beyond its native closing clock")
        if opening < tick < closing:
            samples.append({"tick": tick, "position": list(map(float, row["Pos"])),
                            "inventory": _inventory_counts(row["Inventory"])})
    native_count = len(samples)
    for world, tick, prepend in ((before, opening, True), (after, closing, False)):
        if not prepend and opening == closing:
            break
        state = nbtlib.load(world / "playerdata" / f"{player}.dat")
        row = {"tick": tick, "position": list(map(float, state["Pos"])),
               "inventory": _inventory_counts(state["Inventory"])}
        if prepend:
            samples.insert(0, row)
        else:
            samples.append(row)
    result = _transport_estimate(samples)
    result["native_trace_samples"] = native_count
    return result


def _item_activity(before: Path, after: Path, player: UUID) -> dict:
    categories = []
    for world in (before, after):
        path = world / "stats" / f"{player}.json"
        categories.append(json.loads(path.read_text())["stats"] if path.exists() else {})
    result = {}
    for category in ("crafted", "used", "mined", "picked_up", "dropped"):
        first, last = (row.get("minecraft:" + category, {}) for row in categories)
        deltas = {item: int(last.get(item, 0)) - int(first.get(item, 0))
                  for item in first.keys() | last.keys()}
        if any(value < 0 for value in deltas.values()):
            raise ValueError("Native participant item activity moved backwards")
        result[category] = {item: value for item, value in deltas.items() if value}
    return result


def team_efficiency(before: Path, after: Path, players: dict[str, UUID]) -> dict:
    from game.minecraft.evaluators.threat_targets import target_diagnostics

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
            "native_item_activity_deltas": _item_activity(before / role, after / role, player),
            "sampled_transport": _trace_transport(before / role, after / role, player, opening, closing),
        }
    return {
        "participants": result,
        "enemy_targeting": target_diagnostics(
            before / next(iter(players)), after / next(iter(players)), players,
        ),
        "semantics": "Raw native elapsed ticks, travel and health-loss statistics. "
                     "Time includes deliberation and finalization; not first goal-achievement time. "
                     "Movement-category distance is not cargo-weighted transport; the separate optional "
                     "inventory-weighted trace estimate declares its sampling limitations. "
                     "Compare conditional on success and report failures separately. "
                     "Team endpoint success alone does not establish communication benefit or dependence.",
    }
