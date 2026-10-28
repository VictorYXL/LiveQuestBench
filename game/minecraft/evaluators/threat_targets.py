"""Read-only, optional native AI-target diagnostics; never a cooperation score."""

from collections import Counter
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.fixtures.threat_targets import SCHEMA, target_hashes


def _uuid(values) -> UUID:
    parts = list(map(int, values))
    if len(parts) != 4 or any(not -(2**31) <= part < 2**31 for part in parts):
        raise ValueError("Invalid native target UUID")
    return UUID(bytes=b"".join(part.to_bytes(4, "big", signed=True) for part in parts))


def summarize_targets(frames, players: dict[str, UUID], opening: int, closing: int) -> dict:
    roles = {value: key for key, value in players.items()}
    enemies, counts, ticks = {}, Counter(), []
    previous = -1
    for frame in frames:
        tick = int(frame["tick"])
        if not previous < tick <= closing:
            raise ValueError("Native target sample clock is invalid")
        previous = tick
        if tick <= opening:
            continue
        ticks.append(tick)
        seen = set()
        for row in frame["enemies"]:
            enemy = _uuid(row["enemy"])
            if enemy in seen:
                raise ValueError("Duplicate enemy in native target sample")
            seen.add(enemy)
            target = _uuid(row["target"]) if "target" in row else None
            is_player = int(row["target_is_player"])
            if is_player not in (0, 1) or (target is None and is_player):
                raise ValueError("Invalid native target kind")
            if target in roles and not is_player:
                raise ValueError("Participant target is not marked as a native player")
            label = (f"participant:{roles[target]}" if target in roles
                     else "other_player" if is_player else "nonplayer" if target else "none")
            record = enemies.setdefault(str(enemy), Counter())
            record[label] += 1
            counts[label] += 1
    return {
        "status": "sampled_native_ai_targets",
        "frames": len(ticks),
        "first_sample_tick": ticks[0] if ticks else None,
        "last_sample_tick": ticks[-1] if ticks else None,
        "maximum_sample_gap_ticks": max((b - a for a, b in zip(ticks, ticks[1:])), default=None),
        "enemy_target_sample_counts": dict(sorted(counts.items())),
        "per_enemy_target_sample_counts": {key: dict(sorted(value.items())) for key, value in enemies.items()},
        "semantics": "Passive snapshots of native skeleton AI targets, including nonplayer targets. "
                     "Counts are enemy-observations, not seconds, attacks or damage attribution. "
                     "Targets may change between samples; arrows already in flight may hit another actor. "
                     "No causal protection or cooperation advantage is inferred.",
    }


def target_diagnostics(before: Path, after: Path, players: dict[str, UUID]) -> dict:
    name = "livequest-target-trace.json"
    if not (before / name).exists() and not (after / name).exists():
        return {"status": "unavailable", "reason": "No optional native AI-target observer."}
    registries = []
    for world in (before, after):
        record = json.loads((world / name).read_text())
        if record != {"schema": SCHEMA, "sample_interval_ticks": 20,
                      "pack_sha256": target_hashes(world)}:
            raise ValueError("Native target observer manifest or datapack changed")
        registries.append(record)
    if registries[0] != registries[1]:
        raise ValueError("Native target observer changed during play")
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if closing < opening:
        raise ValueError("Native target clock moved backwards")
    storage = nbtlib.load(after / "data/command_storage_livequest.dat")
    if int(storage["DataVersion"]) != 3700:
        raise ValueError("Native target samples require Minecraft Java 1.20.4")
    record = storage["data"]["contents"]["targets"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Native target storage schema changed")
    return summarize_targets(record["frames"], players, opening, closing)
