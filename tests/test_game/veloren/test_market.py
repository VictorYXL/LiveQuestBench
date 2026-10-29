import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.evaluators.market import market_checks
from game.veloren.fixture import validate_fixture
from game.veloren.market import COINS

CHEST = "common.items.armor.hide.rawhide.chest"
BOOTS = "common.items.armor.hide.rawhide.foot"
APPLE = "common.items.food.apple"
MUSHROOM = "common.items.food.mushroom"
BUNDLES = [{CHEST: 1, APPLE: 2}, {BOOTS: 1, MUSHROOM: 3}]
POSITION = {"target": [0, 0, 501], "horizontal_tolerance": 3,
            "vertical_tolerance": 1, "max_speed": .1}


def test_market_reacquires_loaded_identity_without_requiring_public_proximity():
    from types import SimpleNamespace

    from game.veloren.market import _locate_merchant

    commands = []

    async def command(*arguments):
        commands.append(arguments)

    reader = SimpleNamespace(poll=lambda: [{"rtsim_uid": 1798, "uid": 171, "alive": True}])
    assert asyncio.run(_locate_merchant(command, reader, "1798")) == 171
    assert commands == [("rtsim_tp", "1798")]


@pytest.mark.parametrize("clock_fails", [False, True])
def test_market_applies_declared_time_before_same_eligibility_query(monkeypatch, tmp_path, clock_fails):
    import sys
    from types import SimpleNamespace

    from game.veloren import market

    calls = []
    clock_completed = False

    async def command(admin, receipts, name, *arguments):
        nonlocal clock_completed
        calls.append((name, *arguments))
        if name == "time":
            await asyncio.sleep(0)
            if clock_fails:
                raise RuntimeError("native time command failed")
            clock_completed = True
            return "Time changed"
        assert clock_completed
        assert (name, *arguments) == ("rtsim_npc", "merchant,sell wares", 3)
        return "Showing 3/0 matching NPCs."

    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(setup=object()))
    monkeypatch.setattr(market, "native_command_text", command)
    fixture = {"time_of_day": "12:00", "market": {"merchants": []}}
    message = "native time command failed" if clock_fails else "merchants are unavailable"
    with pytest.raises(RuntimeError, match=message):
        asyncio.run(market.initialize_market(SimpleNamespace(out=tmp_path), object(), fixture))
    expected = [("time", "12:00")]
    if not clock_fails:
        expected.append(("rtsim_npc", "merchant,sell wares", 3))
    assert calls == expected


def snapshots(bundle, *, traded=True):
    def inventory(items):
        return {"items": [{"slot": i, "item": {"id": {"Simple": item}, "amount": amount}}
                          for i, (item, amount) in enumerate(items.items())]}

    actor = {"uid": 7, "lifecycle": "player-generation"}
    merchants = [{"uid": i, "lifecycle": f"merchant-{i}"} for i in (10, 11, 12)]
    initial = {
        "survival": {"health": {"current": 100}},
        "position": [0, 0, 501], "velocity": [0, 0, 0], "on_ground": True,
        "control_actor": actor, "inventory": inventory({COINS: 99}),
        "last_trade_result": None,
        "private_market_evidence": {"schema": "livequest-native-market/1",
                                    "merchants": merchants, "offers": {}},
    }
    final = deepcopy(initial)
    final["inventory"] = inventory({COINS: 5, **bundle})
    if traded:
        final["last_trade_result"] = {
            "schema_version": "1.0", "source": "server_finished_trade",
            "committed": True, "result": "Completed", "parties": [actor, merchants[0]],
        }
    return initial, final


