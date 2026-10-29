import asyncio
import copy
import sys
from types import SimpleNamespace

import pytest

from game.veloren import settlement


class QuoteSequence:
    """Replay the completed provisioning sale followed by a declined empty trade."""

    def __init__(self, *, decline_once=True, decline_again=False, replace_identity=False):
        self.target = {"uid": 147, "lifecycle": "original-merchant"}
        self.admin = SimpleNamespace(request=self.observe)
        self.actor = object()
        self.pending = None
        self.last_result = None
        self.invites = 0
        self.relocations = []
        self.distance = 2.6328537464141846
        self.position = [18505.0, 10224.6552734375, 319.0]
        self.decline_once = decline_once
        self.decline_again = decline_again
        self.replace_identity = replace_identity

    def trade(self):
        def item(name, amount, slot, value):
            return {"id": {"Simple": name}, "amount": amount,
                    "slot": slot, "unit_site_value": value}

        return {
            "trade_id": self.invites - 1, "phase": "Mutate", "self_party_index": 0,
            "parties": [1, 147],
            "inventories": [
                [item("chest", 1, 2, 4.3144879341), item("potion", 1, 0, 5.7525019646)],
                [item("common.items.utility.coins", 962, 589825, .10000000149)]
                + ([item("chest", 1, 3, 4.3144879341)] if self.invites >= 3 else []),
            ],
        }

    async def observe(self, method):
        assert method == "observe"
        target = dict(self.target)
        if self.replace_identity and self.invites >= 2 and self.pending is None:
            target["lifecycle"] = "replacement-merchant"
        return copy.deepcopy({
            "control_actor": {"uid": 1, "lifecycle": "administrator"},
            "current_site": {"loaded_chunk": True},
            "nearby_entities": [{
                "uid": 147, "name_text": "Resident (Merchant)", "control_target": target,
                "position": self.position,
                "distance": self.distance, "health": {"current": 100, "dead": False},
            }],
            "social_and_trade": {"pending_trade": self.pending, "outgoing_invitee_uids": []},
            "last_trade_result": self.last_result,
            "inventory": {"items": [{"item": {"id": {"Simple": "potion"}}}]},
        })

    async def command(self, admin, commands, name, *args):
        if name == "sudo":
            assert args[:2] == ("uid@147", "goto")
            self.position = list(args[2:])
        return "Merchant (1712)" if name == "rtsim_npc" else ""

    async def action(self, admin, kind, **args):
        operation = args["operation"]
        if operation == "invite_trade":
            assert args["target"] == self.target
            self.invites += 1
            if self.invites == 3 and self.decline_once or self.invites > 3 and self.decline_again:
                # The actual trace closes an accepted empty trade between observations.
                self.pending = None
                self.last_result = {
                    "committed": False, "result": "Declined",
                    "parties": [{"uid": 1, "lifecycle": "administrator"}, self.target],
                    "trade": {"parties": [1, 147], "phase": "Mutate", "offers": [[], []]},
                }
            else:
                self.pending = self.trade()
        elif operation == "decline":
            self.pending = None
            self.distance = 4.761466979980469
        elif operation == "accept":
            if self.pending["phase"] == "Mutate":
                self.pending["phase"] = "Review"
            else:
                self.pending = None
                self.last_result = {"committed": True, "result": "Completed"}
        else:
            assert operation == "add_item"
        return {"submitted_to_server": True}

    async def wait(self, actor, predicate, description, **kwargs):
        for _ in range(3):
            row = await self.observe("observe")
            if predicate(row):
                return row
        raise RuntimeError(f"native setup did not establish {description}")

    async def goto(self, admin, actor, point, **kwargs):
        self.relocations.append((actor is self.admin, list(point)))
        self.distance = 0
        return await self.observe("observe")

    async def gift(self, *args):
        pass

    def run(self, monkeypatch):
        monkeypatch.setattr(settlement, "native_command_text", self.command)
        monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(
            setup=SimpleNamespace(action=self.action, wait_observation=self.wait,
                                  goto=self.goto, gift=self.gift)))
        fixture = {
            "merchant": {"stock_item": "chest", "stock_amount": 1, "payment_item": "potion",
                         "payment_reserve": 1, "coin_reserve": 5, "position": [1, 2, 3]},
            "player_state": {"inventory": {"potion": 2, "common.items.utility.coins": 5},
                             "position": [1, 2, 3]},
        }
        return asyncio.run(settlement.initialize_merchant(self.admin, self.actor, fixture))


@pytest.mark.parametrize("decline_once", [False, True])
def test_final_quote_recovers_same_merchant_after_closed_trade(monkeypatch, decline_once):
    sequence = QuoteSequence(decline_once=decline_once)
    prepared = sequence.run(monkeypatch)
    assert sequence.invites == (4 if decline_once else 3)
    assert any(administrator for administrator, _ in sequence.relocations)
    assert prepared["uid"] == 147
    assert prepared["qualified_stock"]["parties"] == [1, 147]


def test_final_quote_does_not_repeat_unbounded_native_refusals(monkeypatch):
    sequence = QuoteSequence(decline_again=True)
    with pytest.raises(RuntimeError, match="native merchant trade"):
        sequence.run(monkeypatch)
    assert sequence.invites <= 4


def test_final_quote_rejects_replaced_merchant_lifecycle(monkeypatch):
    sequence = QuoteSequence(replace_identity=True)
    with pytest.raises(RuntimeError, match="lifecycle"):
        sequence.run(monkeypatch)
    assert sequence.invites == 2


@pytest.mark.parametrize("unrelated", [False, True])
def test_final_quote_does_not_retry_stale_or_other_party_declines(monkeypatch, unrelated):
    sequence = QuoteSequence()
    sequence.invites = 2
    asyncio.run(sequence.action(sequence.admin, "social_action",
                                operation="invite_trade", target=sequence.target))
    sequence.invites = 2
    original = sequence.action

    async def action(*args, **kwargs):
        result = await original(*args, **kwargs)
        if unrelated:
            sequence.last_result["parties"][1] = {"uid": 999, "lifecycle": "other-merchant"}
        return result

    if unrelated:
        sequence.last_result = {"committed": True, "result": "Completed"}
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(
        setup=SimpleNamespace(action=action, wait_observation=sequence.wait, goto=sequence.goto)))
    with pytest.raises(RuntimeError, match="native merchant trade"):
        asyncio.run(settlement.final_quote_trade(sequence.admin, sequence.target, []))
    assert sequence.invites == 3
