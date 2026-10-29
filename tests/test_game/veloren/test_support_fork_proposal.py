from collections import deque
from pathlib import Path

from game.veloren.fixture import solid_voxels
from game.veloren.prototypes.covered_support_forks import build_candidate
from game.veloren.prototypes.rest_support_audit import sweep_clear
from game.veloren.prototypes.support_fork_proposal import build_proposal_geometry, stage_plan


WORLD = Path("config/veloren/fixtures/veloren_0_18_0_0.bin")


def test_camera_bound_candidate_preserves_all_geometry_resources_and_legal_routes():
    tasks = []
    for seed in (0, 1):
        fixture, proposal = build_proposal_geometry(WORLD, seed)
        task, private = build_candidate(WORLD, seed)
        assert {k: v for k, v in task["fixture"].items() if k != "camera_observation"} == fixture
        assert solid_voxels(task["fixture"]) == solid_voxels(fixture)
        assert task["evaluator"]["name"] == "state"
        assert set(task["evaluator"]["parameters"]) == {"min_health", "position"}
        assert task["evaluator"]["parameters"]["position"]["target"] == proposal["proposed_endpoint"]
        assert "route_observation" not in task["fixture"]
        assert "route_evidence" not in task["fixture"]
        assert not private["qualification"]
        tasks.append(task)
    assert tasks[0]["task"] == tasks[1]["task"]
    assert tasks[0]["evaluator"] == tasks[1]["evaluator"]


def reachable(voxels, start, z):
    reached, pending = {start}, deque([start])
    while pending:
        x, y = pending.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_cell = (x + dx, y + dy)
            if next_cell in reached:
                continue
            if sweep_clear(voxels, [x + .5, y + .5, z],
                           [x + dx + .5, y + dy + .5, z],
                           radius=.45, height=2.3333332538604736, supported=True):
                reached.add(next_cell)
                pending.append(next_cell)
    return reached


def test_both_maps_have_native_size_body_clear_supported_routes():
    for seed in (0, 1):
        fixture, private = build_proposal_geometry(WORLD, seed)
        voxels = solid_voxels(fixture)
        start = tuple(int(v) for v in fixture["player_state"]["position"][:2])
        target = tuple(int(v) for v in private["proposed_endpoint"][:2])
        reached = reachable(voxels, start, 501)
        assert target in reached
        assert private["authored_voxels"] <= 8192
        assert not private["approved"]


def test_private_assignment_moves_real_support_and_second_application_rotates():
    left = stage_plan("left", 8)
    right = stage_plan("right", 8)
    assert left["clear"] == right["clear"]
    assert left["floor"] - right["floor"] == left["bridge"]
    assert right["floor"] - left["floor"] == right["bridge"]
    for seed in (0, 1):
        fixture, private = build_proposal_geometry(WORLD, seed)
        assert [s["heading_y"] for s in private["stages"]] == [1, -1]
        assert [s["gap_span"] for s in private["stages"]] == [8, 10]
        assert fixture["public_energy"] is True
        assert not fixture.get("route_evidence", False)
        ox, oy = private["origin"]
        voxels = solid_voxels(fixture)
        for stage in private["stages"]:
            for x, y in stage["bridge"]:
                assert (ox + x, oy + y, 500) in voxels


def test_remembered_relative_side_transfers_but_fixed_world_side_does_not():
    for seed in (0, 1):
        fixture, private = build_proposal_geometry(WORLD, seed)
        voxels = solid_voxels(fixture)
        ox, oy = private["origin"]
        world_west_supported = []
        for stage in private["stages"]:
            centre_x = stage["entry"][0]
            local_left_is_west = stage["heading_y"] == 1
            expected_west = (private["side"] == "left") == local_left_is_west
            bridge_centre = (
                sum(x + .5 for x, _ in stage["bridge"]) / len(stage["bridge"]),
                sum(y + .5 for _, y in stage["bridge"]) / len(stage["bridge"]),
            )
            assert (bridge_centre[0] < centre_x) == expected_west
            assert (ox + int(bridge_centre[0]), oy + int(bridge_centre[1]), 500) in voxels
            world_west_supported.append(expected_west)
        assert sum(world_west_supported) == 1


