import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).parents[3] / "checks/veloren_s05_aim_geometry.py"
spec = importlib.util.spec_from_file_location("s05_aim_geometry", path)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


@pytest.mark.parametrize("height", [5, 6])
def test_outside_camera_clears_solid_platform_but_inboard_downward_ray_does_not(height):
    box = ((13, 4, 0), (24, 12, height))
    target = (22.5, 3.55, .9)
    _, stance = geometry.face_stance(target[:2], 4, 12, height)
    assert not geometry.intersects_box((*stance[:2], height + 2), target, *box)
    assert geometry.intersects_box((22.5, 4.7, height + 2), target, *box)


def test_face_selection_covers_both_side_corridors_without_assuming_east_target():
    assert geometry.face_stance((30, 8), 4, 12, 5)[0] == "east"
    assert geometry.face_stance((22.5, 3.55), 4, 12, 5)[0] == "north"
    assert geometry.face_stance((22.5, 12.45), 4, 12, 5)[0] == "south"
    with pytest.raises(ValueError):
        geometry.face_stance((22.5, 8), 4, 12, 5)


def test_third_person_near_target_offset_is_not_silently_treated_as_first_person():
    with pytest.raises(ValueError, match="lateral-focus"):
        geometry.third_person_points((22.5, 3.85, 5), (22.5, 3.55, 1.3))
    focus, muzzle = geometry.third_person_points((22.5, 20.85, 6), (34.55, 17.45, 1.3))
    assert focus[1] < 21 and muzzle[1] < 21


@pytest.mark.parametrize("height,inset", [(5, .328125), (6, .31640625)])
def test_original_inside_stance_has_coupled_outboard_camera_and_body_muzzle(height, inset):
    actor = (22.5, 4 + inset, height)
    target = (22.5, 3.55, .9)
    focus, muzzle = geometry.third_person_points(actor, target)
    assert 4 - focus[1] > .1
    assert 4 - muzzle[1] > .1
    assert not geometry.intersects_box(focus, target, (13, 4, 0), (24, 12, height))
    assert not geometry.intersects_box(muzzle, target, (13, 4, 0), (24, 12, height))


@pytest.mark.parametrize("height", [5, 6])
def test_conditional_window_accepts_motion_but_rejects_fast_or_stale_target(height):
    assert geometry.near_wall_envelope(height)["conditional_radius_margin"] > .02
    assert geometry.near_wall_envelope(height, target_speed=10)["conditional_radius_margin"] < 0
    assert geometry.near_wall_envelope(height, information_error=.4)["conditional_radius_margin"] < 0
