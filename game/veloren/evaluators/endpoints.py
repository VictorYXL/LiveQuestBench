"""Private before/after position, inventory and health checks with evidence integrity."""

import hashlib
import json
import math
from pathlib import Path


def finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def load_pair(before: Path, after: Path) -> tuple[dict, dict]:
    rows = []
    metadata = []
    for path, phase in ((before, "ready"), (after, "ended")):
        data = (Path(path) / "observation.json").read_bytes()
        meta = json.loads((Path(path) / "_livequest_snapshot.json").read_text())
        if (meta["schema"] != "veloren-endpoint-v1" or meta["phase"] != phase
                or meta["sha256"] != hashlib.sha256(data).hexdigest()):
            raise ValueError("Invalid endpoint identity, phase or evidence checksum")
        row = json.loads(data)
        if row["session_id"] != meta["session_id"]:
            raise ValueError("Observation and endpoint identity disagree")
        rows.append(row)
        metadata.append(meta)
    if rows[0]["session_id"] != rows[1]["session_id"]:
        raise ValueError("Cannot compare different native sessions")
    if rows[0]["self_identity"] != rows[1]["self_identity"]:
        raise ValueError("Cannot compare different native actors")
    if metadata[0]["captured_at_ns"] > metadata[1]["capture_started_at_ns"]:
        raise ValueError("Endpoint captures are reversed or overlap")
    return rows[0], rows[1]


def validate_displacement(*, min_distance: float = 2) -> float:
    threshold = finite(min_distance, "min_distance")
    if threshold <= 0:
        raise ValueError("min_distance must be positive")
    return threshold


def evaluate_displacement(before: Path, after: Path, *, min_distance: float = 2) -> dict:
    threshold = validate_displacement(min_distance=min_distance)
    initial, final = load_pair(before, after)
    points = []
    for row in (initial, final):
        point = row["position"]
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("Missing native XYZ position")
        points.append([finite(value, "position") for value in point])
    distance = math.dist(points[0][:2], points[1][:2])
    health = finite(final["survival"]["health"]["current"], "health")
    return {"success": distance >= threshold and health > 0,
            "horizontal_distance": distance, "min_distance": threshold,
            "position_before": points[0], "position_after": points[1], "health_after": health}


def inventory_counts(row: dict) -> dict[str, int]:
    items = row["inventory"]["items"]
    if not isinstance(items, list):
        raise ValueError("Inventory items must be present")
    result: dict[str, int] = {}
    for entry in items:
        item = entry["item"]
        identifier = item["id"]
        name = (identifier["Simple"] if isinstance(identifier, dict) and set(identifier) == {"Simple"}
                else json.dumps(identifier, sort_keys=True, separators=(",", ":"))
                if isinstance(identifier, dict) and identifier else identifier)
        count = item["amount"]
        if not isinstance(name, str) or type(count) is not int or count < 0:
            raise ValueError("Unsupported native item identity or amount")
        result[name] = result.get(name, 0) + count
    return result


def validate_inventory(*, item: str, min_count: int | None = None, min_delta: int | None = None) -> None:
    thresholds = [value for value in (min_count, min_delta) if value is not None]
    if not isinstance(item, str) or not item or not thresholds or any(
        type(value) is not int or value < 0 for value in thresholds
    ):
        raise ValueError("Provide an item and at least one nonnegative integer threshold")


def evaluate_inventory(
    before: Path, after: Path, *, item: str, min_count: int | None = None, min_delta: int | None = None,
) -> dict:
    validate_inventory(item=item, min_count=min_count, min_delta=min_delta)
    initial, final = load_pair(before, after)
    first, last = inventory_counts(initial).get(item, 0), inventory_counts(final).get(item, 0)
    return {"success": (min_count is None or last >= min_count)
            and (min_delta is None or last - first >= min_delta),
            "item": item, "count_before": first, "count_after": last, "delta": last - first}


