"""Candidate-layout and transfer-scoring checks, not native feasibility claims."""

from collections import deque
import math

import pytest

from game.route_transfer import STEM_LENGTH, build_layout, cuboids, rotate, route_checks


def connected(cells, start):
    seen = {start}
    todo = deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dz in (-1, 0, 1):
                p = (x + dx, y + dy, z + dz)
                if p in cells and p not in seen:
                    seen.add(p)
                    todo.append(p)
    return seen


@pytest.mark.parametrize("variant", range(8))
@pytest.mark.parametrize("headroom", (2, 3))
def test_layouts_preserve_schema_across_composition_and_orientation(variant, headroom):
    layout = build_layout(variant, (0, 0, 201), headroom=headroom)
    assert len(layout["solid"]) <= (8192 if headroom == 2 else 10240)
    assert all((x, y, z + dz) not in layout["solid"]
               for x, y, z in layout["walking"] for dz in range(headroom))
    reachable = connected(layout["walking"], (0, 0, 201))
    assert reachable == layout["walking"]
    for wing in layout["wings"]:
        assert tuple(wing["exit"]) in reachable
    assert [w["rotation"] for w in layout["wings"]] == [0, 1, 2]
    assert len({tuple(m["cue"] for m in w["modules"]) for w in layout["wings"]}) == 3
    expanded = {
        (row["origin"][0] + dx, row["origin"][1] + dy, row["origin"][2] + dz)
        for row in cuboids(layout["solid"])
        for dx in range(row["size"][0])
        for dy in range(row["size"][1])
        for dz in range(row["size"][2])
    }
    assert expanded == layout["solid"]


def samples(points):
    return [{"sequence": i, "position": list(p)} for i, p in enumerate(points)]


def simple_wings():
    return [
        {"phase": phase, "entry": [0, y, 0], "exit": [4, y, 0]}
        for phase, y in (("practice", 0), ("application", 4), ("application", 8))
    ]


def path():
    return [
        (0, 0, 0), (2, 0, 0), (4, 0, 0),
        (4, 2, 0), (2, 2, 0), (0, 4, 0),
        (2, 4, 0), (4, 4, 0),
        (4, 6, 0), (2, 6, 0), (0, 8, 0),
        (2, 8, 0), (4, 8, 0),
    ]


def test_application_budget_excludes_practice_and_stair_transitions():
    result = route_checks(samples(path()), simple_wings(), 8)
    assert result["success"]
    assert result["wing_distances"] == [4, 4, 4]
    assert result["application_distance"] == 8
    assert not route_checks(samples(path()), simple_wings(), 7)["success"]


def test_application_backtracking_counts_but_unvisited_practice_cannot_be_skipped():
    points = path()
    points[6:6] = [(2, 4, 0), (0, 4, 0)]
    assert not route_checks(samples(points), simple_wings(), 8)["success"]
    assert not route_checks(samples(path()[5:]), simple_wings(), 8)["success"]


def test_invalid_motion_is_not_a_scored_agent_failure():
    with pytest.raises(ValueError, match="gap"):
        route_checks(samples([(0, 0, 0), (20, 0, 0)]), simple_wings(), 8)
    with pytest.raises(ValueError, match="sequence"):
        route_checks([{"sequence": True, "position": [0, 0, 0]}], simple_wings(), 8)
    assert not route_checks(
        samples([(0, 0, 0), (20, 0, 0)]), simple_wings(), 8, deaths=1,
    )["success"]


@pytest.mark.parametrize("variant", range(8))
@pytest.mark.parametrize("cue", range(3))
@pytest.mark.parametrize("wing", range(3))
def test_exit_choice_is_not_revealed_by_adjacent_future_corridors(variant, cue, wing):
    left = build_layout(variant, (0, 0, 201))
    right = build_layout(variant ^ (1 << cue), (0, 0, 201))

    def visible(layout):
        row = layout["wings"][wing]
        entry = next(m["entry"] for m in row["modules"] if m["cue"] == cue + 1)
        dx, dy = rotate(0, STEM_LENGTH, row["rotation"])
        centre = (entry[0] + dx, entry[1] + dy, entry[2])
        return {tuple(p[i] - centre[i] for i in range(3)) for p in layout["solid"]
                if all(abs(p[i] - centre[i]) <= 15 for i in range(3))}

    assert visible(left) == visible(right)


def test_fork_views_are_occluded_from_changed_continuations():
    left = build_layout(0, (0, 0, 201))
    right = build_layout(1, (0, 0, 201))
    common = left["solid"] & right["solid"]
    changed = left["solid"] ^ right["solid"]

    def blocked(eye, target):
        direction = [b - a for a, b in zip(eye, target)]
        cell = [math.floor(v) for v in eye]
        steps = [1 if d > 0 else -1 for d in direction]
        increments = [abs(1 / d) if d else math.inf for d in direction]
        crossings = [((c + (d > 0) - a) / d) if d else math.inf
                     for c, a, d in zip(cell, eye, direction)]
        while True:
            if tuple(cell) in common:
                return True
            nearest = min(crossings)
            if nearest >= 1:
                return False
            for axis in range(3):
                if crossings[axis] == nearest:
                    cell[axis] += steps[axis]
                    crossings[axis] += increments[axis]

    for lateral in (.35, 1, 1.65):
        eye = (lateral, STEM_LENGTH + .5, 202.62)
        for cell in changed:
            target = tuple(v + .5 for v in cell)
            assert blocked(eye, target), (eye, cell)
