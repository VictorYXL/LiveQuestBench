"""Identity-bound native route samples and terminal goal checks."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.evaluators.deaths import evaluate_deaths
from game.minecraft.evaluators.world import AIR, read_blocks
from game.minecraft.fixtures.route_transfer import SCHEMA, expected_hashes
from game.route_transfer import build_layout, route_checks, validate_samples


def read_samples(world: Path, player: UUID) -> list[dict]:
    expected = expected_hashes()
    manifest = json.loads((world / "livequest-route-evidence.json").read_text())
    actual = {
        name: hashlib.sha256((world / "datapacks/livequest_route" / name).read_bytes()).hexdigest()
        for name in expected
    }
    if manifest != {"schema": SCHEMA, "pack_sha256": expected} or actual != expected:
        raise ValueError("Native route observer changed")
    stored = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Route evidence requires Minecraft Java 1.20.4")
    record = stored["data"]["contents"]["route"]
    if str(record["schema"]) != SCHEMA or int(record["overflow"]):
        raise ValueError("Native route evidence schema or capacity invalid")
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True)
                for i in range(0, 16, 4)]
    result = []
    for row in record["samples"]:
        if list(map(int, row["player"])) != identity:
            raise ValueError("Native route evidence belongs to another player")
        x, y, z = map(float, row["position"])
        result.append({"sequence": int(row["tick"]), "position": [x, z, y]})
    validate_samples(result)
    if any(b["sequence"] != a["sequence"] + 1 for a, b in zip(result, result[1:])):
        raise ValueError("Native route history has missing game ticks")
    return result


def validate_route(*, variant: int, origin: list[int]) -> None:
    build_layout(variant, tuple(origin))


def verify_layout(world: Path, *, variant: int, origin: list[int]) -> None:
    layout = build_layout(variant, tuple(origin))
    expected = {(x, z, y): {"minecraft:bedrock"} for x, y, z in layout["solid"]}
    for x, y, z in layout["walking"]:
        for dz in (0, 1):
            expected[x, z + dz, y] = AIR | {"minecraft:light"}
    sections = {}
    for point in expected:
        sections.setdefault(tuple(v // 16 for v in point), []).append(point)
    for points in sections.values():
        low = tuple(min(p[i] for p in points) for i in range(3))
        high = tuple(max(p[i] for p in points) for i in range(3))
        blocks = read_blocks(world, low, high, "minecraft:overworld")
        if any(blocks[p] not in expected[p] for p in points):
            raise ValueError("Native route geometry differs from the scored layout")


def evaluate_route(before: Path, after: Path, player: UUID, *, variant: int, origin: list[int]) -> dict:
    layout = build_layout(variant, tuple(origin))
    first, last = read_samples(before, player), read_samples(after, player)
    if last[:len(first)] != first:
        raise ValueError("Native route history changed")
    added = last[max(0, len(first) - 1):]
    opening = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    closing = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if (closing < opening or any(row["sequence"] > opening for row in first)
            or any(not opening <= row["sequence"] <= closing for row in last[len(first):])):
        raise ValueError("Native route sample outside measured play")
    deaths = evaluate_deaths(before, after, player)["deaths"]["count"]
    route = route_checks(added, layout["wings"], layout["application_distance_limit"], deaths=deaths)
    x, y, z = layout["wings"][-1]["exit"]
    result = evaluate_state(before, after, player, position={
        "target": [x + 1, z, y + 1], "horizontal_tolerance": 2,
        "vertical_tolerance": 0.5, "max_speed": 0.1,
    })
    result["checks"].append({"kind": "route_transfer", "passed": route["success"], **route})
    result["success"] = result["success"] and route["success"]
    result["learning_benefit"] = route["learning_benefit"]
    return result
