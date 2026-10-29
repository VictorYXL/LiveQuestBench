"""Arrow-owned target hits, three native lamp latches and a settled return."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.fixtures.gallery import SCHEMA, expected_hashes


def gallery_evidence(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-gallery.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Target-hit observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_gallery" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Target-hit observer changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Gallery evidence requires native Minecraft 1.20.4")
    record = native["data"]["contents"]["gallery"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Gallery evidence identity changed")
    return {
        "hits": [{"target": int(row["target"]), "player": list(map(int, row["player"])),
                  "tick": int(row["tick"])} for row in record["hits"]],
        "lamps": list(map(int, record["lamps"])),
    }


def evaluate_gallery(before: Path, after: Path, player: UUID, *, position: dict):
    initial, final = gallery_evidence(before), gallery_evidence(after)
    if initial["hits"] or any(initial["lamps"]):
        raise ValueError("Gallery must start without earlier hits or powered latches")
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if any(row["player"] != identity or row["target"] not in range(3)
           or not first <= row["tick"] <= last for row in final["hits"]):
        raise ValueError("Gallery hit identity or native time is invalid")
    result = evaluate_state(before, after, player, position=position)
    result["checks"].extend([
        {"kind": "three_attributed_arrow_target_hits",
         "passed": {row["target"] for row in final["hits"]} == {0, 1, 2}},
        {"kind": "three_native_lamp_latches", "passed": final["lamps"] == [1, 1, 1]},
    ])
    result["success"] = all(row["passed"] for row in result["checks"])
    result["target_evidence"] = final
    result["semantics"] += (
        " Vanilla target_hit criteria bind arrow ownership; target POWER identifies the activated native target. "
        "The observer does not activate lamps: native pistons and redstone blocks supply persistent latches."
    )
    return result
