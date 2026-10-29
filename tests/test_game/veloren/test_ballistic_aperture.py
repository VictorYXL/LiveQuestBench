import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from benchmark.config import load_task
from benchmark.factory import make_game
from game.veloren.fixture import solid_voxels
from game.veloren.prototypes.ballistic_aperture import build_instance, write_instance
from game.veloren.prototypes.aperture_counterpolicy import firing_position, settled_navigation


WORLD = Path("config/veloren/fixtures/veloren_0_18_0_0.bin")


def test_all_layouts_have_finite_clearance_and_supported_body_width_routes():
    from game.veloren.prototypes.aperture_geometry_audit import audit

    report = audit(WORLD)
    assert {row["selected"] for row in report["layouts"]} == {0, 1, 2}
    assert all(row["minimum_xy_square_tube_half_width"] > .04 for row in report["layouts"])
    assert all(row["fully_supported_inter_structure_walk"] for row in report["layouts"])


def test_clearance_audit_rejects_an_actually_closed_rear_opening():
    from game.veloren.prototypes.aperture_geometry_audit import support_report

    task, private = build_instance(WORLD, 0)
    task["fixture"]["blocks"].append({"origin": [18705, 10814, 502], "size": [18, 1, 1]})
    with pytest.raises(AssertionError, match="Blocked nominal ray"):
        support_report(task, private["open_slot"])


def test_hidden_choice_changes_native_passage_not_public_goals_or_enemies():
    variants = [build_instance(WORLD, seed) for seed in range(64)]
    assert len({private["open_slot"] for _, private in variants}) == 3
    public = []
    for task, private in variants:
        projected = deepcopy(task)
        projected.pop("fixture")
        public.append(projected)
        voxels = solid_voxels(task["fixture"])
        for front in (10810, 10832):
            for x in (18709, 18712, 18715):
                assert (x, front, 502) not in voxels
            exit_x = ((18710, 18711), (18712,), (18713, 18714))[private["open_slot"]]
            assert tuple(x for x in range(18705, 18723)
                         if (x, front + 4, 502) not in voxels) == exit_x
    assert all(value == public[0] for value in public)
    assert all([(row["role"], row["asset"]) for row in task["fixture"]["encounters"]] ==
               [(row["role"], row["asset"]) for row in variants[0][0]["fixture"]["encounters"]]
               for task, _ in variants)
    assert all(task["fixture"]["encounters"] == variants[0][0]["fixture"]["encounters"]
               for task, _ in variants)
    inner_cells = [
        {voxel for voxel in solid_voxels(task["fixture"])
         if any(front + 7 <= voxel[1] < front + 15 for front in (10810, 10832))}
        for task, _ in variants
    ]
    assert all(cells == inner_cells[0] for cells in inner_cells)


def test_closed_cages_remove_the_old_standing_walkthrough_and_roof_drop():
    task, _ = build_instance(WORLD, 0)
    voxels = solid_voxels(task["fixture"])
    for front in (10810, 10832):
        for x in (18709, 18712, 18715):
            assert (x, front, 501) in voxels
            assert (x, front, 503) in voxels
        assert all((x, y, 506) in voxels for x in range(18704, 18724)
                   for y in range(front, front + 15))
        assert all((x, front + 14, z) in voxels for x in range(18704, 18724)
                   for z in range(501, 506))
        assert all((x, y, z) in voxels for x in (18704, 18723)
                   for y in range(front, front + 15) for z in range(501, 506))


def test_each_exit_has_a_clear_point_projectile_ray_not_a_collision_claim():
    import math

    for seed in range(64):
        task, private = build_instance(WORLD, seed)
        voxels = solid_voxels(task["fixture"])
        entrance_x = (18709, 18712, 18715)[private["open_slot"]] + .5
        for front in (10810, 10832):
            for i in range(101):
                y = front + .5 + i / 10
                x = entrance_x + (18712.5 - entrance_x) * (y - front - .5) / 10
                assert (math.floor(x), math.floor(y), 502) not in voxels
            enemy = next(row for row in task["fixture"]["encounters"]
                         if row["position"][1] == front + 10.5)
            assert enemy["position"][0] == 18712.5
            assert math.dist(task["fixture"]["player_state"]["position"], enemy["position"]) > 32


