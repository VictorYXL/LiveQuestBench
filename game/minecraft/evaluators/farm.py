"""Farm products, replanted native crops and exact surviving bred offspring."""

import hashlib
import gzip
from io import BytesIO
import json
from pathlib import Path
from uuid import UUID
import zlib

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.fixtures.farm import SCHEMA, expected_hashes


def saved_alive_sheep(world):
    alive, seen = [], set()
    for dimension in ("", "DIM-1", "DIM1"):
        folder = world / dimension / "entities"
        for path in folder.glob("r.*.*.mca"):
            _, rx, rz, _ = path.name.split(".")
            with path.open("rb") as stream:
                header = stream.read(8192)
                if not header:
                    continue
                if len(header) != 8192:
                    raise ValueError("Truncated native entity region")
                for index in range(1024):
                    entry = header[index * 4:index * 4 + 4]
                    sector, sectors = int.from_bytes(entry[:3], "big"), entry[3]
                    if sector == sectors == 0:
                        continue
                    if sector < 2 or not sectors:
                        raise ValueError("Invalid native entity chunk location")
                    x, z = int(rx) * 32 + index % 32, int(rz) * 32 + index // 32
                    stream.seek(sector * 4096)
                    size = int.from_bytes(stream.read(4), "big")
                    if not 1 <= size <= sectors * 4096 - 4:
                        raise ValueError("Invalid native entity chunk size")
                    payload = stream.read(size)
                    if len(payload) != size:
                        raise ValueError("Truncated native entity chunk")
                    codec, raw = payload[0], payload[1:]
                    if codec & 128:
                        if size != 1:
                            raise ValueError("Invalid external native entity chunk")
                        raw = (folder / f"c.{x}.{z}.mcc").read_bytes()
                        codec &= 127
                    if codec == 1:
                        raw = gzip.decompress(raw)
                    elif codec == 2:
                        raw = zlib.decompress(raw)
                    elif codec != 3:
                        raise ValueError("Unsupported native entity compression")
                    chunk = nbtlib.File.parse(BytesIO(raw))
                    if int(chunk["DataVersion"]) != 3700 or list(map(int, chunk["Position"])) != [x, z]:
                        raise ValueError("Native entity version or chunk position changed")
                    pending = list(chunk["Entities"])
                    while pending:
                        entity = pending.pop()
                        pending.extend(entity.get("Passengers", []))
                        if str(entity["id"]) != "minecraft:sheep":
                            continue
                        identity = tuple(map(int, entity["UUID"]))
                        if len(identity) != 4 or identity in seen:
                            raise ValueError("Missing or duplicate native sheep identity")
                        seen.add(identity)
                        if float(entity["Health"]) > 0:
                            alive.append(list(identity))
    return alive


def farm_evidence(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-farm.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Farm breeding observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_farm" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Farm breeding observer implementation changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Breeding evidence requires native Minecraft 1.20.4")
    record = native["data"]["contents"]["farm"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Farm breeding storage identity changed")
    return {
        "events": [{"player": list(map(int, e["player"])), "tick": int(e["tick"]),
                    "captured_tick": int(e["captured_tick"]),
                    "children": [list(map(int, child)) for child in e["children"]]} for e in record["events"]],
        "alive": [list(map(int, child)) for child in record["alive"]],
    }


def surviving_offspring(evidence, player, first, last):
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    children = []
    for event in evidence["events"]:
        if event["player"] != identity or not first <= event["tick"] <= last:
            raise ValueError("Breeding event has the wrong player or native time")
        if event["captured_tick"] != event["tick"] + 1 or event["captured_tick"] > last:
            raise ValueError("Newborn capture must follow the breeding event by exactly one native tick")
        if len(event["children"]) != 1 or len(event["children"][0]) != 4:
            raise ValueError("Native breeding child attribution is missing or ambiguous")
        children.append(event["children"][0])
    return [child for child in children if child in evidence["alive"]]


def evaluate_farm(before: Path, after: Path, player: UUID, **state):
    initial, final = farm_evidence(before), farm_evidence(after)
    if initial["events"] or initial["alive"]:
        raise ValueError("Farm task must start with no previous offspring")
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    sampled_alive = final["alive"]
    final["alive"] = saved_alive_sheep(after)
    alive = surviving_offspring(final, player, first, last)
    result = evaluate_state(before, after, player, **state)
    result["checks"].append({"kind": "original_pair_bred_surviving_offspring", "alive": alive, "passed": bool(alive)})
    result["success"] = all(check["passed"] for check in result["checks"])
    result["breeding_events"] = final["events"]
    result["sampled_loaded_offspring"] = sampled_alive
    result["semantics"] += (
        " A vanilla bred_animals advancement binds both initialized parents and the player; "
        "one previously absent newborn must be observed near the original parent exactly one tick later "
        "and its UUID must still be alive in saved native entity data, including unloaded chunks "
        "and vehicle passengers. Missing or ambiguous newborns invalidate attribution; "
        "preexisting nearby sheep do not satisfy breeding."
    )
    return result
