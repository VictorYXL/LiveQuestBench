from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import extraction
from game.minecraft.evaluators.extraction import remaining_pickaxe_uses


def test_worn_and_repaired_pickaxes_use_actual_native_damage():
    assert remaining_pickaxe_uses([{"id": "minecraft:iron_pickaxe", "Count": 1,
                                   "tag": {"Damage": 238}}]) == [12]
    assert remaining_pickaxe_uses([{"id": "minecraft:iron_pickaxe", "Count": 1}]) == [250]
    assert remaining_pickaxe_uses([{"id": "minecraft:stone_pickaxe", "Count": 1}]) == []
    assert remaining_pickaxe_uses([{"id": "minecraft:iron_pickaxe", "Count": 1,
                                   "tag": {"Damage": 230}}]) == [20]


@pytest.mark.parametrize("damage,count", [(-1, 1), (250, 1), (0, 2)])
def test_impossible_native_tool_wear_is_invalid_evidence(damage, count):
    with pytest.raises(ValueError, match="wear"):
        remaining_pickaxe_uses([{"id": "minecraft:iron_pickaxe", "Count": count, "tag": {"Damage": damage}}])


@pytest.mark.parametrize("uses,stock_ok,passed", [
    ([12, 12], True, False),
    ([12, 20], True, True),
    ([250], False, False),
])
def test_one_serviceable_pickaxe_and_all_stock_goals_must_coexist(monkeypatch, uses, stock_ok, passed):
    monkeypatch.setattr(extraction, "evaluate_state", lambda *args, **kwargs: {
        "success": stock_ok, "checks": [{"kind": "inventory", "passed": stock_ok}], "semantics": "",
    })
    monkeypatch.setattr(extraction.nbtlib, "load", lambda path: {"Inventory": [
        {"id": "minecraft:iron_pickaxe", "Count": 1, "tag": {"Damage": 250 - n}} for n in uses
    ]})
    result = extraction.evaluate_extraction(
        Path("before"), Path("after"), UUID(int=1),
        inventory=[{"item": "raw_iron", "min_count": 12}],
        position={"target": [0, 72, 0], "horizontal_tolerance": 3,
                  "vertical_tolerance": 1, "max_speed": .1},
        minimum_pickaxe_uses=20,
    )
    assert result["success"] is passed
