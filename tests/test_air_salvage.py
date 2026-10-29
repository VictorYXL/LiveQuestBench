from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators import air_salvage


@pytest.fixture
def scoring_case(tmp_path, monkeypatch):
    before, after = tmp_path / "before", tmp_path / "after"
    for path, tick in ((before, 100), (after, 160)):
        path.mkdir()
        (path / "livequest-air.json").write_text("{}")
        nbtlib.File({"Data": nbtlib.Compound({"Time": nbtlib.Long(tick)})}).save(path / "level.dat")
    trace = [{
        "player": [0, 0, 0, 3], "tick": 120, "position": [10., 72., 0.],
        "health": 20., "air_ticks": 0, "effects": [],
    }]
    monkeypatch.setattr(air_salvage, "verify_initial_cargo", lambda *a, **k: None)
    monkeypatch.setattr(air_salvage, "samples", lambda path: [] if path == before else trace)
    monkeypatch.setattr(air_salvage, "evaluate_cargo", lambda *a, **k: {
        "success": True, "checks": [{"kind": "original_cargo", "passed": True}],
    })
    return before, after, trace


@pytest.mark.parametrize("deaths,success", [(0, True), (1, False)])
def test_native_death_overrides_recovered_cargo_but_air_is_diagnostic(scoring_case, monkeypatch, deaths, success):
    before, after, _ = scoring_case
    monkeypatch.setattr(air_salvage, "evaluate_deaths", lambda *a: {"deaths": {"count": deaths}})
    result = air_salvage.evaluate_air_salvage(before, after, UUID(int=3), cargo=[], position={})
    assert result["success"] is success
    assert result["air_timeline"][0]["air_ticks"] == 0


@pytest.mark.parametrize("field,value", [("player", [0, 0, 0, 4]), ("tick", 170)])
def test_rejects_foreign_or_out_of_episode_native_air_samples(scoring_case, monkeypatch, field, value):
    before, after, trace = scoring_case
    trace[0][field] = value
    monkeypatch.setattr(air_salvage, "evaluate_deaths", lambda *a: {"deaths": {"count": 0}})
    with pytest.raises(ValueError, match="Invalid native air sample"):
        air_salvage.evaluate_air_salvage(before, after, UUID(int=3), cargo=[], position={})