def test_generated_native_task_constructs_through_existing_binding(tmp_path):
    task_path = write_instance(tmp_path / "instance", WORLD)
    task = load_task(task_path)
    make_game(task, tmp_path / "offline-binding", headless=True,
              recording=False, recording_fps=5)


def test_target_cell_has_real_sides_roof_and_a_wide_low_entrance():
    for seed in range(16):
        task, _ = build_instance(WORLD, seed)
        voxels = solid_voxels(task["fixture"])
        for enemy in task["fixture"]["encounters"]:
            x, y, z = (int(value) for value in enemy["position"])
            assert (x, y, z) not in voxels
            assert (x, y, z + 1) not in voxels
            assert (x, y - 1, z) not in voxels
            assert (x, y - 1, z + 1) in voxels
            assert all((side, yy, zz) in voxels for side in (x - 1, x + 1)
                       for yy in range(y, y + 4) for zz in range(z, z + 3))


def test_cold_controller_skips_unsupported_native_motion_candidates():
    assert firing_position(18708.5, [18718.5, 10815.5, 502], 10810) is None
    assert firing_position(18716.5, [18705.5, 10815.5, 502], 10810) is None
    for seed in range(32):
        task, private = build_instance(WORLD, seed)
        slot = (18709.5, 18712.5, 18715.5)[private["open_slot"]]
        for enemy in task["fixture"]["encounters"]:
            front = enemy["position"][1] - 10.5
            assert firing_position(slot, enemy["position"], front) is not None


def test_navigation_rechecks_coasted_pose_instead_of_accepting_pre_stop_arrival():
    row = {"position": [.1, 0, 501], "velocity": [-3.36, 0, 0],
           "on_ground": True,
           "survival": {"health": {"dead": False}}}
    calls = []

    async def observe():
        return deepcopy(row)

    async def action(tool, **arguments):
        calls.append(tool)
        if tool == "StopTool":
            row["position"] = [-.58, 0, 501] if len(calls) == 1 else [.08, 0, 501]
            row["velocity"] = [0, 0, 0]
        elif tool == "MoveTool":
            row["position"] = [.05, 0, 501]
            row["velocity"] = [1, 0, 0]

    async def no_wait(_):
        pass

    settled = asyncio.run(settled_navigation(observe, action, [0, 0], sleep=no_wait))
    assert "MoveTool" in calls
    assert calls.count("StopTool") == 2
    assert settled["position"] == [.08, 0, 501]
    assert settled["velocity"] == [0, 0, 0]


@pytest.mark.parametrize("retain_feedback, second_miss, second_attacks",
                         [(False, False, 5), (True, False, 2), (True, True, 3)])
