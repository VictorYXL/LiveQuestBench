"""Stable native farmland hydration without flooding the public walkway."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.fixtures.irrigation import SCHEMA, expected_hashes


def stable_ticks(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-irrigation.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Irrigation observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_irrigation" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Irrigation observer changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Irrigation evidence requires Minecraft 1.20.4")
    record = native["data"]["contents"]["irrigation"]
    if str(record["schema"]) != SCHEMA or int(record["stable_ticks"]) < 0:
        raise ValueError("Invalid irrigation stability evidence")
    return int(record["stable_ticks"])


def evaluate_irrigation(before: Path, after: Path, player: UUID, *, position: dict):
    if stable_ticks(before):
        raise ValueError("Irrigation must not be complete at initialization")
    stable = stable_ticks(after)
    elapsed = (int(nbtlib.load(after / "level.dat")["Data"]["Time"])
               - int(nbtlib.load(before / "level.dat")["Data"]["Time"]))
    if elapsed < 0 or stable > elapsed:
        raise ValueError("Irrigation stability exceeds elapsed native world ticks")
    result = evaluate_state(before, after, player, position=position)
    result["checks"].append({"kind": "water_supplied_hydrated_fields_and_dry_walkway", "stable_ticks": stable,
                            "minimum_native_ticks": 100, "passed": stable >= 100})
    result["success"] = all(row["passed"] for row in result["checks"])
    result["semantics"] += (
        " Every marked farmland cell must have native water within vanilla hydration range, remain "
        "fully hydrated, and the white walkway must remain clear of water and obstruction for at least "
        "100 consecutive native world ticks; repeated observer calls while frozen do not count. "
        "Residual moisture after water removal is insufficient; "
        "waterlogged blocks remain valid water sources. Water placement and flow remain vanilla."
    )
    return result
