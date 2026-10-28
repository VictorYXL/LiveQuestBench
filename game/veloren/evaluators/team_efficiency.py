"""Raw native team travel and possession changes, without counterfactual credit."""

import math
from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair
from game.veloren.evaluators.itinerary import route_samples
from game.veloren.fixture import inventory_counts, item_id


def possessions(row: dict) -> dict:
    counts = inventory_counts(row)
    for item in row["inventory"]["equipment"].values():
        if item is not None:
            name = item_id(item)
            counts[name] = counts.get(name, 0) + item["amount"]
    return counts


def difference(before: dict, after: dict) -> dict:
    return {name: after.get(name, 0) - before.get(name, 0)
            for name in sorted(before.keys() | after.keys())
            if before.get(name, 0) != after.get(name, 0)}


def team_efficiency(before: Path, after: Path, roles: list[str]) -> dict:
    participants, totals = {}, ({}, {})
    identities = set()
    for role in roles:
        first, last = load_pair(before / role, after / role)
        identity = first["self_identity"]["uid"]
        if identity in identities:
            raise ValueError("Team travel requires distinct native players")
        identities.add(identity)
        samples = route_samples(first, last)
        points = [first["position"], *(row["position"] for row in samples), last["position"]]
        clocks = [row["survival"]["buff_clock"] for row in (first, last)]
        if (not all(row["synchronized"] is True and math.isfinite(row["now"]) for row in clocks)
                or clocks[1]["now"] < clocks[0]["now"]):
            raise ValueError("Native client clocks must be synchronized and ordered")
        counts = [possessions(row) for row in (first, last)]
        for total, observed in zip(totals, counts):
            for name, amount in observed.items():
                total[name] = total.get(name, 0) + amount
        participants[role] = {
            "sampled_horizontal_metres": sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:])),
            "sampled_3d_metres": sum(math.dist(a, b) for a, b in zip(points, points[1:])),
            "native_client_physics_seconds": clocks[1]["now"] - clocks[0]["now"],
            "native_client_updates": last["private_route_evidence"]["through_tick"]
                                     - first["private_route_evidence"]["through_tick"],
            "possessions_net_changes": difference(*counts),
        }
    return {
        "participants": participants,
        "team_sampled_horizontal_metres": sum(row["sampled_horizontal_metres"] for row in participants.values()),
        "team_possessions_net_changes": difference(*totals),
        "semantics": (
            "Per-player fresh native route polylines and synchronized client-physics intervals; "
            "sequential snapshots are non-atomic. Possessions include carried and equipped items. "
            "Net changes are not consumption or source-identity receipts. These raw diagnostics do not "
            "prove a speedup over a solo policy, equal contribution, or a cooperation benefit."
        ),
    }
