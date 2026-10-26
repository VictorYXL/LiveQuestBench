"""Native crafted-weapon kill credit and a living return, from frozen world evidence."""

import json
import math
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.fixtures.forge_hunt import OUTPOST_SCHEMA, SCHEMA, TARGET, pack_hashes, route_gates, targets_for, uuid_parts
from game.minecraft.fixtures.trade_hunt import MERCHANTS, SCHEMA as TRADE_SCHEMA, SMITH, pack_hashes as trade_hashes
from game.minecraft.fixtures import lost_expedition


def registry(world: Path) -> dict:
    value = json.loads((world / "livequest-expedition.json").read_text())
    encounters = 2 if value["schema"] in (OUTPOST_SCHEMA, TRADE_SCHEMA) else 1
    hashes = trade_hashes(world) if value["schema"] == TRADE_SCHEMA else pack_hashes(world, encounters)
    if value["schema"] not in (SCHEMA, OUTPOST_SCHEMA, TRADE_SCHEMA, lost_expedition.SCHEMA) or hashes != value["pack_sha256"]:
        raise ValueError("Expedition fixture or passive evidence datapack changed")
    if value["schema"] == lost_expedition.SCHEMA and (
            value["targets"] != lost_expedition.TARGETS or value["merchants"] != lost_expedition.MERCHANTS
            or value["folios"] != list(lost_expedition.FOLIOS)):
        raise ValueError("Lost expedition native identities or folios changed")
    if value["schema"] == TRADE_SCHEMA and value["merchants"] != MERCHANTS:
        raise ValueError("Merchant identities differ from the native purchase predicate")
    if encounters == 2 and (value["targets"] != targets_for(2) or value["cargo"] != "outpost_records"):
        raise ValueError("Outpost targets or cargo differ from the native evidence predicates")
    if "route_condition" in value or "route_gates" in value:
        if (value["schema"] != OUTPOST_SCHEMA
                or value["route_gates"] != route_gates(value["route_condition"])):
            raise ValueError("Reconnaissance route registry differs from the authored condition")
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
    if expected["schema"] in (OUTPOST_SCHEMA, TRADE_SCHEMA):
        if opening["targets"] != expected["targets"] or cargo_count(world, player):
            raise ValueError("Outpost targets must start alive at full health, with cargo absent from the player")
    if "route_gates" in expected and opening.get("route_gates") != expected["route_gates"]:
        raise ValueError("Reconnaissance opening lacks native passage validation")
    if expected["schema"] == TRADE_SCHEMA:
        if record["purchases"] or opening["merchants"] != expected["merchants"]:
            raise ValueError("Trade expedition requires fresh merchants and no previous purchase receipt")
    if expected["schema"] == lost_expedition.SCHEMA:
        if (opening["targets"] != expected["targets"] or opening["merchants"] != expected["merchants"]
                or folios(world, player)):
            raise ValueError("Lost expedition requires fresh targets, merchants and no initial folios")


def folios(world: Path, player: UUID) -> set[str]:
    native = nbtlib.load(world / "playerdata" / f"{player}.dat")
    return {str(item.get("tag", {}).get("livequest_folio", "")) for item in native["Inventory"]
            if str(item["id"]) == "minecraft:paper" and int(item["Count"]) > 0
            and str(item.get("tag", {}).get("livequest_folio", "")) in lost_expedition.FOLIOS}


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
    trading = expected["schema"] == TRADE_SCHEMA
    purchase = None
    sequences = set()
    if trading:
        if len(record["purchases"]) > 1:
            raise ValueError("Ambiguous first native weapon purchase")
        for receipt in record["purchases"]:
            if (list(receipt["player"]) != uuid_parts(player) or str(receipt["merchant"]) != SMITH
                    or str(receipt["item"]) != "minecraft:iron_axe"
                    or int(receipt["tick"]) < 0 or int(receipt["sequence"]) <= 0):
                raise ValueError("Native purchase receipt has wrong identity, item or event sequence")
            purchase = receipt
            sequences.add(int(receipt["sequence"]))
    for kill in kills:
        role = str(kill["role"])
        if (role not in roles or role in seen or list(kill["player"]) != uuid_parts(player)
                or int(kill["tick"]) < 0 or min(int(kill["stone"]), int(kill["iron"])) < 0):
            raise ValueError("Native kill receipt has wrong actor, role or counters")
        seen.add(role)
        if trading:
            sequence = int(kill["sequence"])
            if sequence <= 0 or sequence in sequences:
                raise ValueError("Native trade/kill event sequence is invalid or duplicated")
            sequences.add(sequence)
            if (purchase is not None and sequence > int(purchase["sequence"])
                    and int(kill["tick"]) >= int(purchase["tick"])
                    and str(kill["hand"]) == str(purchase["item"])):
                qualified.add(role)
        elif expected["schema"] == lost_expedition.SCHEMA:
            qualified.add(role)
        elif ((str(kill["hand"]) == "minecraft:stone_sword" and int(kill["stone"]) > 0)
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
        {"kind": ("native_kill" if expected["schema"] == lost_expedition.SCHEMA else
                  "traded_weapon_native_kill" if trading else "crafted_weapon_native_kill"), "passed": qualified == roles},
        {"kind": "survival", "health": health, "deaths": death_delta, "passed": health > 0 and death_delta == 0},
        {"kind": "return", "horizontal_error": horizontal, "vertical_error": vertical,
         "motion_blocks_per_tick": speed, "passed": str(native["Dimension"]) == "minecraft:overworld"
         and bool(native["OnGround"]) and horizontal <= 2 and vertical <= .5 and speed <= .1},
    ]
    if expected["schema"] in (OUTPOST_SCHEMA, TRADE_SCHEMA):
        checks.insert(1, {"kind": "outpost_kills", "required": sorted(roles), "qualified": sorted(qualified),
                          "passed": qualified == roles})
        amount = cargo_count(after, player)
        checks.append({"kind": "cargo_return", "count": amount, "passed": amount == 1})
    if trading:
        checks.append({"kind": "native_weapon_purchase", "passed": purchase is not None})
        return {"success": all(check["passed"] for check in checks), "checks": checks,
                "semantics": "Native villager_trade for an iron axe from the exact authored weaponsmith, "
                "followed in native event order by both designated player_killed_entity receipts holding that "
                "weapon type. This is purchase/type provenance, not unique-item tracking or last-damage proof. "
                "Same-player death-free grounded cargo return; coal sales and food purchases are not mandatory score steps."}
    if expected["schema"] == lost_expedition.SCHEMA:
        recovered = folios(after, player)
        checks.append({"kind": "folio_return", "required": list(lost_expedition.FOLIOS),
                       "recovered": sorted(recovered), "passed": recovered == set(lost_expedition.FOLIOS)})
        return {"success": all(check["passed"] for check in checks), "checks": checks,
                "semantics": "Exact native Archive Sentinel player kill credit, all three distinct authored "
                "paper folios carried by the same living player on grounded camp return, and no deaths. "
                "No required weapon, crafting recipe, trade, route, construction or discovery order. "
                "Native identity tags distinguish genuine folios from renamed or duplicated ordinary paper; "
                "completion does not itself prove adaptation or memory use."}
    return {"success": all(check["passed"] for check in checks), "checks": checks,
            "semantics": "Native player_killed_entity for the exact authored UUID, with a held stone/iron "
            "sword and a positive native crafted counter for that sword type at the kill. "
            "No particular recovery action required; same-player death-free return. "
            "This is native kill credit, not an exclusive last-damage attribution claim."}
