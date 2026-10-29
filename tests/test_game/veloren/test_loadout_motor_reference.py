import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).parents[2] / "fixtures/veloren/loadout_motor_reference.py"
spec = importlib.util.spec_from_file_location("loadout_motor_reference", path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def test_missing_operator_finish_is_bounded_and_late_marker_cannot_extend_it():
    now = [0]
    checks = []

    def finished():
        checks.append(now[0])
        return now[0] >= 2

    with pytest.raises(TimeoutError, match="finite control deadline"):
        reference.await_finish(finished, seconds=2, clock=lambda: now[0],
                               sleep=lambda step: now.__setitem__(0, now[0] + step))
    assert checks == [0, .5, 1, 1.5]


def test_operator_finish_ends_control_without_claiming_native_success():
    reference.await_finish(lambda: True, sleep=lambda _: pytest.fail("unnecessary wait"))
