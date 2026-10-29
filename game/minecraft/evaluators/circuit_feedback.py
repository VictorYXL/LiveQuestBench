"""Coherent final-repair evidence, in addition to the unchanged circuit gates."""

import hashlib
import json

import nbtlib

from game.minecraft.evaluators.circuit import evaluate_circuit
from game.minecraft.fixtures.circuit_feedback_observer import (
    NAMESPACE, SCHEMA, STABLE_TICKS, expected_hashes, mined_blocks,
)


def evidence(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-feedback.json").read_text()) != {
        "schema": SCHEMA, "sha256": expected,
    }:
        raise ValueError("Feedback observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks" / NAMESPACE / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Feedback observer implementation changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Feedback evidence requires Minecraft 1.20.4")
    record = native["data"]["contents"]["feedback"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Feedback storage identity changed")
    return {
        "events": [{key: list(map(int, row[key])) if key == "player" else int(row[key])
                    for key in ("player", "tick", "start_tick", "input", "mined", "edits")}
                   for row in record["events"]],
        "edits": [{"player": list(map(int, row["player"])), "tick": int(row["tick"])}
                  for row in record["edits"]],
    }


def mined_total(world, player):
    path = world / "stats" / f"{player}.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    counts = data["stats"].get("minecraft:mined", {})
    known = {"minecraft:" + name for name in mined_blocks()}
    if (data["DataVersion"] != 3700 or not isinstance(counts, dict)
            or any(name not in known or type(value) is not int or value < 0
                   for name, value in counts.items())):
        raise ValueError("Unsupported native mining statistics")
    return sum(counts.values())


def final_modes(record, player, first, last, mined):
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    if last < first:
        raise ValueError("Feedback clock moved backwards")
    events, edits = record["events"], record["edits"]
    for rows in (events, edits):
        if any(row["player"] != identity or not first <= row["tick"] <= last for row in rows):
            raise ValueError("Invalid feedback identity or time")
        if any(a["tick"] > b["tick"] for a, b in zip(rows, rows[1:])):
            raise ValueError("Feedback records are not chronological")
    for row in events:
        if (row["input"] not in (0, 1)
                or not first <= row["start_tick"] <= row["tick"] - STABLE_TICKS + 1
                or not 0 <= row["edits"] <= len(edits) or not 0 <= row["mined"] <= mined):
            raise ValueError("Invalid stable feedback interval or repair revision")
        count = row["edits"]
        if (any(edit["tick"] > row["start_tick"] for edit in edits[:count])
                or any(edit["tick"] < row["tick"] for edit in edits[count:])):
            raise ValueError("Feedback interval crossed a block interaction")
    if any(b["start_tick"] <= a["tick"] or b["mined"] < a["mined"] or b["edits"] < a["edits"]
           for a, b in zip(events, events[1:])):
        raise ValueError("Feedback stability intervals overlap or revisions moved backwards")
    return {row["input"] for row in events
            if row["edits"] == len(edits) and row["mined"] == mined}


def verify_initial(world, player):
    if evidence(world) != {"events": [], "edits": []} or mined_total(world, player):
        raise ValueError("Feedback task must start without demonstrations or player block edits")


def evaluate_feedback(before, after, player, *, position):
    verify_initial(before, player)
    result = evaluate_circuit(before, after, player, position=position)
    record = evidence(after)
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    mined = mined_total(after, player)
    modes = final_modes(record, player, first, last, mined)
    result["checks"].append({"kind": "settled_modes_after_final_repair",
                             "passed": modes == {0, 1}, "modes": sorted(modes),
                             "final_revision": {"mined": mined, "edits": len(record["edits"])}})
    result["success"] = all(row["passed"] for row in result["checks"])
    result["feedback_evidence"] = record
    result["semantics"] += (
        " Additionally, both modes require 100 consecutive native matching ticks after the final "
        "player mining, placement or other block interaction, excluding use of the original input lever. "
        "The original ten-tick lifetime history alone cannot qualify this version."
    )
    return result
