from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from game.minecraft.evaluators.state import evaluate_state, validate_state


@pytest.mark.parametrize("mode,passed", [(2, True), (0, False)])
def test_adventure_endpoint_is_checked_from_native_player_mode(mode, passed):
    with patch("game.minecraft.evaluators.state.nbtlib.load", return_value={
        "DataVersion": 3700, "Health": 20, "playerGameType": mode,
    }):
        result = evaluate_state(Path("before"), Path("after"), UUID(int=1), gamemode="adventure")
    assert result["success"] is passed


def test_unknown_native_mode_is_rejected():
    with pytest.raises(ValueError, match="native Minecraft mode"):
        validate_state(gamemode="protected")
