"""Resource delivery with independent native furnace efficiency evidence."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.fixtures.furnaces import SCHEMA, expected_hashes


def mined_statistics(world: Path, player: UUID) -> dict:
    path = world / "stats" / f"{player}.json"
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    counts = value["stats"].get("minecraft:mined", {})
    if value["DataVersion"] != 3700 or not isinstance(counts, dict) or any(
        type(count) is not int or count < 0 for count in counts.values()
    ):
        raise ValueError("Invalid native mining statistics")
    return counts


def furnace_evidence(world: Path) -> dict:
    expected = expected_hashes()
    manifest = json.loads((world / "livequest-furnaces.json").read_text())
    if manifest != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Furnace observer manifest differs from its declared implementation")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_furnaces" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Furnace observer datapack changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Furnace observation requires native Minecraft 1.20.4")
    record = native["data"]["contents"]["dispatch"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Furnace evidence schema changed")
    events = []
    for event in record["events"]:
        kind, machine, tick = str(event["kind"]), int(event["machine"]), int(event["tick"])
        if kind not in ("completion", "fuel") or machine not in (0, 1) or tick < 0:
            raise ValueError("Malformed furnace event")
        row = {"kind": kind, "machine": machine, "tick": tick}
        if kind == "completion":
            row.update(item=str(event["output"]["id"]), output_count=int(event["output"]["Count"]))
        else:
            # This is the last sampled slot label, not proven consumed-item identity.
            row["item"] = str(event["item"]) if "item" in event else None
        events.append(row)
    metrics = [{key: int(row[key]) for key in ("burning_ticks", "empty_input_burn_ticks")}
               for row in record["metrics"]]
    if len(metrics) != 2 or any(not 0 <= row["empty_input_burn_ticks"] <= row["burning_ticks"] for row in metrics):
        raise ValueError("Invalid native burn accounting")
    return {"events": events, "machines": metrics}


def evaluate_dispatch(before: Path, after: Path, player: UUID, **state) -> dict:
    opening, closing = furnace_evidence(before), furnace_evidence(after)
    if opening["events"] or any(row["burning_ticks"] for row in opening["machines"]):
        raise ValueError("Furnace task must start without previous production")
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if last < first or any(not first <= event["tick"] <= last for event in closing["events"]):
        raise ValueError("Furnace event is outside the measured native clock")
    initial_mined, final_mined = mined_statistics(before, player), mined_statistics(after, player)
    mined = {item: final_mined.get(item, 0) - initial_mined.get(item, 0)
             for item in initial_mined.keys() | final_mined.keys()}
    if any(count < 0 for count in mined.values()):
        raise ValueError("Native mining statistic moved backwards")
    result = evaluate_state(before, after, player, **state)
    result["furnace_efficiency"] = closing | {
        "native_elapsed_ticks": last - first, "native_mined_delta": mined,
    }
    result["semantics"] += (
        " Passive output increases and fuel starts at the two original furnace positions provide native timestamps; "
        "production after furnace relocation is not covered by these observers. "
        "Empty-input burn ticks count sampled burning/empty-input states, including batch-completion boundaries; "
        "they are not an exact waste measure and do not cover all blocked-furnace losses. "
        "Fuel labels are last sampled slot contents, not proven consumed-item identities; missing labels are unknown. "
        "Native mined-block deltas expose replacement gathering, not attribution of collected items to fuel. "
        "Serial production, furnace relocation and replacement gathering are legal."
    )
    return result
