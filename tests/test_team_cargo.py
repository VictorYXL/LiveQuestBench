from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators.team_cargo import (
    _inventory_counts, _transport_estimate, evaluate_team_cargo,
)


def evaluate(counts):
    cargo = {"id": "parcel", "item": "minecraft:paper", "chest": [0, 72, 0]}
    stacks = [
        nbtlib.List[nbtlib.Compound]([nbtlib.Compound({
            "id": nbtlib.String("minecraft:paper"), "Count": nbtlib.Byte(count),
            "tag": nbtlib.Compound({"livequest_cargo": nbtlib.String("parcel")}),
        })]) if count else nbtlib.List[nbtlib.Compound]()
        for count in counts
    ]
    with (
        patch("game.minecraft.evaluators.team_cargo.verify_team_cargo"),
        patch("game.minecraft.evaluators.team_cargo.player_inventory", side_effect=stacks),
    ):
        return evaluate_team_cargo(
            Path("before"), Path("after"), {"Alpha": UUID(int=1), "Beta": UUID(int=2)},
            cargo=[cargo], position={},
        )


@pytest.mark.parametrize("counts", [(1, 0), (0, 1)])
def test_either_peer_can_legally_retrieve_cargo(counts):
    assert evaluate(counts)["success"]


def test_missing_cargo_fails():
    assert not evaluate((0, 0))["success"]


def test_duplicated_original_cargo_is_invalid():
    with pytest.raises(ValueError, match="duplicated"):
        evaluate((1, 1))


def test_transport_reports_separate_item_estimates_across_inventory_changes():
    samples = [
        {"tick": 100, "position": [0, 72, 0], "inventory": {"raw_iron": 8, "coal": 1}},
        {"tick": 120, "position": [3, 72, 4], "inventory": {"raw_iron": 4, "coal": 1}},
        {"tick": 140, "position": [3, 72, 5], "inventory": {"coal": 1}},
    ]
    result = _transport_estimate(samples)
    assert result["sampled_path_metres"] == 6
    assert result["carried_item_metres"] == {"coal": 6, "raw_iron": 32}
    assert result["maximum_sample_gap_ticks"] == 20
    assert result["status"] == "approximate_passive_trace"


@pytest.mark.parametrize("tick", [99, 100])
def test_transport_rejects_repeated_or_backwards_sample_clocks(tick):
    with pytest.raises(ValueError, match="strictly increasing"):
        _transport_estimate([
            {"tick": 100, "position": [0, 72, 0], "inventory": {}},
            {"tick": tick, "position": [1, 72, 0], "inventory": {}},
        ])


def test_transport_inventory_aggregates_equipped_and_split_stacks():
    assert _inventory_counts([
        {"id": "minecraft:paper", "Count": 2, "Slot": 0},
        {"id": "minecraft:paper", "Count": 1, "Slot": -106},
    ]) == {"minecraft:paper": 3}
    with pytest.raises(ValueError, match="inventory count"):
        _inventory_counts([{"id": "minecraft:paper", "Count": -1}])
