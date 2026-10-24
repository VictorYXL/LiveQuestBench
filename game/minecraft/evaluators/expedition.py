"""Native crafted-weapon kill credit and a living return, from frozen world evidence."""

import json
import math
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.fixtures.forge_hunt import OUTPOST_SCHEMA, SCHEMA, TARGET, pack_hashes, targets_for, uuid_parts


def registry(world: Path) -> dict:
    value = json.loads((world / "livequest-expedition.json").read_text())
    encounters = 2 if value["schema"] == OUTPOST_SCHEMA else 1
    if value["schema"] not in (SCHEMA, OUTPOST_SCHEMA) or pack_hashes(world, encounters) != value["pack_sha256"]:
        raise ValueError("Expedition fixture or passive evidence datapack changed")
    if encounters == 2 and (value["targets"] != targets_for(2) or value["cargo"] != "outpost_records"):
        raise ValueError("Outpost targets or cargo differ from the native evidence predicates")
    if UUID(value["target_uuid"]) != TARGET or value["target_type"] != "minecraft:husk":
        raise ValueError("Expedition target must match the passive datapack's native predicate")
    point = value["return_position"]
    if (not isinstance(point, list) or len(point) != 3
            or any(type(coordinate) not in (int, float) or not math.isfinite(coordinate) for coordinate in point)):
        raise ValueError("Expedition return position must contain three finite coordinates")
    return value


def evidence(world: Path) -> dict:
    data = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(data["DataVersion"]) != 3700:
        raise ValueError("Expedition evidence requires Minecraft 1.20.4")
    return data["data"]["contents"]["expedition"]


def verify_initial(world: Path, player: UUID) -> None:
    expected = registry(world)
    record = evidence(world)
    opening = json.loads((world / "livequest-opening.json").read_text())
    if (record["state"]["schema"] != expected["schema"] or record["state"]["target"] != expected["target_uuid"]
            or record["kills"] or opening["target_uuid"] != expected["target_uuid"]
            or type(opening["health"]) not in (int, float) or not math.isfinite(opening["health"])
            or opening["health"] <= 0 or opening["player_uuid"] != str(player)):
        raise ValueError("Expedition requires a fresh living target and empty native kill evidence")
    if expected["schema"] == OUTPOST_SCHEMA:
        if opening["targets"] != expected["targets"] or cargo_count(world, player):
            raise ValueError("Outpost targets must start alive at full health, with cargo absent from the player")


def cargo_count(world: Path, player: UUID) -> int:
    native = nbtlib.load(world / "playerdata" / f"{player}.dat")
    return sum(int(item["Count"]) for item in native["Inventory"]
               if str(item["id"]) == "minecraft:paper"
               and str(item.get("tag", {}).get("livequest_cargo", "")) == "outpost_records")


def deaths(world: Path, player: UUID) -> int:
    path = world / "stats" / f"{player}.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    if data["DataVersion"] != 3700:
        raise ValueError("Expedition statistics require Minecraft 1.20.4")
    value = data["stats"].get("minecraft:custom", {}).get("minecraft:deaths", 0)
    if type(value) is not int or value < 0:
        raise ValueError("Invalid native player death count")
    return value


def evaluate_expedition(before: Path, after: Path, player: UUID) -> dict:
    verify_initial(before, player)
    expected = registry(before)
    if registry(after) != expected:
        raise ValueError("Expedition registry changed during play")
    record = evidence(after)
    if record["state"] != evidence(before)["state"]:
        raise ValueError("Native expedition evidence identity changed")
    kills = record["kills"]
    targets = expected.get("targets", targets_for())
    roles = {enemy["role"] for enemy in targets}
    if len(kills) > len(targets):
        raise ValueError("Ambiguous native designated-target kill evidence")
    qualified = set()
    seen = set()
    for kill in kills:
        role = str(kill["role"])
        if (role not in roles or role in seen or list(kill["player"]) != uuid_parts(player)
                or int(kill["tick"]) < 0 or min(int(kill["stone"]), int(kill["iron"])) < 0):
            raise ValueError("Native kill receipt has wrong actor, role or counters")
        seen.add(role)
        if ((str(kill["hand"]) == "minecraft:stone_sword" and int(kill["stone"]) > 0)
                or (str(kill["hand"]) == "minecraft:iron_sword" and int(kill["iron"]) > 0)):
            qualified.add(role)
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    if int(native["DataVersion"]) != 3700 or list(native["UUID"]) != uuid_parts(player):
        raise ValueError("Final player evidence identity changed")
    position = [float(value) for value in native["Pos"]]
    motion = [float(value) for value in native["Motion"]]
    health = float(native["Health"])
    if not all(math.isfinite(value) for value in (*position, *motion, health)):
        raise ValueError("Non-finite native player state")
    target = expected["return_position"]
    horizontal = math.hypot(position[0] - target[0], position[2] - target[2])
    vertical = abs(position[1] - target[1])
    speed = math.sqrt(sum(value * value for value in motion))
    death_delta = deaths(after, player) - deaths(before, player)
    if death_delta < 0:
        raise ValueError("Native death counter moved backwards")
    checks = [
        {"kind": "crafted_weapon_native_kill", "passed": qualified == roles},
        {"kind": "survival", "health": health, "deaths": death_delta, "passed": health > 0 and death_delta == 0},
        {"kind": "return", "horizontal_error": horizontal, "vertical_error": vertical,
         "motion_blocks_per_tick": speed, "passed": str(native["Dimension"]) == "minecraft:overworld"
         and bool(native["OnGround"]) and horizontal <= 2 and vertical <= .5 and speed <= .1},
    ]
    if expected["schema"] == OUTPOST_SCHEMA:
        checks.insert(1, {"kind": "outpost_kills", "required": sorted(roles), "qualified": sorted(qualified),
                          "passed": qualified == roles})
        amount = cargo_count(after, player)
        checks.append({"kind": "cargo_return", "count": amount, "passed": amount == 1})
    return {"success": all(check["passed"] for check in checks), "checks": checks,
            "semantics": "Native player_killed_entity for the exact authored UUID, with a held stone/iron "
            "sword and a positive native crafted counter for that sword type at the kill. "
            "No particular recovery action required; same-player death-free return. "
            "This is native kill credit, not an exclusive last-damage attribution claim."}