@pytest.mark.parametrize("successful_offset", [1.4, 1.0, 1.8])
def test_sweep_reuses_only_its_observed_health_feedback(
        monkeypatch, retain_feedback, second_miss, second_attacks, successful_offset):
    from game.veloren.prototypes import aperture_counterpolicy as policy

    position = [18712.5, 10783.5, 501]
    aimed = list(position)
    attacks = {1: 0, 2: 0}
    enemies = [
        {"uid": uid, "name_text": "Green Legoom", "position": [18712.5, y, 502],
         "health": {"current": 10, "dead": False}}
        for uid, y in ((1, 10820.5), (2, 10842.5))
    ]

    async def observe():
        return deepcopy({"position": position, "velocity": [0, 0, 0], "on_ground": True,
                         "survival": {"health": {"dead": False}}, "nearby_entities": enemies})

    async def action(tool, **arguments):
        if tool == "LookTool":
            aimed[:] = [arguments[axis] for axis in ("x", "y", "z")]
        elif tool == "MoveTool":
            position[:2] = aimed[:2]
        elif (tool == "AttackTool" and abs(position[0] - 18712.5) < .15
              and abs(aimed[2] - (502 - successful_offset)) < .001):
            enemy = next(row for row in enemies if row["position"][1] == aimed[1])
            attacks[enemy["uid"]] += 1
            if not (second_miss and enemy["uid"] == 2 and attacks[2] == 2):
                enemy["health"]["current"] = max(0, enemy["health"]["current"] - 5)
                enemy["health"]["dead"] = enemy["health"]["current"] == 0
        return await observe()

    async def no_wait(_):
        pass

    async def navigate(observe, action, destination, **kwargs):
        return await settled_navigation(observe, action, destination, sleep=no_wait, **kwargs)

    monkeypatch.setattr(policy, "settled_navigation", navigate)
    monkeypatch.setattr(policy.asyncio, "sleep", no_wait)
    result = {}
    asyncio.run(policy.cold_sweep(observe, action, result, retain_feedback=retain_feedback))
    first, second = result["structures"]
    assert first["first_feedback_slot"] == 18712.5
    offset_probes = [1.4, 1.0, 1.8].index(successful_offset)
    assert first["shot_requests"] == 5 + offset_probes
    assert second["shot_requests"] == second_attacks + (0 if retain_feedback else offset_probes)
    assert second["slot_order"][0] == (18712.5 if retain_feedback else 18709.5)
    assert second["aim_offset_order_by_slot"]["18712.5"][0] == (
        successful_offset if retain_feedback else 1.4)
    assert second.get("nondamaging_feedback_retries", 0) == int(second_miss)


def test_navigation_rejects_correct_xy_on_lower_native_terrain():
    calls = []

    async def observe():
        return {"position": [18708.15, 10806, 381], "velocity": [0, 0, 0],
                "on_ground": True, "survival": {"health": {"dead": False}}}

    async def action(tool, **arguments):
        calls.append(tool)

    async def no_wait(_):
        pass

    from game.veloren.prototypes.aperture_counterpolicy import PolicyStop
    with pytest.raises(PolicyStop, match="published platform floor"):
        asyncio.run(settled_navigation(observe, action, [18708.15, 10806], sleep=no_wait))
    assert "MoveTool" not in calls


def test_navigation_calibrates_unknown_native_update_displacement_before_long_pulses():
    position = [18712.5, 10806, 501]
    aimed = list(position)
    pulses = []

    async def observe():
        return {"position": list(position), "velocity": [0, 0, 0],
                "on_ground": True, "survival": {"health": {"dead": False}}}

    async def action(tool, **arguments):
        if tool == "LookTool":
            aimed[:] = [arguments[axis] for axis in ("x", "y", "z")]
        elif tool == "MoveTool":
            ticks = arguments["duration_ticks"]
            pulses.append(ticks)
            position[0] += (1 if aimed[0] > position[0] else -1) * 2.2 * ticks

    async def no_wait(_):
        pass

    settled = asyncio.run(settled_navigation(
        observe, action, [18708.15, 10806], sleep=no_wait))
    assert pulses == [1, 1]
    assert abs(settled["position"][0] - 18708.15) <= .15


def test_perimeter_is_real_geometry_without_an_extra_evaluator_obligation():
    task, _ = build_instance(WORLD, 0)
    voxels = solid_voxels(task["fixture"])
    for z in (501, 502):
        assert all((x, y, z) in voxels for x in range(18700, 18728)
                   for y in (10780, 10851))
        assert all((x, y, z) in voxels for x in (18700, 18727)
                   for y in range(10780, 10852))
    assert set(task["evaluator"]["parameters"]) == {"roles", "no_death", "min_health"}