def test_recovery_pits_do_not_connect_to_each_other_or_final_room():
    for seed in (0, 1):
        fixture, private = build_proposal_geometry(WORLD, seed)
        voxels = solid_voxels(fixture)
        lower = reachable(voxels, (18710, 10832), 496)
        assert (18738, 10826) not in lower
        assert tuple(int(v) for v in private["proposed_endpoint"][:2]) not in lower
        assert all(10828 <= y < 10836 for _, y in lower)


def test_local_pits_have_unobstructed_five_metre_recovery_to_normal_deck():
    for seed in (0, 1):
        fixture, private = build_proposal_geometry(WORLD, seed)
        voxels = solid_voxels(fixture)
        # Check both physical orientations, not a mirrored geometric assumption.
        # This is static access evidence, not a native climb/grounding receipt.
        for stage in private["stages"]:
            def point(local_x, local_y, z):
                sign = stage["heading_y"]
                return [
                    private["origin"][0] + stage["entry"][0] + sign * (local_x - .5),
                    private["origin"][1] + stage["entry"][1] + sign * (local_y + 3.5),
                    z,
                ]

            x = 4.5 if private["side"] == "left" else -3.5
            edge = 12 + stage["gap_span"]
            bottom, lip, deck = point(x, edge - .5, 496), point(x, edge - .5, 501), point(x, edge + .5, 501)
            assert sweep_clear(voxels, bottom, lip, radius=.45, height=2.3333332538604736,
                               supported=False)
            assert sweep_clear(voxels, lip, deck, radius=.45, height=2.3333332538604736,
                               supported=False)
            assert sweep_clear(voxels, deck, deck, radius=.45, height=2.3333332538604736,
                               supported=True)


def test_pinned_overhead_minimap_does_not_encode_bridge_height():
    # Native composite_layer_overhead returns the first Rock color after air,
    # not a height shade. Its MODE_OVERHEAD is constant true. These are source
    # algorithm checks, not rendered screenshots or a modified observation.
    def pixel(voxels, x, y, ceiling):
        solids = air = 0
        for z in range(ceiling, 494, -1):
            if (x, y, z) in voxels:
                if air:
                    return (160, 160, 160, 255)
                solids += 1
            else:
                air += 1
            if solids > 12:
                break
        return (0, 0, 0, 255)

    variants = [solid_voxels(build_proposal_geometry(WORLD, seed)[0]) for seed in (0, 1)]
    changed_columns = {(x, y) for x, y, _ in variants[0] ^ variants[1]}
    assert changed_columns
    for x, y in changed_columns:
        for ceiling in range(495, 506):
            assert pixel(variants[0], x, y, ceiling) == pixel(variants[1], x, y, ceiling)


def test_double_turn_blocks_sampled_collision_visible_fork_cameras():
    plan = stage_plan("left", 8)
    free = plan["clear"]
    walls = {
        (x + dx, y + dy) for x, y in free
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    } - free

    def clear_line(a, b):
        for x, y in walls:
            low, high = 0.0, 1.0
            for start, finish, minimum in zip(a, b, (x, y)):
                delta = finish - start
                if delta == 0:
                    if not minimum < start < minimum + 1:
                        high = -1
                        break
                else:
                    t1, t2 = (minimum - start) / delta, (minimum + 1 - start) / delta
                    low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
            if low < high:
                return False
        return True

    cameras = [
        (x + dx, y + dy) for x, y in free
        for dx, dy in ((.1, .1), (.1, .9), (.9, .1), (.9, .9), (.5, .5))
        if clear_line((.5, .5), (x + dx, y + dy))
    ]
    assert cameras
    for target in ((-4.5, 12.5), (-2.5, 12.5), (-3.5, 16.5)):
        assert not any(clear_line(camera, target) for camera in cameras)