def validate_health(
    *, min_health: float | None = None, min_delta: float | None = None,
) -> tuple[float | None, float | None]:
    if min_health is None and min_delta is None:
        raise ValueError("Provide at least one health threshold")
    threshold = finite(min_health, "min_health") if min_health is not None else None
    delta = finite(min_delta, "min_delta") if min_delta is not None else None
    if threshold is not None and threshold < 0:
        raise ValueError("min_health must be nonnegative")
    return threshold, delta


def evaluate_health(
    before: Path, after: Path, *, min_health: float | None = None, min_delta: float | None = None,
) -> dict:
    threshold, delta = validate_health(min_health=min_health, min_delta=min_delta)
    initial, final = load_pair(before, after)
    first, last = (finite(row["survival"]["health"]["current"], "health") for row in (initial, final))
    return {"success": (threshold is None or last >= threshold)
            and (delta is None or last - first >= delta),
            "health_before": first, "health_after": last, "delta": last - first}


def validate_state(
    *, inventory: list[dict] | None = None, equipment: dict[str, str] | None = None,
    recipes: list[str] | None = None, position: dict | None = None, min_health: float = 1,
) -> None:
    if finite(min_health, "min_health") <= 0:
        raise ValueError("min_health must be positive")
    if inventory is not None:
        if not isinstance(inventory, list) or not inventory:
            raise ValueError("inventory must contain requirements")
        seen = set()
        for row in inventory:
            if not isinstance(row, dict) or set(row) - {"item", "min_count", "max_count", "min_delta"}:
                raise ValueError("Invalid inventory requirement")
            item = row.get("item")
            thresholds = {key: row[key] for key in ("min_count", "max_count", "min_delta") if key in row}
            if (not isinstance(item, str) or not item or item in seen or not thresholds
                    or any(type(value) is not int or value < 0 for value in thresholds.values())
                    or row.get("max_count", math.inf) < row.get("min_count", 0)):
                raise ValueError("Invalid inventory item or thresholds")
            seen.add(item)
    if equipment is not None and (
        not isinstance(equipment, dict) or not equipment
        or any(not isinstance(slot, str) or not slot or not isinstance(item, str) or not item
               for slot, item in equipment.items())
    ):
        raise ValueError("equipment must map slots to item identifiers")
    if recipes is not None and (
        not isinstance(recipes, list) or not recipes
        or any(not isinstance(recipe, str) or not recipe for recipe in recipes)
        or len(set(recipes)) != len(recipes)
    ):
        raise ValueError("recipes must contain unique recipe identifiers")
    if position is not None:
        required = {"target", "horizontal_tolerance", "vertical_tolerance", "max_speed"}
        if not isinstance(position, dict) or set(position) != required:
            raise ValueError(f"position requires exactly {sorted(required)}")
        point = position["target"]
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("position.target must contain native XYZ")
        for value in point:
            finite(value, "position.target")
        for key in required - {"target"}:
            if finite(position[key], key) < 0:
                raise ValueError(f"{key} must be nonnegative")


def known_recipes(row: dict, *, required: list[str] | None = None) -> set[str]:
    value = row["known_recipes"]
    if (not isinstance(value, dict) or type(value.get("total")) is not int
            or type(value.get("omitted")) is not int or value["omitted"] < 0):
        raise ValueError("Native recipe evidence must include recipe count metadata")
    entries = value["items"]
    if not isinstance(entries, list) or value["total"] != len(entries) + value["omitted"]:
        raise ValueError("Native recipe count does not match the entries")
    result = set()
    seen = set()
    for entry in entries:
        name = entry["recipe"]
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Invalid native recipe identifier")
        seen.add(name)
        # The native known_recipes list contains learned recipes, not all manifest recipes.
        known = entry.get("character_known", True)
        if type(known) is not bool:
            raise ValueError("Invalid native recipe knowledge")
        if known:
            result.add(name)
    for name, query in row.get("private_recipe_evidence", {}).items():
        matches = [entry for entry in query["items"] if entry["recipe"] == name]
        if len(matches) != 1 or type(matches[0].get("character_known")) is not bool:
            raise ValueError("Invalid private native recipe evidence")
        known = matches[0]["character_known"]
        if name in seen and (name in result) != known:
            raise ValueError("Conflicting native recipe knowledge")
        seen.add(name)
        if known:
            result.add(name)
    if value["omitted"] and (required is None or set(required) - seen):
        raise ValueError("Truncated native recipe evidence cannot establish missing recipe knowledge")
    return result


