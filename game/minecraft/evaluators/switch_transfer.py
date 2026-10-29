"""Native switch correspondence application; success is not a learning-benefit estimate."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state, validate_state


def registry(world: Path) -> dict:
    data = json.loads((world / "livequest-switch.json").read_text())
    if data["schema"] != "minecraft-switch-transfer/1":
        raise ValueError("Unknown switch transfer registry")
    for name, expected in data["pack_sha256"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid switch observer path")
        if hashlib.sha256((world / "datapacks/livequest_switch" / path).read_bytes()).hexdigest() != expected:
            raise ValueError("Switch observer changed")
    return data


def evidence(world: Path) -> dict:
    stored = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Switch transfer requires Minecraft Java 1.20.4")
    return stored["data"]["contents"]["switch"]


def verify_initial_switch(before: Path, player: UUID, *, position: dict) -> None:
    validate_state(position=position)
    value = registry(before)
    if sorted(value["permutation"]) != [0, 1, 2]:
        raise ValueError("Native routing must be a three-output permutation")
    if value["remote_routing_minimum_x"] - value["maximum_legal_player_x"] <= 15:
        raise ValueError("Remote permutation routing is within the public ST radius")
    record = evidence(before)
    if (record["events"] or int(record["application_toggles"]) or int(record["practice_toggles"])
            or int(record["practice_feedback"]) or int(record["phase"])
            or int(record["ready_1"]) or int(record["ready_2"])):
        raise ValueError("Switch application and practice evidence must start empty")
    player_data = nbtlib.load(before / "playerdata" / f"{player}.dat")
    if int(player_data["playerGameType"]) != 2:
        raise ValueError("Native Adventure protection was not initialized")


def evaluate_switch(before: Path, after: Path, player: UUID, *, position: dict) -> dict:
    verify_initial_switch(before, player, position=position)
    if registry(before) != registry(after):
        raise ValueError("Switch registry changed during play")
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if last < first:
        raise ValueError("Native switch clock moved backwards")
    data = evidence(after)
    toggles, practice, phase = (int(data[key]) for key in ("application_toggles", "practice_toggles", "phase"))
    if min(toggles, practice, phase) < 0 or phase > 2:
        raise ValueError("Invalid native switch counters")
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
    events = []
    previous = first
    for index, row in enumerate(data["events"], start=1):
        tick = int(row["tick"])
        if (int(row["application"]) != index or list(map(int, row["player"])) != identity
                or not previous <= tick <= last):
            raise ValueError("Invalid native switch application identity/order")
        events.append({"application": index, "tick": tick})
        previous = tick
    if len(events) != phase:
        raise ValueError("Native switch phase and event count disagree")
    mode = int(nbtlib.load(after / "playerdata" / f"{player}.dat")["playerGameType"])
    result = evaluate_state(before, after, player, position=position)
    result["checks"] += [
        {"kind": "native_adventure_mode", "actual": mode, "passed": mode == 2},
        {"kind": "practice_feedback", "toggles": practice, "passed": practice > 0 and bool(data["practice_feedback"])},
        {"kind": "ordered_native_outputs", "events": events, "passed": phase == 2},
        {"kind": "final_requested_only_outputs",
         "passed": bool(data["ready_1"]) and bool(data["ready_2"])},
        {"kind": "application_toggle_budget", "actual": toggles, "maximum": 4, "passed": toggles <= 4},
    ]
    result["success"] = all(row["passed"] for row in result["checks"])
    result["learning_benefit"] = {
        "status": "not_estimated",
        "reason": "Separate matched retained/erased native application contrasts are required.",
    }
    result["semantics"] = (
        "Native practice lamp feedback, ordered requested-only application lamp states and actual "
        "application lever transitions. Circuit routing is unchanged; passive scoring never opens a door. "
        "Chance or prior static-map knowledge may succeed without acquiring the rule."
    )
    return result
