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


def evaluate_displacement(before: Path, after: Path, *, min_distance: float = 2) -> dict:
    threshold = finite(min_distance, "min_distance")
    if threshold <= 0:
        raise ValueError("min_distance must be positive")
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


def inventory(row: dict) -> dict[str, int]:
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


def evaluate_inventory(before: Path, after: Path, *, item: str, min_count: int, min_delta: int = 0) -> dict:
    if not isinstance(item, str) or not item or any(type(value) is not int or value < 0 for value in (min_count, min_delta)):
        raise ValueError("Provide an item and nonnegative integer thresholds")
    initial, final = load_pair(before, after)
    first, last = inventory(initial).get(item, 0), inventory(final).get(item, 0)
    return {"success": last >= min_count and last - first >= min_delta,
            "item": item, "count_before": first, "count_after": last, "delta": last - first}


def evaluate_health(before: Path, after: Path, *, min_health: float, min_delta: float = 0) -> dict:
    threshold, delta = finite(min_health, "min_health"), finite(min_delta, "min_delta")
    if threshold < 0:
        raise ValueError("min_health must be nonnegative")
    initial, final = load_pair(before, after)
    first, last = (finite(row["survival"]["health"]["current"], "health") for row in (initial, final))
    return {"success": last >= threshold and last - first >= delta,
            "health_before": first, "health_after": last, "delta": last - first}
