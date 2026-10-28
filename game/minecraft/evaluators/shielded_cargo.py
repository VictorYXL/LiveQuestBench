"""Source-bound cargo plus a native skeleton-projectile shield block."""

import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.cargo import evaluate_cargo, verify_initial_cargo
from game.minecraft.fixtures.projectile_blocks import SCHEMA, projectile_hashes


def projectile_events(world: Path) -> list[dict]:
    manifest = json.loads((world / "livequest-shield-evidence.json").read_text())
    if manifest != {"schema": SCHEMA, "pack_sha256": projectile_hashes(world)}:
        raise ValueError("Skeleton projectile evidence manifest or datapack changed")
    stored = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Skeleton projectile evidence requires Minecraft 1.20.4")
    record = stored["data"]["contents"]["shield"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Skeleton projectile storage schema changed")
    events = record["events"]
    if not isinstance(events, nbtlib.List):
        raise ValueError("Skeleton projectile events must be a list")
    return [
        {"kind": str(row["kind"]), "player": list(map(int, row["player"])), "tick": int(row["tick"])}
        for row in events
    ]


def verify_initial_shielded_cargo(before: Path, player: UUID, *, cargo: list[dict], position: dict) -> None:
    verify_initial_cargo(before, player, cargo=cargo, position=position)
    if projectile_events(before):
        raise ValueError("Skeleton projectile evidence must start empty")


def evaluate_shielded_cargo(before: Path, after: Path, player: UUID, *, cargo: list[dict], position: dict) -> dict:
    verify_initial_shielded_cargo(before, player, cargo=cargo, position=position)
    if (before / "livequest-shield-evidence.json").read_bytes() != (
        after / "livequest-shield-evidence.json"
    ).read_bytes():
        raise ValueError("Skeleton projectile manifest changed during play")
    result = evaluate_cargo(before, after, player, cargo=cargo, position=position)
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if closing < opening:
        raise ValueError("Native clock moved backwards")
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
    events = projectile_events(after)
    previous = opening
    for event in events:
        if (event["kind"] != "skeleton_arrow_block" or event["player"] != identity
                or not previous <= event["tick"] <= closing):
            raise ValueError("Invalid projectile event source, player or native clock")
        previous = event["tick"]
    result["checks"].append({
        "kind": "skeleton_projectile_shield_block", "events": events, "passed": bool(events),
    })
    result["success"] = all(check["passed"] for check in result["checks"])
    result["native_elapsed_ticks"] = closing - opening
    result["semantics"] = (
        "Original tagged chest cargo and living settled return, plus at least one native blocked "
        "arrow from a Skeleton attributed to this player. Merely raising a shield is insufficient. "
        "Legal recovery and killing the skeleton are allowed; death is measured separately."
    )
    return result