@pytest.mark.parametrize("collision_displacement", [0.595703125, 1.5])
def test_market_preparation_approach_allows_bounded_native_collision(
        monkeypatch, tmp_path, collision_displacement):
    import math
    import sys
    from types import SimpleNamespace

    from game.veloren import market

    class InviteReached(Exception):
        pass

    merchant_position = [18727.12890625, 10807.0322265625, 501.0]
    target = {"uid": 173, "lifecycle": "original-merchant"}
    observation = {"nearby_entities": [
        {"uid": 173, "control_target": target, "position": merchant_position, "distance": 4.0}]}

    async def command(admin, receipts, name, *arguments):
        return "(1) (2) (3)" if name == "rtsim_npc" else ""

    async def locate(*arguments):
        return 173

    async def gift(*arguments):
        pass

    async def observe(*arguments):
        return observation

    async def goto(admin, actor, point, *, horizontal_tolerance=.2):
        if point == merchant_position:
            actual = [point[0], point[1] + collision_displacement, point[2]]
            if math.dist(actual[:2], point[:2]) >= horizontal_tolerance:
                raise RuntimeError("native setup did not establish goto")
        return observation

    async def wait_observation(actor, predicate, reason, **kwargs):
        assert predicate(observation)
        return observation

    async def action(actor, kind, **arguments):
        assert kind == "social_action"
        assert arguments == {"operation": "invite_trade", "target": target}
        raise InviteReached

    setup = SimpleNamespace(gift=gift, goto=goto, wait_observation=wait_observation, action=action)
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(setup=setup))
    monkeypatch.setattr(market, "native_command_text", command)
    monkeypatch.setattr(market, "_locate_merchant", locate)
    fixture = {"time_of_day": "12:00", "market": {"merchants": [
        {"position": [18726.5, 10809.5, 501.0], "stock": {MUSHROOM: 3}}]}}
    admin = SimpleNamespace(out=tmp_path, request=observe)
    expected = InviteReached if collision_displacement < 1 else RuntimeError
    with pytest.raises(expected):
        asyncio.run(market.initialize_market(admin, object(), fixture))


@pytest.mark.parametrize(("bundle", "traded", "expected"), [
    (BUNDLES[0], True, True), (BUNDLES[1], True, True),
    (BUNDLES[0], False, False), ({CHEST: 1, MUSHROOM: 3}, True, False),
])
def test_market_requires_one_complete_bundle_and_actual_trade(bundle, traded, expected):
    assert market_checks(*snapshots(bundle, traded=traded), bundles=BUNDLES,
                         coin_reserve=5, position=POSITION)["success"] is expected


def test_market_alive_only_floor_applies_to_the_bundle_checks_too():
    initial, final = snapshots(BUNDLES[0])
    final["survival"]["health"]["current"] = .390625
    parameters = {"bundles": BUNDLES, "coin_reserve": 5, "position": POSITION}
    assert not market_checks(initial, final, **parameters)["success"]
    assert market_checks(initial, final, **parameters, min_health=0)["success"]


def test_market_trade_binds_original_player_and_merchant_lifecycles():
    initial, final = snapshots(BUNDLES[0])
    final["last_trade_result"]["parties"][1] = {"uid": 10, "lifecycle": "replacement"}
    assert not market_checks(initial, final, bundles=BUNDLES, coin_reserve=5, position=POSITION)["success"]
    initial, final = snapshots(BUNDLES[0])
    initial["last_trade_result"] = deepcopy(final["last_trade_result"])
    with pytest.raises(ValueError, match="opening"):
        market_checks(initial, final, bundles=BUNDLES, coin_reserve=5, position=POSITION)


def test_market_rejects_one_stop_bundle_and_initial_goal_stock():
    task = load_task(Path("config/veloren/tasks/structured_tools/market_stock_reconciliation.yaml"))
    fixture = deepcopy(task.fixture)
    fixture["market"]["merchants"][0]["stock"][APPLE] = 2
    del fixture["market"]["merchants"][1]["stock"][APPLE]
    with pytest.raises(ValueError, match="just one"):
        validate_fixture(fixture)
    fixture = deepcopy(task.fixture)
    fixture["player_state"]["inventory"][CHEST] = 1
    with pytest.raises(ValueError, match="initially"):
        validate_fixture(fixture)


