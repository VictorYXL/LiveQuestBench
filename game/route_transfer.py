"""Vanilla corridor layouts for within-episode route-schema transfer candidates."""

import math


SCHEMA = "native-route-transfer/2"
BRANCH_LENGTH = 32
STEM_LENGTH = 18
BRANCH_BEND = 14
BRANCH_OFFSET = 4
FLOOR_SEPARATION = 32
APPLICATION_ALLOWANCE = 16
ORDERS = ((0, 1, 2), (2, 0, 1), (1, 2, 0))


def rotate(x: int, y: int, quarter_turns: int) -> tuple[int, int]:
    for _ in range(quarter_turns % 4):
        x, y = -y, x
    return x, y


def build_layout(variant: int, origin: tuple[int, int, int], *, headroom: int = 2) -> dict:
    """Build three wings with consistent module exits but changed composition."""
    if type(variant) is not int or not 0 <= variant < 8:
        raise ValueError("variant must be an integer in [0, 7]")
    if len(origin) != 3 or any(type(v) is not int for v in origin):
        raise ValueError("origin must contain three integer coordinates")
    if type(headroom) is not int or headroom not in (2, 3):
        raise ValueError("headroom must be two or three native blocks")
    walking: set[tuple[int, int, int]] = set()
    stairs: set[tuple[int, int, int]] = set()
    wings = []
    start = origin
    for index, order in enumerate(ORDERS):
        turn = index
        ox, oy, z = start

        def point(x, y):
            dx, dy = rotate(x, y, turn)
            return ox + dx, oy + dy, z

        def add(x, y):
            walking.add(point(x, y))

        def gate(x, y):
            corners = [point(x + dx, y + dy) for dx in (0, 1) for dy in (0, 1)]
            return [min(p[0] for p in corners), min(p[1] for p in corners), z]

        x, y = 0, 0
        modules = []
        for cue in order:
            entry = point(x, y)
            for dx in (0, 1):
                for dy in range(STEM_LENGTH + 2):
                    add(x + dx, y + dy)
            # Shallow, separated wall niches identify repeated architectural modules.
            for niche in range(cue + 1):
                for dx in (-2, -1):
                    add(x + dx, y + 1 + niche * 2)
            y += STEM_LENGTH
            for dx in range(-BRANCH_BEND, BRANCH_BEND + 2):
                for dy in (0, 1):
                    add(x + dx, y + dy)
            for direction in (-1, 1):
                for dx in (0, 1):
                    for dy in range(BRANCH_OFFSET + 2):
                        add(x + direction * BRANCH_BEND + dx, y + dy)
                for distance in range(BRANCH_BEND, BRANCH_LENGTH + 1):
                    for dx in (0, 1):
                        for dy in (0, 1):
                            add(x + direction * distance + dx, y + BRANCH_OFFSET + dy)
            y += BRANCH_OFFSET
            side = 1 if variant & (1 << cue) else -1
            wrong = point(x - side * BRANCH_LENGTH, y)
            x += side * BRANCH_LENGTH
            modules.append({
                "cue": cue + 1, "entry": list(entry),
                "exit": list(point(x, y)), "dead_end": list(wrong),
            })
        if index == len(ORDERS) - 1:
            for dx in range(-1, 3):
                for dy in range(7):
                    add(x + dx, y + dy)
            y += 4
        wings.append({
            "phase": "practice" if index == 0 else "application",
            "entry": gate(0, 0), "exit": gate(x, y), "rotation": turn,
            "modules": modules,
            "reference_distance": len(order) * (BRANCH_LENGTH + STEM_LENGTH + BRANCH_OFFSET)
            + (4 if index == len(ORDERS) - 1 else 0),
        })
        if index < len(ORDERS) - 1:
            for step in range(1, FLOOR_SEPARATION + 1):
                for width in (0, 1):
                    dx, dy = rotate(x + width, y + step + 1, turn)
                    cell = (ox + dx, oy + dy, z - step)
                    walking.add(cell)
                    stairs.add(cell)
            for step in range(2, 8):
                for width in (0, 1):
                    dx, dy = rotate(x + width, y + FLOOR_SEPARATION + step, turn)
                    cell = (ox + dx, oy + dy, z - FLOOR_SEPARATION)
                    walking.add(cell)
                    stairs.add(cell)
            dx, dy = rotate(x, y + FLOOR_SEPARATION + 7, turn)
            start = ox + dx, oy + dy, z - FLOOR_SEPARATION

    solid: set[tuple[int, int, int]] = set()
    for x, y, z in walking:
        clearance = headroom + 1 if (x, y, z) in stairs else headroom
        solid.add((x, y, z - 1))
        solid.add((x, y, z + clearance))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if not any((x + dx, y + dy, z + dz) in walking for dz in (-1, 0, 1)):
                solid.update((x + dx, y + dy, z + dz) for dz in range(clearance))
    for x, y, z in walking:
        if any((x, y, z + dz) in solid for dz in (0, 1)):
            raise ValueError("Generated walking route intersects solid headroom")
    return {
        "schema": SCHEMA, "variant": variant, "headroom": headroom, "wings": wings,
        "application_distance_limit": sum(w["reference_distance"] for w in wings[1:])
        + APPLICATION_ALLOWANCE,
        "walking": walking, "solid": solid,
    }