def evaluate_state(
    before: Path, after: Path, *, inventory: list[dict] | None = None,
    equipment: dict[str, str] | None = None, recipes: list[str] | None = None,
    position: dict | None = None, min_health: float = 1,
) -> dict:
    """Require simultaneous terminal predicates, never infer actions or past survival."""
    validate_state(inventory=inventory, equipment=equipment, recipes=recipes,
                   position=position, min_health=min_health)
    initial, final = load_pair(before, after)
    return state_checks(initial, final, inventory=inventory, equipment=equipment,
                        recipes=recipes, position=position, min_health=min_health)


def state_checks(
    initial: dict, final: dict, *, inventory: list[dict] | None = None,
    equipment: dict[str, str] | None = None, recipes: list[str] | None = None,
    position: dict | None = None, min_health: float = 1,
) -> dict:
    checks = []
    hp = finite(final["survival"]["health"]["current"], "health")
    checks.append({"kind": "health", "actual": hp, "minimum": min_health,
                   "passed": hp >= min_health and final["survival"].get("dead") is not True
                   and final["survival"]["health"].get("dead") is not True})
    if inventory:
        first, last = inventory_counts(initial), inventory_counts(final)
        for row in inventory:
            old, new = first.get(row["item"], 0), last.get(row["item"], 0)
            checks.append({"kind": "inventory", **row, "before": old, "after": new, "delta": new - old,
                           "passed": new >= row.get("min_count", 0)
                           and new <= row.get("max_count", math.inf)
                           and ("min_delta" not in row or new - old >= row["min_delta"])})
    if equipment:
        from game.veloren.fixture import item_id
        slots = final["inventory"]["equipment"]
        for slot, expected in equipment.items():
            if slot not in slots:
                raise ValueError(f"Native equipment slot is missing: {slot}")
            actual = item_id(slots[slot]) if slots[slot] is not None else None
            checks.append({"kind": "equipment", "slot": slot, "expected": expected,
                           "actual": actual, "passed": actual == expected})
    if recipes:
        known = known_recipes(final, required=recipes)
        checks.extend({"kind": "recipe", "recipe": recipe, "passed": recipe in known} for recipe in recipes)
    if position:
        point, velocity = final["position"], final["velocity"]
        if any(not isinstance(value, list) or len(value) != 3 for value in (point, velocity)):
            raise ValueError("Native position and velocity must contain XYZ")
        point = [finite(value, "position") for value in point]
        speed = math.sqrt(sum(finite(value, "velocity") ** 2 for value in velocity))
        if type(final["on_ground"]) is not bool:
            raise ValueError("Native on_ground must be boolean")
        horizontal = math.dist(point[:2], position["target"][:2])
        vertical = abs(point[2] - position["target"][2])
        checks.append({"kind": "position", "actual": point, "horizontal_error": horizontal,
                       "vertical_error": vertical, "speed": speed, "on_ground": final["on_ground"],
                       "passed": horizontal <= position["horizontal_tolerance"]
                       and vertical <= position["vertical_tolerance"]
                       and speed <= position["max_speed"] and final["on_ground"]})
    return {"success": all(row["passed"] for row in checks), "checks": checks,
            "semantics": "simultaneous terminal state; no action attribution or continuous-survival claim"}