def test_market_fixture_exposes_actual_trade_projection(tmp_path):
    from types import SimpleNamespace

    from game.veloren.game import VelorenGame
    from game.veloren.structured_tools.interface import FIELDS

    task = load_task(Path("config/veloren/tasks/structured_tools/market_stock_reconciliation.yaml"))
    game = VelorenGame(output_dir=tmp_path / "game", fixture=task.fixture, track="structured_tool")
    game.phase = "running"
    trade = {
        "trade_id": None, "parties": [7, 10], "self_party_index": 0, "phase": "Mutate",
        "offers": [{}, {}], "accept_flags": [False, False], "offer_site_values": [0, 0],
        "price_scope": "native", "effect_scope": "pending", "inventories": [[], []],
        "private": "excluded",
    }
    row = {field: None for field in FIELDS}
    row.update(dialogue=None, dialogue_markers=[], last_trade_result=None,
               social_and_trade={"pending_trade": trade})

    async def request(operation):
        assert operation == "observe"
        return row

    game._session = SimpleNamespace(check_ready=lambda: None, request=request)
    observed = asyncio.run(game.get_agent_interface().observe())
    assert observed["pending_trade"]["phase"] == "Mutate"
    assert "private" not in observed["pending_trade"]


def market_history_pair():
    from types import SimpleNamespace

    from game.veloren.market_trades import MarketTradeJournal

    initial, final = snapshots(BUNDLES[1])
    sink = []
    journal = MarketTradeJournal(SimpleNamespace(write=lambda **row: sink.append(row), close=lambda: None))
    for state, cursor in ((initial, 10), (final, 30)):
        state.update(session_id="player", event_cursor=cursor,
                     sequence_domain={"kind": "client-update-counter", "session_id": "player"})
        state["private_market_evidence"]["schema"] = "livequest-native-market/2"
    initial["private_market_evidence"]["trade_history"] = journal.snapshot(initial)
    completed = {
        "type": "event", "event": "trade_complete", "protocol_version": "0.2",
        "session_id": "player", "sequence_domain": initial["sequence_domain"],
        "seq": 20, "data": deepcopy(final["last_trade_result"]),
    }
    journal.write(origin="native_event", actor="player", event=completed)
    declined = deepcopy(completed)
    declined.update(seq=25, data={**declined["data"], "result": "Declined", "committed": False})
    journal.write(origin="native_event", actor="player", event=declined)
    final["last_trade_result"] = declined["data"]
    final["private_market_evidence"]["trade_history"] = journal.snapshot(
        final, initial["private_market_evidence"]["trade_history"]["registry"])
    return initial, final, journal, sink


def test_native_trade_survives_later_decline_without_using_inventory_as_a_receipt():
    initial, final, journal, sink = market_history_pair()
    assert len(sink) == 2
    sink[0]["event"]["data"]["committed"] = False
    assert journal.events[0]["event"]["data"]["committed"] is True
    parameters = {"bundles": BUNDLES, "coin_reserve": 5, "position": POSITION}
    assert market_checks(initial, final, **parameters)["success"]
    final["private_market_evidence"]["trade_history"]["events"].pop(0)
    assert not market_checks(initial, final, **parameters)["success"]


@pytest.mark.parametrize("damage", ["session", "sequence", "boundary", "actor"])
def test_market_history_rejects_replaced_identity_and_invalid_event_boundaries(damage):
    initial, final, _, _ = market_history_pair()
    history = final["private_market_evidence"]["trade_history"]
    if damage == "session":
        history["events"][0]["session_id"] = "another-player"
    elif damage == "sequence":
        history["events"][1]["seq"] = 20
    elif damage == "boundary":
        history["through_sequence"] = 19
    else:
        history["registry"]["actor"]["lifecycle"] = "replacement"
    with pytest.raises(ValueError):
        market_checks(initial, final, bundles=BUNDLES, coin_reserve=5, position=POSITION)


def test_market_history_excludes_setup_other_clients_and_future_receipts():
    initial, final, journal, _ = market_history_pair()
    event = deepcopy(journal.events[0]["event"])
    for actor, sequence in (("administrator", 21), ("player", 9), ("player", 31)):
        event["seq"] = sequence
        journal.write(origin="native_event", actor=actor, event=event)
    history = journal.snapshot(final, initial["private_market_evidence"]["trade_history"]["registry"])
    assert [row["seq"] for row in history["events"]] == [20, 25]
