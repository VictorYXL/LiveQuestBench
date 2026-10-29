import pytest

from game.minecraft.fixtures.camel_response import application_charge, commands, in_pad


def test_public_response_not_private_instance_selects_application_charge():
    assert application_charge(7) > application_charge(28)
    for invalid in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            application_charge(invalid)


def test_same_public_course_has_only_native_attribute_variation():
    first, second = commands(0), commands(1)
    changed = [(a, b) for a, b in zip(first, second) if a != b]
    assert len(changed) == 1
    assert changed[0][0].startswith("summon camel ")
    assert "minecraft:generic.movement_speed" in changed[0][0]
    assert all(not c.startswith(("attribute ", "tp ", "teleport ")) for c in first)


def test_application_geometry_keeps_two_distinct_four_by_four_pads():
    assert in_pad({"x": 5, "z": 20}, 0)
    assert not in_pad({"x": 9, "z": 20}, 0)
    assert in_pad({"x": 16.9, "z": 23.9}, 1)
    assert not in_pad({"x": 16.9, "z": 24}, 1)


def test_initial_authoring_never_removes_support_below_the_live_player():
    for command in commands(0):
        words = command.split()
        if words[0] == "fill" and words[-1] == "air":
            x1, y1, z1, x2, y2, z2 = map(int, words[1:7])
            assert not (x1 <= -43 <= x2 and y1 <= 71 <= y2 and z1 <= 1 <= z2)
