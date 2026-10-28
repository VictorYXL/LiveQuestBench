from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import dispatch


def test_existing_production_is_not_new_dispatch_evidence(monkeypatch):
    monkeypatch.setattr(dispatch, "furnace_evidence",
                        lambda _p: {"events": [{"tick": 10}], "machines": [{"burning_ticks": 1}]})
    with pytest.raises(ValueError, match="previous production"):
        dispatch.evaluate_dispatch(Path("before"), Path("after"), UUID(int=1))


def test_serial_delivery_does_not_require_parallel_furnaces(monkeypatch):
    empty = {"events": [], "machines": [{"burning_ticks": 0, "empty_input_burn_ticks": 0}] * 2}
    complete = {
        "events": [{"kind": "completion", "machine": 0, "tick": 200}],
        "machines": [{"burning_ticks": 200, "empty_input_burn_ticks": 0},
                     {"burning_ticks": 0, "empty_input_burn_ticks": 0}],
    }
    monkeypatch.setattr(dispatch, "furnace_evidence", lambda p: empty if str(p) == "before" else complete)
    monkeypatch.setattr(dispatch.nbtlib, "load",
                        lambda p: {"Data": {"Time": 0 if str(p).startswith("before") else 300}})
    monkeypatch.setattr(dispatch, "evaluate_state", lambda *_a, **_kw: {"success": True, "semantics": ""})
    monkeypatch.setattr(dispatch, "mined_statistics",
                        lambda p, _u: {} if str(p) == "before" else {"minecraft:oak_log": 2})
    result = dispatch.evaluate_dispatch(Path("before"), Path("after"), UUID(int=1))
    assert result["success"]
    assert result["furnace_efficiency"]["machines"][1]["burning_ticks"] == 0
    assert result["furnace_efficiency"]["native_mined_delta"] == {"minecraft:oak_log": 2}
