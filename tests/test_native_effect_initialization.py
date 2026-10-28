from uuid import UUID

from nbtlib import Int
import pytest

from game.minecraft.init_player_state import PlayerState


def test_finite_initial_effect_accepts_native_readiness_countdown_not_replenishment():
    player = UUID(int=1)
    state = PlayerState(position=(0, 72, 0), effects=[
        {"id": "minecraft:water_breathing", "amplifier": 0, "duration": 80},
    ])
    actual = state.nbt(player)
    actual["active_effects"][0]["duration"] = Int(66)
    state.verify(actual, player)
    for duration in (0, -1, 81):
        actual["active_effects"][0]["duration"] = Int(duration)
        with pytest.raises(RuntimeError, match="active_effects"):
            state.verify(actual, player)
    actual["active_effects"].clear()
    with pytest.raises(RuntimeError, match="active_effects"):
        state.verify(actual, player)


def test_infinite_initial_effect_still_requires_exact_native_duration():
    player = UUID(int=1)
    state = PlayerState(position=(0, 72, 0), effects=[
        {"id": "minecraft:night_vision", "amplifier": 0, "duration": -1},
    ])
    actual = state.nbt(player)
    state.verify(actual, player)
    actual["active_effects"][0]["duration"] = Int(20)
    with pytest.raises(RuntimeError, match="active_effects"):
        state.verify(actual, player)
