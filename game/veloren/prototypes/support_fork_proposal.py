"""Source-only proposal geometry, not an admitted task or native launch command."""

from copy import deepcopy
from pathlib import Path

from game.veloren.fixture import solid_voxels, validate_fixture
from game.veloren.prototypes.rest_support import build_instance


def _rectangle(x, y, width, depth):
    return {(i, j) for i in range(x, x + width) for j in range(y, y + depth)}


def stage_plan(side, span):
    if side not in ("left", "right") or span not in (8, 10):
        raise ValueError("Proposal has two side assignments and fixed 8/10m applications")
    end = 12 + span
    clear = _rectangle(-1, -4, 3, 6) | _rectangle(-9, -1, 19, 3)
    for sign in (-1, 1):
        clear |= _rectangle(-9 if sign == -1 else 7, -1, 3, 11)
        clear |= _rectangle(-9 if sign == -1 else 3, 7, 7, 3)
        clear |= _rectangle(-5 if sign == -1 else 3, 7, 3, end - 3)
    clear |= _rectangle(-5, end + 3, 11, 3)
    clear |= _rectangle(-1, end + 3, 3, 6)
    bay = _rectangle(-11, 12, 23, span)
    clear |= bay
    bridge = _rectangle(-5 if side == "left" else 3, 12, 3, span)
    return {"clear": clear, "floor": (clear - bay) | bridge,
            "bay": bay, "bridge": bridge, "exit_y": end + 7}


def build_proposal_geometry(world_path: Path, seed: int):
    """Reuse the v4 native body/loadout and Rock author; return no task/scorer YAML."""
    old_task, private = build_instance(world_path, seed)
    side = private["shelf_side"]
    first, second = stage_plan(side, 8), stage_plan(side, 10)
    clear, floor, pit_edges = set(), set(), set()

    def transform(cells, offset, sign):
        return {(offset[0] + sign * x, offset[1] + sign * y) for x, y in cells}

    stages = []
    for plan, offset, sign in ((first, (0, 0), 1), (second, (28, 26), -1)):
        clear |= transform(plan["clear"], offset, sign)
        floor |= transform(plan["floor"], offset, sign)
        edge = {
            (x + dx, y + dy) for x, y in plan["bay"]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        } - plan["bay"]
        pit_edges |= transform(edge & plan["floor"], offset, sign)
        stages.append({
            "entry": [offset[0] + .5, offset[1] - sign * 4 + .5, 501],
            "exit": [offset[0] + .5, offset[1] + sign * plan["exit_y"] + .5, 501],
            "heading_y": sign, "gap_span": 8 if sign == 1 else 10,
            "bridge": sorted(transform(plan["bridge"], offset, sign)),
        })
    # Covered connector makes both structures part of one physical journey;
    # no observer, checkpoint or compulsory practice predicate is introduced.
    connector = _rectangle(-1, 24, 3, 9) | _rectangle(-1, 30, 31, 3)
    connector |= _rectangle(27, 29, 3, 4)
    preview = _rectangle(-7, -14, 15, 11) | _rectangle(-1, -5, 3, 2)
    clear |= connector | preview
    floor |= connector | preview
    walls = {
        (x + dx, y + dy) for x, y in clear
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    } - clear

    origin = (18710, 10816)
    blocks = []

    def box(x, y, z, width=1, depth=1, height=1):
        blocks.append({"origin": [origin[0] + x, origin[1] + y, z],
                       "size": [width, depth, height]})

    for x, y in sorted(walls):
        box(x, y, 496, height=9)
    for x, y in sorted(clear):
        box(x, y, 495)
        box(x, y, 505 if (x, y) in preview else 504)
    for x, y in sorted(floor):
        box(x, y, 500)
    for x, y in sorted(pit_edges):
        box(x, y, 496, height=4)
    # A directly inspectable actual raised Rock support, not a textual answer.
    box(-5 if side == "left" else 3, -10, 501, 3, 3)
    for x in (-7, 7):
        box(x, -11, 502)
    fixture = deepcopy(old_task["fixture"])
    fixture.update({
        "platform": {"origin": [18710, 10803, 495], "size": [4, 4], "block": "Rock"},
        "blocks": blocks,
    })
    fixture["player_state"]["position"] = [18710.5, 10803.5, 501]
    validate_fixture(fixture)
    voxels = solid_voxels(fixture)
    return fixture, {
        "schema": "covered-support-forks-source-proposal/1",
        "approved": False,
        "native_execution": False,
        "observation_gate": (
            "Stock far-zoom camera is not proven local. Sampled local-camera occlusion "
            "does not qualify this geometry under the unchanged native observation contract."
        ),
        "side": side,
        "actual_mapping_count": 2,
        "origin": list(origin),
        "stages": stages,
        "authored_voxels": len(voxels),
        "proposed_endpoint": [18738.5, origin[1] + 26 - second["exit_y"] + .5, 501],
        "scope": "Geometry-only candidate. No canonical task, public condition, scorer or runtime is installed.",
    }