def cuboids(cells: set[tuple[int, int, int]]) -> list[dict]:
    """Coalesce exact voxel runs without filling unsupported intervening cells."""
    rows = {}
    for x, y, z in cells:
        rows.setdefault((y, z), []).append(x)
    result = []
    for (y, z), xs in sorted(rows.items()):
        xs.sort()
        start = previous = xs[0]
        for x in xs[1:]:
            if x != previous + 1:
                result.append({"origin": [start, y, z], "size": [previous - start + 1, 1, 1]})
                start = x
            previous = x
        result.append({"origin": [start, y, z], "size": [previous - start + 1, 1, 1]})
    for axis in (1, 2):
        groups = {}
        others = [i for i in range(3) if i != axis]
        for box in result:
            key = tuple(box["origin"][i] for i in others) + tuple(box["size"][i] for i in others)
            groups.setdefault(key, []).append(box)
        merged = []
        for boxes in groups.values():
            boxes.sort(key=lambda box: box["origin"][axis])
            run = None
            for box in boxes:
                if run is not None and run["origin"][axis] + run["size"][axis] == box["origin"][axis]:
                    run["size"][axis] += box["size"][axis]
                else:
                    run = {"origin": box["origin"][:], "size": box["size"][:]}
                    merged.append(run)
        result = merged
    return result


def validate_samples(samples: list[dict]) -> None:
    if not isinstance(samples, list):
        raise ValueError("Native route history must be a list")
    previous = -1
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != {"sequence", "position"}:
            raise ValueError("Unexpected native route sample fields")
        sequence, pos = sample["sequence"], sample["position"]
        if (type(sequence) is not int or sequence <= previous
                or not isinstance(pos, list) or len(pos) != 3
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pos)):
            raise ValueError("Invalid native route sequence or position")
        previous = sequence


def route_checks(
    samples: list[dict], wings: list[dict], distance_limit: float, *, deaths: int = 0,
) -> dict:
    """Score sampled native movement; never infer learning from completion alone."""
    validate_samples(samples)
    if type(deaths) is not int or deaths < 0:
        raise ValueError("Native deaths must be a nonnegative integer")
    if len(wings) != 3 or distance_limit <= 0 or not math.isfinite(distance_limit):
        raise ValueError("Require one practice and two application wings with a finite budget")
    if any(w["phase"] != ("practice" if i == 0 else "application")
           for i, w in enumerate(wings)):
        raise ValueError("Invalid phase order")
    previous = None
    total = 0.0
    wing = 0
    entered = None
    distances = []
    milestones = []
    for sample in samples:
        sequence, pos = sample["sequence"], sample["position"]
        if previous is not None:
            distance = math.dist(previous, pos)
            if distance > 4:
                if not deaths:
                    raise ValueError("Route sample gap or relocation exceeds the measurement bound")
            else:
                total += distance
        previous = pos
        if wing == len(wings):
            continue
        row = wings[wing]

        def inside(cell):
            return (cell[0] <= pos[0] < cell[0] + 2
                    and cell[1] <= pos[1] < cell[1] + 2
                    and abs(pos[2] - cell[2]) <= 0.5)

        if entered is None and inside(row["entry"]):
            entered = total
            milestones.append({"wing": wing, "event": "entry", "sequence": sequence})
        if entered is not None and inside(row["exit"]):
            distances.append(total - entered)
            milestones.append({"wing": wing, "event": "exit", "sequence": sequence})
            entered = None
            wing += 1
    complete = wing == len(wings)
    application_distance = sum(distances[1:]) if len(distances) > 1 else 0
    return {
        "success": complete and application_distance <= distance_limit and deaths == 0,
        "native_deaths": deaths,
        "completed_wings": wing,
        "wing_distances": distances,
        "application_distance": application_distance,
        "application_distance_limit": distance_limit,
        "milestones": milestones,
        "learning_benefit": {
            "status": "not_estimated",
            "reason": "Experience-dependent transfer requires matched instance/history comparisons.",
        },
        "semantics": (
            "Ordered practice/application traversal without death and sampled native travel. "
            "Distance is a sampled polyline, not a server-atomic odometer. "
            "Success is transfer proficiency, not proof of an internal learning mechanism."
        ),
    }
