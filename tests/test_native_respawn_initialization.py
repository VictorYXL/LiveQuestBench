from uuid import UUID

from nbtlib import Int
import pytest

from game.minecraft.init_player_state import PlayerState


def test_optional_native_respawn_is_verified_without_changing_default_spawn():
    player = UUID(int=1)
    default = PlayerState(position=(.5, 72, .5))
    assert "SpawnX" not in default.nbt(player)
    state = PlayerState(position=(.5, 72, .5), respawn_position=(0, 72, 0), yaw=-90)
    actual = state.nbt(player)
    assert actual["SpawnForced"] == 1
    state.verify(actual, player)
    actual["SpawnY"] = Int(79)
    with pytest.raises(RuntimeError, match="SpawnY"):
        state.verify(actual, player)


@pytest.mark.parametrize("position", [(0, 72), (0, 72.5, 0), (False, 72, 0)])
def test_respawn_position_rejects_non_block_coordinates(position):
    with pytest.raises(ValueError, match="Respawn position"):
        PlayerState(position=(.5, 72, .5), respawn_position=position)
