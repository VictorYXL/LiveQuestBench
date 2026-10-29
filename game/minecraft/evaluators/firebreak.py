"""Passive native fire dwell and irreversible original-structure loss."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state, validate_state
from game.minecraft.evaluators.world import read_blocks


def manifest(world: Path) -> dict:
    data = json.loads((world / "livequest-firebreak.json").read_text())
    if data["schema"] != "minecraft-native-firebreak/1":
        raise ValueError("Unknown native firebreak schema")
    for name, expected in data["pack_sha256"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid firebreak datapack path")
        if hashlib.sha256((world / "datapacks/livequest_firebreak" / path).read_bytes()).hexdigest() != expected:
            raise ValueError("Native firebreak observer changed")
    return data


def evidence(world: Path) -> dict:
    value = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(value["DataVersion"]) != 3700:
        raise ValueError("Firebreak requires Minecraft Java 1.20.4")
    return value["data"]["contents"]["firebreak"]


def verify_initial_firebreak(before: Path, player: UUID, *, position: dict) -> None:
    validate_state(position=position)
    registry = manifest(before)
    if evidence(before)["destroyed"]:
        raise ValueError("Protected originals were already lost before play")
    for row in registry["protected"]:
        point = tuple(row["position"])
        if read_blocks(before, point, point, "minecraft:overworld")[point] != row["block"]:
            raise ValueError("Initial protected structure does not match registry")
    ignition = tuple(registry["ignition"])
    if read_blocks(before, ignition, ignition, "minecraft:overworld")[ignition] != "minecraft:fire":
        raise ValueError("Fire must be active before play")


def evaluate_firebreak(before: Path, after: Path, player: UUID, *, position: dict) -> dict:
    verify_initial_firebreak(before, player, position=position)
    registry = manifest(before)
    if manifest(after) != registry:
        raise ValueError("Firebreak registry changed during play")
    data = evidence(after)
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    allowed = {tuple(row["position"]) for row in registry["protected"]}
    lost = []
    previous = opening
    for row in data["destroyed"]:
        point, tick = tuple(map(int, row["cell"])), int(row["tick"])
        if point not in allowed or point in lost or not previous <= tick <= closing:
            raise ValueError("Invalid irreversible protected-cell evidence")
        lost.append(point)
        previous = tick
    quiet, burning = int(data["quiet_ticks"]), int(data["burning_cells"])
    if not 0 <= quiet <= closing - opening or burning < 0:
        raise ValueError("Invalid native fire dwell")
    retained = len(allowed) - len(lost)
    result = evaluate_state(before, after, player, position=position)
    result["checks"] += [
        {"kind": "original_structure_retention", "retained": retained, "initial": len(allowed),
         "irreversibly_lost": lost, "minimum_fraction": .8, "passed": retained * 5 >= len(allowed) * 4},
        {"kind": "native_fire_absent_dwell", "burning_cells": burning, "quiet_ticks": quiet,
         "minimum_ticks": 400, "passed": burning == 0 and quiet >= 400},
    ]
    result["success"] = all(row["passed"] for row in result["checks"])
    result["native_elapsed_ticks"] = closing - opening
    result["semantics"] = (
        "Native block fire absent in the publicly marked yard volume throughout a 400-tick dwell, "
        "at least 80% of original marked "
        "roof/support cells never lost, and living settled safe-pad arrival. "
        "Rebuilding never restores lost-original credit. No runtime fire or structure repair commands."
    )
    return result
