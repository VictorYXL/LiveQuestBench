import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).parents[2] / "fixtures/veloren/guarded_ranged_motor_reference.py"
spec = importlib.util.spec_from_file_location("guarded_ranged_motor_reference", path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def packet(operation, **visible):
    return {"frame": 7, "visible": {"mode": "play", "footing": True,
                                   "edge": "safe", **visible}, "do": operation}


def state():
    return {"frame": 7, "camera": {"yaw": 8, "pitch": 8}}


def test_arrival_stops_and_long_or_edge_forward_segments_are_refused():
    commands, result = reference.plan(state(), packet(
        ["step", "w", 180, True], landmark="platform", path_clear=True))
    assert [row["name"] for row in commands] == ["release_all", "wait"]
    assert result["arrival_frame"] == 7
    for operation, visible in [
        (["step", "w", 850, True], {"landmark": "stairs"}),
        (["reposition", "w", 40, False], {"landmark": "platform", "edge": "near"}),
    ]:
        with pytest.raises(ValueError, match="Unsafe"):
            reference.plan(state(), packet(operation, path_clear=True, **visible))


def test_aim_uses_observed_sign_and_refuses_previous_floor_target():
    view = dict(landmark="platform", bow=True, clear_line=True,
                target_box=[400, 140, 450, 195])
    commands, _ = reference.plan(state(), packet(["aim"], **view))
    assert commands[0]["arguments"] == {"dx": -7, "dy": -13}
    with pytest.raises(ValueError, match="floor-directed"):
        reference.plan(state(), packet(["shot", "north", 1], **view))
    view["target_box"] = [470, 250, 500, 290]
    with pytest.raises(ValueError, match="observed damage"):
        reference.plan(state(), packet(["shot", "north", 2], **view))
    commands, result = reference.plan(state(), packet(["shot", "north", 1], **view))
    assert result["shots"] == {"north": 1}
    assert sum(row["name"] == "mouse_down" for row in commands) == 1
    with pytest.raises(ValueError, match="visible target line"):
        reference.plan(state(), packet(["shot", "north", 1], **{**view, "clear_line": False}))


def test_public_probe_rejects_unresponsive_camera_and_respawn_resets_orientation():
    prior = {"frame": 7, "probe": {"axis": "yaw", "point": [400, 160],
                                  "landmark_id": "arch-corner"}}
    with pytest.raises(reference.UnsupportedControl, match="camera response"):
        reference.plan(prior, packet(["wait"], landmark_id="arch-corner",
                                    landmark_pixel=[400, 160]))
    _, calibrated = reference.plan(prior, packet(["look", 0, 0],
        landmark_id="arch-corner", landmark_pixel=[360, 160]))
    assert calibrated["camera"]["yaw"] == 8
    _, reset = reference.plan(state(), packet(["respawn"], mode="dead"))
    assert reset["camera"] == {} and reset["needs_arch"]
    with pytest.raises(ValueError, match="both camera signs"):
        reference.plan(reset, packet(["step", "w", 100, False], path_clear=True))
    with pytest.raises(ValueError, match="fresh public frame"):
        reference.plan(state(), {**packet(["wait"]), "frame": 6})
    with pytest.raises(ValueError, match="fresh public frame"):
        reference.plan({**state(), "review_consumed": True}, packet(["wait"]))
    with pytest.raises(ValueError, match="visible arch"):
        reference.plan({**reset, "camera": state()["camera"]},
                       packet(["step", "w", 100, False], landmark="stairs", path_clear=True))
