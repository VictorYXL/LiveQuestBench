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
    first, last = inventory(initial).get(item, 0), inventory(final).get(item, 0)
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
