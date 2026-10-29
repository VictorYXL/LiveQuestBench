import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).parents[2] / "fixtures/veloren/ranged_motor_reference.py"
spec = importlib.util.spec_from_file_location("ranged_motor_reference", path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def test_native_shot_is_released_and_each_yard_budget_stays_finite():
    commands, counts = reference.translate([["shot", "north"]], {"north": 44})
    assert counts == {"north": 45}
    assert [row["name"] for row in commands] == ["mouse_down", "wait", "mouse_up", "wait"]
    with pytest.raises(ValueError, match="45 shots"):
        reference.translate([["shot", "north"]], counts)
    with pytest.raises(ValueError, match="existing bound"):
        reference.translate([["shot", "south"]] * 6, {})


def test_missing_operator_finish_cannot_exceed_control_deadline():
    times = iter([0, 0, 539.5, 540])
    with pytest.raises(TimeoutError, match="540s"):
        reference.await_finish(lambda: False, clock=lambda: next(times), sleep=lambda _: None)
