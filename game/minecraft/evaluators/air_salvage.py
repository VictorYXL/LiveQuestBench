"""Original underwater samples, no native deaths and passive air diagnostics."""

import json
import math
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.cargo import evaluate_cargo, verify_initial_cargo
from game.minecraft.evaluators.deaths import evaluate_deaths
from game.minecraft.fixtures.air_observer import SCHEMA, air_hashes


def samples(world: Path) -> list[dict]:
    manifest = json.loads((world / "livequest-air.json").read_text())
    if manifest != {"schema": SCHEMA, "pack_sha256": air_hashes(world)}:
        raise ValueError("Native air observer manifest or datapack changed")
    value = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(value["DataVersion"]) != 3700:
        raise ValueError("Native air diagnostics require Minecraft 1.20.4")
    stored = value["data"]["contents"]["air"]
    if str(stored["schema"]) != SCHEMA:
        raise ValueError("Native air storage schema changed")
    return [
        {"player": list(map(int, row["UUID"])), "tick": int(row["tick"]),
         "position": list(map(float, row["Pos"])), "health": float(row["Health"]),
         "air_ticks": int(row["Air"]), "effects": [
             {"id": str(effect["id"]), "duration_ticks": int(effect["duration"]),
              "amplifier": int(effect.get("amplifier", 0))}
             for effect in row["active_effects"]
         ]}
        for row in stored["samples"]
    ]


def verify_initial_air_salvage(before: Path, player: UUID, *, cargo: list[dict], position: dict) -> None:
    verify_initial_cargo(before, player, cargo=cargo, position=position)
    if samples(before):
        raise ValueError("Native air samples must start empty")


def evaluate_air_salvage(before: Path, after: Path, player: UUID, *, cargo: list[dict], position: dict) -> dict:
    verify_initial_air_salvage(before, player, cargo=cargo, position=position)
    if (before / "livequest-air.json").read_bytes() != (after / "livequest-air.json").read_bytes():
        raise ValueError("Native air observer manifest changed during play")
    result = evaluate_cargo(before, after, player, cargo=cargo, position=position)
    deaths = evaluate_deaths(before, after, player)["deaths"]["count"]
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if closing < opening:
        raise ValueError("Native clock moved backwards")
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
    trace = samples(after)
    previous = opening
    for row in trace:
        if (row["player"] != identity or not previous < row["tick"] <= closing
                or len(row["position"]) != 3
                or not all(math.isfinite(value) for value in row["position"] + [row["health"]])
                or not -20 <= row["air_ticks"] <= 300):
            raise ValueError("Invalid native air sample identity, values or clock")
        previous = row["tick"]
    result["checks"].append({"kind": "no_native_death", "deaths": deaths, "passed": deaths == 0})
    result["success"] = all(row["passed"] for row in result["checks"])
    result["native_elapsed_ticks"] = closing - opening
    result["air_timeline"] = trace
    result["semantics"] = (
        "Both original tagged samples and living settled surface return, without any native death. "
        "Air/effect samples are one-second diagnostics, not a continuous minimum-air guarantee or "
        "a prescribed air-chamber route. Completing before the initial effect expires is legal."
    )
    return result
