"""A trade invitation response is native consent, not an inventory transfer."""

import pytest

from game.veloren.structured_tools.interface import validate_tool


def test_trade_response_is_bound_to_observed_inviter_and_trade_kind():
    assert validate_tool("RespondTradeInviteTool", {"inviter_uid": 3, "accept": True}) == (
        "social_action", {"operation": "respond_accept", "invite_kind": "Trade", "inviter_uid": 3})
    assert validate_tool("RespondTradeInviteTool", {"inviter_uid": 3, "accept": False}) == (
        "social_action", {"operation": "respond_decline", "invite_kind": "Trade", "inviter_uid": 3})
    with pytest.raises(ValueError):
        validate_tool("RespondTradeInviteTool", {"inviter_uid": 3, "accept": True, "invite_kind": "Group"})
