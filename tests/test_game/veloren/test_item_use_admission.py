import asyncio
from copy import deepcopy

import pytest

from game.veloren.runtime.item_use import use_item
from tests.test_game.veloren.test_initialization import load_worker


def observation(state="ComboMelee2", consumable=True):
    return {"character_state": state, "inventory": {"items": [
        {"slot": 0, "item": {"consumable": {"kind": "Drink"} if consumable else None}},
    ]}, "tick": 100}


class Actor:
    def __init__(self, basis):
        self.basis = basis
        self.calls = []

    async def request(self, command, **kwargs):
        self.calls.append((command, kwargs))
        assert command == "observe" and kwargs == {"origin": "agent"}
        return self.basis


@pytest.mark.parametrize("enabled", [False, True])
def test_worker_opt_in_prevents_proven_ignored_input_without_replaying_or_relabelling(monkeypatch, enabled):
    from types import SimpleNamespace

    calls = []
    native_timeout = {"status": "failed", "action_type": "use_item", "detail": {"code": "action_timeout"}}

    async def action(actor, **kwargs):
        calls.append(kwargs)
        return native_timeout

    worker = load_worker(monkeypatch, SimpleNamespace(action=action))
    session = object.__new__(worker.Session)
    session.config = {"experimental_item_use_admission": "combo-consumable-preflight-v1"} if enabled else {}
    session.track = "structured_tool"
    session.running = True
    session.actor = Actor(observation())
    result = asyncio.run(session.dispatch("action", {"action_type": "use_item", "slot": 0}))
    if enabled:
        assert calls == []
        assert result["status"] == "refused"
        assert result["detail"]["sent"] is False
        assert "started_tick" not in result
    else:
        assert result is native_timeout
        assert len(calls) == 1
        assert session.actor.calls == []


@pytest.mark.parametrize("state,consumable,slot", [
    ("Idle", True, 0), ("Wielding", True, 0), ("ComboMelee2", False, 0),
    ("ComboMelee2", True, 1),
])
def test_other_paths_preserve_native_partial_receipt_and_fence_without_shorter_deadline(state, consumable, slot):
    basis = observation(state, consumable)
    original = deepcopy(basis)
    actor = Actor(basis)
    receipt = {"action_type": "use_item", "status": "completed", "started_tick": 100,
               "finished_tick": 480, "detail": {"entered_use": True, "definition_count_delta": 0},
               "survival": {"after": {"health": {"current": 42}}}}
    calls = []

    async def action(target, **kwargs):
        assert target is actor and kwargs["basis"] is basis
        calls.append(kwargs)
        return receipt

    result = asyncio.run(use_item(actor, action, {"action_type": "use_item", "slot": slot}))
    assert result is receipt
    assert calls == [{"origin": "agent", "require_completed": False, "basis": basis,
                      "action_type": "use_item", "slot": slot}]
    assert actor.basis == original
    assert actor.calls == [("observe", {"origin": "agent"})]


def test_dispatched_cancellation_is_propagated_without_retry_or_success_fallback():
    actor = Actor(observation("Wielding"))
    calls = []

    async def action(*args, **kwargs):
        calls.append(kwargs)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(use_item(actor, action, {"action_type": "use_item", "slot": 0}))
    assert len(calls) == 1
