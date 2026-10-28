from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators.team_cargo import evaluate_team_cargo


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
