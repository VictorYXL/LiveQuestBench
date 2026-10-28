"""Native workshop proficiency and first-attainment events, not a learning score."""

import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state, validate_state
from game.minecraft.fixtures.workshop_orders import ORDERS, SCHEMA, expected_hashes, pack_hashes


def order_events(world: Path) -> list[dict]:
    manifest = json.loads((world / "livequest-workshop-evidence.json").read_text())
    if manifest != {"schema": SCHEMA, "pack_sha256": expected_hashes()} or pack_hashes(world) != expected_hashes():
        raise ValueError("Workshop evidence datapack differs from the declared observer")
    stored = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Workshop evidence requires Minecraft Java 1.20.4")
    record = stored["data"]["contents"]["workshop"]
    if str(record["schema"]) != SCHEMA or not isinstance(record["events"], nbtlib.List):
        raise ValueError("Invalid native workshop event storage")
    return [{"order": int(row["order"]), "player": list(map(int, row["player"])), "tick": int(row["tick"])}
            for row in record["events"]]


def evaluate_workshop(before: Path, after: Path, player: UUID, **state) -> dict:
    validate_state(**state)
    if order_events(before):
        raise ValueError("Workshop order history must start empty")
    events = order_events(after)
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    expected_player = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
    seen = set()
    previous = opening
    for event in events:
        if (event["order"] not in ORDERS or event["order"] in seen or event["player"] != expected_player
                or not previous <= event["tick"] <= closing):
            raise ValueError("Invalid workshop milestone identity, uniqueness or time")
        previous = event["tick"]
        seen.add(event["order"])
    result = evaluate_state(before, after, player, **state)
    result["checks"].append({
        "kind": "native_order_milestones", "orders": sorted(seen), "passed": seen == set(ORDERS),
    })
    result["success"] = all(check["passed"] for check in result["checks"])
    result["order_milestones"] = events
    result["learning_benefit"] = {
        "status": "not_estimated",
        "reason": "First attainment and final proficiency do not identify learning without matched controls.",
    }
    result["semantics"] += (
        " Passive vanilla inventory advancements record first attainment with player UUID and game tick. "
        "No order of production is required; global batching is legal. Events do not prove furnace "
        "efficiency, causal learning or mandatory experience stages."
    )
    return result
