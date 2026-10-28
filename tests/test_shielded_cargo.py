from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from game.minecraft.evaluators.shielded_cargo import evaluate_shielded_cargo


PLAYER = UUID("12345678-1234-5678-1234-567812345678")
IDENTITY = [int.from_bytes(PLAYER.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]


def score(events):
    with (
        patch("game.minecraft.evaluators.shielded_cargo.verify_initial_shielded_cargo"),
        patch.object(Path, "read_bytes", return_value=b"same manifest"),
        patch("game.minecraft.evaluators.shielded_cargo.evaluate_cargo",
              return_value={"checks": [{"kind": "original_cargo", "passed": True}]}),
        patch("game.minecraft.evaluators.shielded_cargo.nbtlib.load",
              side_effect=[{"Data": {"Time": 100}}, {"Data": {"Time": 200}}]),
        patch("game.minecraft.evaluators.shielded_cargo.projectile_events", return_value=events),
    ):
        return evaluate_shielded_cargo(Path("before"), Path("after"), PLAYER, cargo=[], position={})


def test_cargo_without_native_block_is_not_success():
    assert score([])["success"] is False


def test_native_attributed_block_completes_cargo():
    result = score([{"kind": "skeleton_arrow_block", "player": IDENTITY, "tick": 150}])
    assert result["success"] is True
    assert result["native_elapsed_ticks"] == 100


@pytest.mark.parametrize("replacement", [
    {"kind": "shield_use"}, {"player": [0, 0, 0, 0]}, {"tick": 99}, {"tick": 201},
])
def test_invalid_or_outside_episode_evidence_is_not_scored(replacement):
    event = {"kind": "skeleton_arrow_block", "player": IDENTITY, "tick": 150}
    with pytest.raises(ValueError, match="Invalid projectile"):
        score([{**event, **replacement}])


def test_native_event_order_must_be_monotone():
    with pytest.raises(ValueError, match="native clock"):
        score([{"kind": "skeleton_arrow_block", "player": IDENTITY, "tick": tick}
               for tick in (160, 150)])
