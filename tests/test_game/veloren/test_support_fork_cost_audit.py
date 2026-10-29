import math
from pathlib import Path

from game.veloren.prototypes.support_fork_cost_audit import audit, distances, segment_hit


def test_diagonal_route_cannot_cut_a_solid_or_unsupported_corner():
    assert (1, 1) not in distances({(0, 0), (1, 1)}, (0, 0))[0]
    open_square = {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert distances(open_square, (0, 0))[0][(1, 1)] == math.sqrt(2)


def test_visibility_stops_at_the_first_intervening_solid():
    target, wall = (5, 0, 0), (2, 0, 0)
    assert segment_hit({target}, (.5, .5, .5), (5.5, .5, .5)) == target
    assert segment_hit({target, wall}, (.5, .5, .5), (5.5, .5, .5)) == wall


def test_cold_inspection_and_normal_recovery_remain_available_in_both_orientations():
    result = audit(Path("config/veloren/fixtures/veloren_0_18_0_0.bin"))
    assert {row["side"] for row in result["rows"]} == {"left", "right"}
    for row in result["rows"]:
        cold = row["memoryless_world_west_inspection_and_ground_retreat"]
        assert cold["unsupported_initial_choices"] == 1
        assert cold["extra_vs_known_whole_grid_walk_m"] > 0
        assert row["continuation_from_native_endpoint_cell_centre"]["remaining_supported_grid_walk_m"] > 0
        opposite = "right" if row["side"] == "left" else "left"
        assert [s["heading_y"] for s in row["stages"]] == [1, -1]
        for stage in row["stages"]:
            assert stage["whole_supported_route_crosses_this_bridge"]
            assert stage["lower_recovery"]["full_body_sweeps_clear"]
            known = stage["inspection"][row["side"]]
            cold = stage["inspection"][opposite]
            assert math.isclose(known["extra_vs_known_supported_grid_walk_m"], 0, abs_tol=1e-8)
            assert cold["extra_vs_known_supported_grid_walk_m"] > 0
            assert not stage["lower_recovery"]["native_execution_or_time_measured"]
