from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import market


POSITION = {"target": [0, 72, 0], "horizontal_tolerance": 3, "vertical_tolerance": 1, "max_speed": .1}


def test_partial_purchases_do_not_mix_alternative_bundle_goals(monkeypatch):
    monkeypatch.setattr(market, "evaluate_state", lambda *_a, **kw: {"success": False, "checks": []})
    monkeypatch.setattr(market, "custom_statistics", lambda *_a: {})
    bundles = [[{"item": "iron_axe", "min_count": 1}], [{"item": "iron_shovel", "min_count": 1}]]
    result = market.evaluate_market(Path("before"), Path("after"), UUID(int=1), bundles=bundles, position=POSITION)
    assert not result["success"]
    monkeypatch.setattr(market, "evaluate_state",
                        lambda *_a, **kw: {"success": kw["inventory"] == bundles[1], "checks": []})
    assert market.evaluate_market(Path("before"), Path("after"), UUID(int=1),
                                  bundles=bundles, position=POSITION)["success"]


def test_trade_counter_regression_invalidates_measurement(monkeypatch):
    monkeypatch.setattr(market, "evaluate_state", lambda *_a, **kw: {"success": True})
    monkeypatch.setattr(market, "custom_statistics",
                        lambda path, _p: {"minecraft:traded_with_villager": 2 if str(path) == "before" else 1})
    with pytest.raises(ValueError, match="backwards"):
        market.evaluate_market(Path("before"), Path("after"), UUID(int=1),
                               bundles=[[{"item": "bread", "min_count": 8}]], position=POSITION)


def test_empty_procurement_bundle_is_not_automatic_success():
    with pytest.raises(ValueError, match="empty"):
        market.validate_market(bundles=[[]], position=POSITION)
