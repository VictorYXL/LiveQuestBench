"""Original-token success with non-gating native site and travel diagnostics."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.cargo import evaluate_cargo
from game.minecraft.evaluators.state import custom_statistics
from game.minecraft.fixtures.quarry import SCHEMA, expected_hashes


def visits(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-quarry.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Quarry observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_quarry" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Quarry observer implementation changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Quarry evidence requires native Minecraft 1.20.4")
    record = native["data"]["contents"]["quarry"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Quarry observer identity changed")
    return [{"site": int(row["site"]), "tick": int(row["tick"]),
             "player": list(map(int, row["player"]))} for row in record["visits"]]


def entry_diagnostics(record, player, first, last):
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    if any(row["site"] not in (0, 1, 2) or row["player"] != identity
           or not first <= row["tick"] <= last for row in record):
        raise ValueError("Quarry entry has invalid site, player or native time")
    return {
        "entries": record, "distinct_sites_entered": sorted({row["site"] for row in record}),
        "wrong_site_entries": sum(row["site"] != 0 for row in record),
        "semantics": "Native foot-position entries into quarry interiors, including repeat entries. "
                     "Looking from outside is not an entry. Entries do not prove clue use.",
    }


def evaluate_quarry(before: Path, after: Path, player: UUID, *, cargo, position):
    if visits(before):
        raise ValueError("Quarry visit history must start empty")
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    diagnostics = entry_diagnostics(visits(after), player, first, last)
    opening, closing = custom_statistics(before, player), custom_statistics(after, player)
    names = ("walk_one_cm", "sprint_one_cm", "crouch_one_cm", "swim_one_cm",
             "walk_on_water_one_cm", "walk_under_water_one_cm", "climb_one_cm",
             "fall_one_cm", "fly_one_cm")
    deltas = {name: closing.get("minecraft:" + name, 0) - opening.get("minecraft:" + name, 0)
              for name in names}
    if any(value < 0 for value in deltas.values()) or last < first:
        raise ValueError("Native quarry travel or clock moved backwards")
    result = evaluate_cargo(before, after, player, cargo=cargo, position=position)
    result["information_diagnostics"] = {
        **diagnostics, "native_elapsed_ticks": last - first,
        "native_movement_cm": deltas, "on_foot_distance_m": sum(deltas.values()) / 100,
        "distance_semantics": "Sum of vanilla movement-category counters, not a shortest-path estimate.",
    }
    result["semantics"] += (
        " Wrong-site entries, native travel and time are non-gating diagnostics. Exhaustive search, "
        "repeat visits and any legal retrieval route remain valid. Clue interactions and plan changes "
        "require separate public trajectory review; endpoint success is not information-use evidence."
    )
    return result
