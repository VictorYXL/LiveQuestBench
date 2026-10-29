from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import irrigation


@pytest.mark.parametrize("settled,expected", [(False, False), (True, True)])
def test_hydration_does_not_replace_the_settled_return(monkeypatch, settled, expected):
    monkeypatch.setattr(irrigation, "stable_ticks", lambda p: 0 if p == Path("before") else 120)
    monkeypatch.setattr(irrigation.nbtlib, "load",
                        lambda p: {"Data": {"Time": 0 if p.parts[0] == "before" else 200}})
    monkeypatch.setattr(irrigation, "evaluate_state", lambda *_a, **_kw: {
        "success": settled, "checks": [{"kind": "position", "passed": settled}], "semantics": "",
    })
    assert irrigation.evaluate_irrigation(Path("before"), Path("after"), UUID(int=1), position={})["success"] is expected


def test_frozen_observer_calls_cannot_claim_unelapsed_native_stability(monkeypatch):
    monkeypatch.setattr(irrigation, "stable_ticks", lambda p: 0 if p == Path("before") else 120)
    monkeypatch.setattr(irrigation.nbtlib, "load",
                        lambda p: {"Data": {"Time": 100 if p.parts[0] == "before" else 120}})
    with pytest.raises(ValueError, match="elapsed native world ticks"):
        irrigation.evaluate_irrigation(Path("before"), Path("after"), UUID(int=1), position={})
