"""Native player endpoints and vanilla statistic deltas, without action proxies."""

import json
import math
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.inventory import evaluate_inventory, validate_requirements
from game.minecraft.evaluators.structure import evaluate_structure, validate_config
from game.minecraft.fixtures.forge_hunt import uuid_parts
from game.minecraft.fixtures.workshop import ACTION_SCHEMA, action_hashes


def validate_state(
    *, inventory: list[dict] | None = None, position: dict | None = None,
    held_item: str | None = None, min_food: int | None = None,
    statistics: dict[str, int] | None = None, min_health: float = 1,
    structure: dict | None = None, action_sequence: list[str] | None = None, no_death: bool = False,
) -> None:
    if not any(value is not None for value in (
        inventory, position, held_item, min_food, statistics, structure, action_sequence,
    )):
        raise ValueError("State evaluation requires a goal predicate")
    if type(no_death) is not bool:
        raise ValueError("no_death must be boolean")
    if structure is not None:
        validate_config(structure)
    if action_sequence is not None and action_sequence != ["block", "damage"]:
        raise ValueError("The supported native action sequence is block then damage")
    if type(min_health) not in (int, float) or not math.isfinite(min_health) or not 0 < min_health <= 20:
        raise ValueError("min_health must be finite and in (0, 20]")
    if inventory is not None:
        validate_requirements(inventory)
    if held_item is not None:
        validate_requirements([{"item": held_item, "min_count": 1}])
    if min_food is not None and (type(min_food) is not int or not 0 <= min_food <= 20):
        raise ValueError("min_food must be an integer in [0, 20]")
    if position is not None:
        required = {"target", "horizontal_tolerance", "vertical_tolerance", "max_speed"}
        if not isinstance(position, dict) or set(position) != required:
            raise ValueError("Position requires target, horizontal_tolerance, vertical_tolerance and max_speed")
        point = position["target"]
        if not isinstance(point, list) or len(point) != 3 or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in point
        ):
            raise ValueError("Position target must contain finite native XYZ")
        for key in required - {"target"}:
            value = position[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("Position tolerances and max_speed must be finite and nonnegative")
    if statistics is not None and (
        not isinstance(statistics, dict) or not statistics
        or any(key not in ("open_chest", "damage_dealt", "jump")
               or type(value) is not int or value < 1 for key, value in statistics.items())
    ):
        raise ValueError("Statistics require positive native open_chest, damage_dealt or jump deltas")


def custom_statistics(world: Path, player: UUID) -> dict:
    path = world / "stats" / f"{player}.json"
    # Vanilla does not create a statistics file until the player has statistics.
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if value["DataVersion"] != 3700:
        raise ValueError("State evaluation requires Minecraft 1.20.4 statistics")
    result = value["stats"].get("minecraft:custom", {})
    if not isinstance(result, dict) or any(type(v) is not int or v < 0 for v in result.values()):
        raise ValueError("Invalid native custom statistics")
    return result


def action_events(world: Path) -> list[dict]:
    manifest = json.loads((world / "livequest-action-evidence.json").read_text())
    if manifest != {"schema": ACTION_SCHEMA, "pack_sha256": action_hashes(world)}:
        raise ValueError("Native action evidence registry or datapack hashes changed")
    stored = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(stored["DataVersion"]) != 3700:
        raise ValueError("Native action storage requires Minecraft 1.20.4")
    record = stored["data"]["contents"]["actions"]
    if str(record["schema"]) != ACTION_SCHEMA:
        raise ValueError("Native action storage identity changed")
    events = record["events"]
    if not isinstance(events, nbtlib.List):
        raise ValueError("Native action events must be a list")
    return [{"kind": str(row["kind"]), "player": list(map(int, row["player"])), "tick": int(row["tick"])}
            for row in events]


def evaluate_state(
    before: Path, after: Path, player: UUID, *, inventory: list[dict] | None = None,
    position: dict | None = None, held_item: str | None = None,
    min_food: int | None = None, statistics: dict[str, int] | None = None,
    min_health: float = 1,
    structure: dict | None = None, action_sequence: list[str] | None = None, no_death: bool = False,
) -> dict:
    validate_state(inventory=inventory, position=position, held_item=held_item,
                   min_food=min_food, statistics=statistics, min_health=min_health,
                   structure=structure, action_sequence=action_sequence, no_death=no_death)
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("State evaluation requires Minecraft 1.20.4 player data")
    health = float(native["Health"])
    if not math.isfinite(health):
        raise ValueError("Invalid native health")
    checks = [{"kind": "health", "actual": health, "minimum": min_health, "passed": health >= min_health}]
    if no_death:
        first = custom_statistics(before, player).get("minecraft:deaths", 0)
        last = custom_statistics(after, player).get("minecraft:deaths", 0)
        if last < first:
            raise ValueError("Native death count moved backwards")
        checks.append({"kind": "no_death", "delta": last - first, "passed": first == last})
    if inventory is not None:
        checks.extend({"kind": "inventory", **check} for check in
                      evaluate_inventory(before, after, player, inventory)["checks"])
    if min_food is not None:
        food = int(native["foodLevel"])
        if not 0 <= food <= 20:
            raise ValueError("Invalid native food level")
        checks.append({"kind": "food", "actual": food, "minimum": min_food, "passed": food >= min_food})
    if held_item is not None:
        selected = int(native["SelectedItemSlot"])
        if not 0 <= selected <= 8:
            raise ValueError("Invalid native selected hotbar slot")
        stacks = [stack for stack in native["Inventory"] if int(stack["Slot"]) == selected]
        if len(stacks) > 1:
            raise ValueError("Duplicate selected inventory slot")
        actual = str(stacks[0]["id"]) if stacks and int(stacks[0]["Count"]) > 0 else None
        expected = held_item if ":" in held_item else "minecraft:" + held_item
        checks.append({"kind": "held_item", "slot": selected, "actual": actual,
                       "expected": expected, "passed": actual == expected})
    if position is not None:
        point, motion = list(map(float, native["Pos"])), list(map(float, native["Motion"]))
        if len(point) != 3 or len(motion) != 3 or any(not math.isfinite(v) for v in point + motion):
            raise ValueError("Invalid native position or motion")
        horizontal = math.dist((point[0], point[2]), (position["target"][0], position["target"][2]))
        vertical = abs(point[1] - position["target"][1])
        speed = math.sqrt(sum(v * v for v in motion))
        grounded = bool(native["OnGround"])
        checks.append({"kind": "position", "horizontal_error": horizontal, "vertical_error": vertical,
                       "motion_blocks_per_tick": speed, "on_ground": grounded,
                       "passed": str(native["Dimension"]) == "minecraft:overworld" and grounded
                       and horizontal <= position["horizontal_tolerance"]
                       and vertical <= position["vertical_tolerance"] and speed <= position["max_speed"]})
    if statistics is not None:
        initial, final = custom_statistics(before, player), custom_statistics(after, player)
        for name, minimum in statistics.items():
            key = "minecraft:" + name
            delta = final.get(key, 0) - initial.get(key, 0)
            if delta < 0:
                raise ValueError("Native statistic moved backwards")
            checks.append({"kind": "statistic", "name": name, "delta": delta,
                           "minimum": minimum, "passed": delta >= minimum})
    if structure is not None:
        result = evaluate_structure(before, after, structure)
        checks.append({"kind": "structure", "passed": result["success"], "result": result})
    if action_sequence is not None:
        if action_events(before):
            raise ValueError("Native action sequence must start empty")
        if (before / "livequest-action-evidence.json").read_bytes() != (
            after / "livequest-action-evidence.json"
        ).read_bytes():
            raise ValueError("Native action manifest changed during play")
        events = action_events(after)
        opening_tick = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
        closing_tick = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
        previous = opening_tick
        matched = []
        for index, event in enumerate(events):
            if (event["kind"] not in ("block", "damage") or event["player"] != uuid_parts(player)
                    or not previous <= event["tick"] <= closing_tick):
                raise ValueError("Invalid native action identity or event ordering")
            previous = event["tick"]
            if len(matched) < len(action_sequence) and event["kind"] == action_sequence[len(matched)]:
                matched.append(index)
        checks.append({"kind": "action_sequence", "expected": action_sequence, "events": events,
                       "matched_indices": matched, "passed": len(matched) == len(action_sequence)})
    semantics = ("Simultaneous native player endpoints and requested vanilla statistic deltas. "
                 "Damage and chest statistics do not identify a particular target or container. "
                 "No hidden route, recipe, continuous survival or exact action sequence is required.")
    if structure is not None or action_sequence is not None or no_death:
        semantics = (
            "Simultaneous native player/structure predicates and any explicitly requested statistic, "
            "no-death and ordered-effect conditions. Native action records bind the player UUID and "
            "Husk damage source/target type, not an exact enemy UUID. Crop state does not prove a "
            "particular harvest/replant history. No hidden route or recipe is required."
        )
    return {"success": all(check["passed"] for check in checks), "checks": checks,
            "semantics": semantics}
