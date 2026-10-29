import asyncio
from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from game.veloren.evaluators.message import message_checks
from game.veloren.message_contract import message_registry, prepare_message_offer


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_initial_message_check_uses_serialized_public_controls(tmp_path, status):
    import json
    from game.bindings import bind_controls
    from game.veloren.structured_tools.interface import (
        StructuredInterface, agent_observation, agent_tools,
    )
    from scripts.veloren_initial_message_check import public_check

    calls = []
    opening = {
        "dialogue": {"sender_uid": 27, "dialogue_id": "12533376870734453177",
                     "tag": 1, "text": "Deliver a message to Wiph for531 coins?",
                     "responses": [{"response_id": 0, "text": "Yes"},
                                   {"response_id": 1, "text": "No"}]},
        "inventory": {"items": []},
    }

    async def observe():
        if calls:
            raise RuntimeError("End of recorded opening")
        return opening

    async def execute(name, arguments):
        calls.append((name, arguments))
        return {"status": status}

    controls, _ = bind_controls(
        StructuredInterface(observe, execute), agent_observation, agent_tools(),
        ("DialogueResponseTool",))
    result = {"public_actions": 0}
    expected = "End of recorded opening" if status == "completed" else "did not complete"
    with pytest.raises(RuntimeError, match=expected):
        asyncio.run(public_check(controls, result, tmp_path))
    assert calls == [("DialogueResponseTool", {
        "sender_uid": 27, "dialogue_id": "12533376870734453177", "tag": 1,
        "response_id": 0,
    })]
    assert result["public_actions"] == 1
    assert result.get("ordinary_yes_submitted", False) == (status == "completed")
    trace = [json.loads(line) for line in (tmp_path / "public.jsonl").read_text().splitlines()]
    assert trace[0]["observation"] == opening
    assert trace[1]["response"] == {"status": status}


@pytest.mark.parametrize("case", [
    "success", "walking_giver", "atomic_moving_giver", "atomic_rejected",
    "invalid_giver", "no_candidates", "wrong_offer",
])
def test_initialization_v2_stages_before_native_offer_and_closes_without_accepting(case):
    import json
    from game.veloren.message_contract import prepare_initial_message_offer

    events, prepared = [], {}
    source_distance, acknowledged = 2.0, False
    residents = [{"uid": number} for number in (2, 3, 4)]
    recipient = {"uid": 5, "name_text": "Recipient (Farmer)"}
    fixture = {
        "player_state": {"position": [0, 0, 1]},
        "message_contract": {"giver_position": [2, 0, 1], "recipient_position": [30, 0, 1],
                             "distractor_positions": [[12, 0, 1], [20, 0, 1]]},
    }
    atomic = case.startswith("atomic_")
    protocol = "initial-message-v3" if atomic else "initial-message-v2"
    if atomic:
        fixture["message_contract"]["initialization_protocol"] = protocol

    async def command(name, *arguments):
        nonlocal source_distance
        if name != "rtsim_info":
            events.append(name)
            if arguments[:2] == ("uid@2", "goto"):
                source_distance = 2.0
                events.append("source_staged")
            else:
                source_distance += 1.1
            return ""
        operation = arguments[1]
        events.append(operation)
        if operation == "prepare":
            if case == "invalid_giver":
                return "native_message_invalid_giver"
            if case == "no_candidates":
                return "native_message_unavailable:no_fully_eligible_existing_recipient"
            return json.dumps({"protocol": protocol, "phase": "prepared",
                               "proposal_id": "opaque", "recipient_rtsim_uid": 55,
                               "recipient_name": "Recipient"})
        if atomic and operation == "publish":
            assert arguments[2:] == ("opaque", 2, 0, 1)
            assert source_distance > 5
            assert "source_staged" not in events
            if case == "atomic_rejected":
                return "native_message_source_out_of_range"
            source_distance = 2
            events.append("atomic_commit")
        return "Previous native administrator command completed\n" + json.dumps({"protocol": protocol,
                           "phase": {"publish": "published", "close": "closed"}[operation]})

    async def load(identifier, position):
        assert identifier == 55 and position == [30, 0, 1]
        events.append("load")
        return recipient

    async def goto(*arguments):
        nonlocal source_distance
        source_distance += .6
        events.append("player_staged")

    async def observe(operation):
        return {"self_identity": {"uid": 1}}

    async def prompt(actor, previous=None):
        if case in ("walking_giver", "atomic_moving_giver") and not acknowledged:
            return {"kind": "Statement", "sender_uid": 2, "dialogue_id": 8, "tag": 0}
        return {"kind": "Question", "sender_uid": 2, "dialogue_id": 8, "tag": 1,
                "content": {"Localized": {
                    "key": "npc-response-quest-messenger-ask",
                    "args": {"name": {"Plain": "Other" if case == "wrong_offer" else "Recipient"}},
                }}}

    async def forbidden_acceptance(*arguments):
        nonlocal acknowledged
        if case in ("walking_giver", "atomic_moving_giver") and arguments[1]["kind"] == "Statement":
            if source_distance >= 5:
                raise RuntimeError("dialogue_sender_unavailable")
            acknowledged = True
            return
        raise AssertionError("Initializer must not accept the native offer")

    helper = SimpleNamespace(prompt=prompt, dialogue_action=forbidden_acceptance,
                             key=lambda content: content["Localized"]["key"],
                             plain=lambda content: content["Plain"])
    operation = prepare_initial_message_offer(
        object(), SimpleNamespace(request=observe), residents, fixture, command, load,
        prepared, helper, SimpleNamespace(goto=goto))
    if case in ("success", "walking_giver", "atomic_moving_giver"):
        asyncio.run(operation)
        assert prepared["loaded_recipient"] == recipient
        assert events.index("load") < events.index("publish") < events.index("close")
        if atomic:
            assert events.index("player_staged") < events.index("publish") < events.index("atomic_commit")
        else:
            assert events.index("player_staged") < events.index("source_staged") < events.index("publish")
        assert acknowledged == (case in ("walking_giver", "atomic_moving_giver"))
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(operation)
        if case in ("wrong_offer", "atomic_rejected"):
            assert events[-1] == "close"
        else:
            assert events == ["prepare"]


@pytest.mark.parametrize("opening_only", [False, True])
def test_initial_message_diagnostic_stops_at_requested_boundary(tmp_path, monkeypatch, opening_only):
    from game.bindings import bind_controls
    from game.veloren.structured_tools.interface import (
        StructuredInterface, agent_observation, agent_tools,
    )
    from scripts.veloren_initial_message_check import public_check

    calls = []
    offer = {
        "sender_uid": 27, "dialogue_id": "12533376870734453177", "tag": 1,
        "text": "Deliver a message to Wiph the Sincere for531 coins?",
        "responses": [{"response_id": 0, "text": "Yes"}],
    }
    recipient = {
        "uid": 291, "name_text": "Wiph the Sincere (Guard)", "distance": 2,
        "control_target": {"uid": 291, "lifecycle": "test-incarnation"},
    }
    rows = iter([
        {"dialogue": offer, "inventory": {"items": []}},
        *[{"dialogue": {**offer, "tag": tag, "responses": []}} for tag in (2, 3, 4)],
        {"position": [18729, 10813, 501]},
        {"position": [18745, 10813, 501]},
        {"nearby_entities": [recipient]},
        {"inventory": {"items": [{"item": {
            "id": {"Simple": "common.items.utility.coins"}, "amount": 531}}]}},
    ])

    async def observe():
        return next(rows)

    async def execute(name, arguments):
        calls.append(name)
        return {"status": "completed"}

    async def sleep(_):
        pass

    monkeypatch.setattr(asyncio, "sleep", sleep)
    controls, _ = bind_controls(
        StructuredInterface(observe, execute), agent_observation, agent_tools(), None)
    result = {"public_actions": 0}
    asyncio.run(public_check(controls, result, tmp_path, opening_only=opening_only))
    expected = ["DialogueResponseTool", *["DialogueAckTool"] * 3]
    if opening_only:
        assert result["opening_only_source_statements"] == 3
        assert "public_reward_delta" not in result
    else:
        expected.append("TalkTool")
        assert result["public_reward_delta"] == 531
    assert calls == expected


def boundaries():
    registry = {
        "schema": "livequest-message-contract/1", "run_id": "run", "nonce": "nonce",
        "opening_sequence": 10, "preexisting_quest_ids": [],
        "player": {"uid": 1, "actor": {"Character": 11}},
        "giver": {"uid": 2, "actor": {"Npc": 22}},
        "recipient": {"uid": 3, "actor": {"Npc": 33}},
    }
    first = {"self_identity": {"uid": 1}, "survival": {"health": {"current": 100}},
             "private_message_evidence": {"registry": registry, "through_sequence": 10,
                                          "ordinary_acceptance_sequences": [], "candidates": []}}
    last = deepcopy(first)
    last["private_message_evidence"].update(
        through_sequence=20, ordinary_acceptance_sequences=[12], candidates=[{
            "activation_sequence": 13,
            "quest": {"quest_id": "new", "quest": {
                "arbiter": {"Npc": 33}, "kind": {"Courier": {"instance": {
                    "kind": "Message", "messenger": {"Character": 11},
                    "source_actor": {"Npc": 22}, "target_actor": {"Npc": 33},
                }}},
            }},
            "reward": {"resolution": True, "actual_reward_inserted": True},
        }])
    return first, last


@pytest.mark.parametrize("change", [None, "missing_close", "changed_target", "reordered"])
def test_v2_opening_requires_native_revocation_and_exact_proposal_parties(change):
    from game.veloren.message_contract import verify_initial_message_protocol

    source, target, player = {"Npc": 1}, {"Npc": 2}, {"Character": 3}
    proposal = {"proposal_id": "native-proposal", "instance": {
        "kind": "Message", "source_actor": source, "target_actor": target, "messenger": player}}
    prepared = {"giver": {"actor": source}, "recipient": {"actor": target},
                "initialization_protocol": {"prepare": deepcopy(proposal)}}
    rows = [{"sequence": 1, "event": "initial_message_v2_prepared", "data": proposal},
            {"sequence": 2, "event": "initial_message_v2_published",
             "data": {"proposal_id": "native-proposal"}},
            {"sequence": 3, "event": "initial_message_v2_closed", "data": {}}]
    if change == "missing_close":
        rows.pop()
    elif change == "changed_target":
        prepared["recipient"]["actor"] = {"Npc": 99}
    elif change == "reordered":
        rows[-1]["sequence"] = 0
    if change is None:
        assert verify_initial_message_protocol(prepared, rows, player)["version"] == "initial-message-v2"
    else:
        with pytest.raises(RuntimeError):
            verify_initial_message_protocol(prepared, rows, player)


@pytest.mark.parametrize("change", [None, "no_commit", "hold_remaining", "not_ready", "out_of_range", "nonfinite"])
def test_v3_ready_requires_atomic_native_commit_and_no_setup_hold(change):
    from game.veloren.message_contract import verify_initial_message_protocol

    source, target, player = {"Npc": 1}, {"Npc": 2}, {"Character": 3}
    proposal = {"protocol": "initial-message-v3", "proposal_id": "native-proposal", "instance": {
        "kind": "Message", "source_actor": source, "target_actor": target, "messenger": player}}
    prepared = {"giver": {"actor": source}, "recipient": {"actor": target},
                "initialization_protocol": {"prepare": deepcopy(proposal)}}
    publication = {"proposal_id": "native-proposal", "atomic_placement": True,
                   "normal_talk_active": True, "source_player_distance": 2, "setup_hold_active": False}
    closure = {"ready": True, "source_player_distance": 2.2, "setup_hold_active": False}
    if change == "no_commit":
        publication["atomic_placement"] = False
    elif change == "hold_remaining":
        closure["setup_hold_active"] = True
    elif change == "not_ready":
        closure["ready"] = False
    elif change == "out_of_range":
        closure["source_player_distance"] = 5
    elif change == "nonfinite":
        publication["source_player_distance"] = float("nan")
    rows = [{"sequence": 1, "event": "initial_message_v3_prepared", "data": proposal},
            {"sequence": 2, "event": "initial_message_v3_published", "data": publication},
            {"sequence": 3, "event": "initial_message_v3_closed", "data": closure}]
    if change is None:
        assert verify_initial_message_protocol(prepared, rows, player)["version"] == "initial-message-v3"
    else:
        with pytest.raises(RuntimeError, match="in-range readiness"):
            verify_initial_message_protocol(prepared, rows, player)


def test_v3_fixture_rejects_native_interaction_boundary_before_launch():
    from pathlib import Path
    from benchmark.config import load_task
    from game.veloren.fixture import validate_fixture

    root = Path(__file__).resolve().parents[3]
    fixture = load_task(
        root / "config/veloren/tasks/structured_tools/native_message_courier_initial_v3.yaml").fixture
    fixture["message_contract"]["giver_position"][0] = fixture["player_state"]["position"][0] + 5
    with pytest.raises(ValueError, match="strictly within"):
        validate_fixture(fixture)
    fixture["message_contract"]["giver_position"][0] -= .01
    validate_fixture(fixture)


def test_exact_native_message_chain():
    assert message_checks(*boundaries())["success"]


def test_message_alive_only_floor_accepts_positive_fractional_health():
    first, last = boundaries()
    last["survival"]["health"]["current"] = .390625
    assert not message_checks(first, last)["success"]
    assert message_checks(first, last, min_health=0)["success"]


@pytest.mark.parametrize("missing", ["acceptance", "correct_recipient", "real_payment"])
def test_message_rejects_incomplete_or_mismatched_chain(missing):
    first, last = boundaries()
    evidence = last["private_message_evidence"]
    if missing == "acceptance":
        evidence["ordinary_acceptance_sequences"] = []
    elif missing == "correct_recipient":
        evidence["candidates"][0]["quest"]["quest"]["arbiter"] = {"Npc": 44}
    else:
        evidence["candidates"][0]["reward"]["actual_reward_inserted"] = False
    assert not message_checks(first, last)["success"]


@pytest.mark.parametrize("eligible,ambiguous", [(True, False), (False, False), (True, True)])
def test_preoffer_restages_each_bounded_attempt_without_accepting(eligible, ambiguous):
    events = []
    residents = [{"uid": 2, "name_text": "Source (Farmer)"},
                 {"uid": 3, "name_text": "Recipient (Farmer)"}]
    prepared = {}
    recipients = [{"name_text": "Recipient", "rtsim_uid": 33}]
    if ambiguous:
        recipients.append({"name_text": "Recipient", "rtsim_uid": 44})

    def content(key):
        return {"Localized": {"key": key, "args": {"name": {"Plain": "Recipient"}}}}

    class Actor:
        async def request(self, operation):
            assert operation == "observe"
            return {"nearby_entities": residents}

    class Helper:
        key = staticmethod(lambda value: value["Localized"]["key"])
        plain = staticmethod(lambda value: value["Plain"])

        async def menu(self, actor, speaker):
            events.append("menu")
            return {"dialogue_id": 1, "tag": 0, "responses": [
                {"content": content("dialogue-question-quest_req"), "response_id": 0}]}

        async def dialogue_action(self, actor, dialogue, response=None):
            events.append(self.key(response["content"]))

        async def prompt(self, actor, previous):
            return {
                "dialogue_id": 1, "tag": 1, "kind": "Question",
                "content": content("npc-response-quest-messenger-ask"
                                   if eligible and events.count("stage") == 2
                                   else "npc-response-quest-slay-ask"),
                "responses": [{"content": content("common-no"), "response_id": 1},
                              {"content": content("common-yes"), "response_id": 2}],
            }

    async def stage():
        events.append("stage")

    if eligible and not ambiguous:
        asyncio.run(prepare_message_offer(
            Actor(), residents[0], recipients,
            stage, prepared, Helper()))
        assert prepared["recipient"]["rtsim_uid"] == 33
        assert events.count("stage") == 2
        assert events.count("common-no") == 1
    else:
        with pytest.raises(RuntimeError, match="Bounded ordinary"):
            asyncio.run(prepare_message_offer(
                Actor(), residents[0], recipients,
                stage, prepared, Helper()))
        assert events.count("stage") == events.count("common-no") == 32
    assert "common-yes" not in events
    assert all(events[index - 1] == "stage"
               for index, event in enumerate(events) if event == "menu")


def test_message_fixture_exposes_ordinary_dialogue(tmp_path):
    from pathlib import Path
    from types import SimpleNamespace

    from benchmark.config import load_task
    from game.veloren.game import VelorenGame
    from game.veloren.structured_tools.interface import FIELDS

    task = load_task(Path("config/veloren/tasks/structured_tools/native_message_courier_initial_v3.yaml"))
    game = VelorenGame(output_dir=tmp_path / "game", fixture=task.fixture, track="structured_tool")
    game.phase = "running"
    row = {field: None for field in FIELDS}
    row.update(dialogue={"dialogue_id": 17, "sender_uid": 2, "tag": 1,
                         "text": "Deliver this message to Rowan.", "responses": [],
                         "content": {"Localized": {"key": "native-localization-key"}}},
               dialogue_markers=[], social_and_trade={"pending_trade": None}, last_trade_result=None)

    async def request(operation):
        assert operation == "observe"
        return row

    game._session = SimpleNamespace(check_ready=lambda: None, request=request)
    observed = asyncio.run(game.get_agent_interface().observe())
    assert observed["dialogue"]["text"] == "Deliver this message to Rowan."
    assert observed["dialogue"]["dialogue_id"] == "17"
    assert "content" not in observed["dialogue"]


@pytest.fixture
def opening(monkeypatch):
    residents = [{"uid": uid, "server_entity": f"entity-{uid}", "actor": {"Npc": uid}}
                 for uid in range(2, 6)]
    offer = {
        "dialogue_id": 17, "tag": 4,
        "content": {"Localized": {"key": "npc-response-quest-messenger-ask"}},
        "responses": [{"content": {"Localized": {"key": "common-yes"}}, "response_id": 0}],
    }
    prepared = {
        "giver": residents[0], "recipient": residents[1], "distractors": residents[2:],
        "offer": offer, "helper_sha256": "unchanged-helper",
    }
    observation = {
        "self_identity": {"uid": 1, "native_character_id": 11},
        "dialogue": {**offer, "kind": "Question", "sender_uid": 2},
    }
    bindings = [{**resident, "dead": False, "health": 100} for resident in residents]
    latest = {"quest_states": [], "combat_entity_bindings": {"bindings": bindings}}
    helper = SimpleNamespace(
        bindings=lambda rows: [{"uid": 1, "actor": {"Character": 11}}],
        latest=lambda rows, event, default=None: latest.get(event, default),
    )
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(contract_evidence=helper))
    rows = [{"sequence": 0, "data": {"run_id": "run", "nonce": "nonce"}}, {"sequence": 10}]
    return prepared, observation, rows, bindings


def test_opening_uses_shared_snapshot_instead_of_stale_preparation_health(opening):
    prepared, observation, rows, bindings = opening
    prepared["giver"]["binding"] = {"dead": True, "health": 0}
    registry = message_registry(prepared, observation, rows)
    assert registry["giver"]["binding"] == bindings[0]
    assert registry["recipient"]["binding"] == bindings[1]
    assert prepared["giver"]["binding"]["dead"]


@pytest.mark.parametrize("participant", range(4))
def test_opening_rejects_dead_participant_including_distractors(opening, participant):
    prepared, observation, rows, bindings = opening
    bindings[participant]["dead"] = True
    with pytest.raises(RuntimeError, match="living participant incarnation"):
        message_registry(prepared, observation, rows)


@pytest.mark.parametrize("problem", ["missing", "ambiguous", "replaced", "nonpositive_health"])
def test_opening_rejects_unproven_participant_incarnation(opening, problem):
    prepared, observation, rows, bindings = opening
    if problem == "missing":
        bindings.pop()
    elif problem == "ambiguous":
        bindings.append(deepcopy(bindings[0]))
    elif problem == "replaced":
        bindings[0]["server_entity"] = "replacement-entity"
    else:
        bindings[0]["health"] = 0
    with pytest.raises(RuntimeError, match="living participant incarnation"):
        message_registry(prepared, observation, rows)


@pytest.mark.parametrize("field,value", [
    ("kind", "Statement"), ("dialogue_id", 18), ("tag", 5), ("sender_uid", 3),
])
def test_opening_rejects_expired_or_replaced_offer(opening, field, value):
    prepared, observation, rows, _ = opening
    observation["dialogue"][field] = value
    with pytest.raises(RuntimeError, match="changed or expired"):
        message_registry(prepared, observation, rows)


def test_postoffer_staging_defers_health_to_existing_opening_snapshot(monkeypatch):
    from game.veloren import message_contract

    residents = [
        {"uid": uid + 100, "rtsim_uid": uid, "name_text": name,
         "actor": {"Npc": uid}, "server_entity": f"entity-{uid}"}
        for uid, name in enumerate(["Source", "Second", "Third", "Recipient"], 1)
    ]
    events = []

    async def command(admin, commands, name, *arguments):
        events.append(name)
        if name == "rtsim_npc":
            selected = residents[:3] if arguments[0] == "civilised,farmer" else residents
            return ", ".join(f"{r['name_text']} ({r['rtsim_uid']})" for r in selected)
        return ""

    async def observe(operation):
        return {"nearby_entities": residents}

    async def goto(*arguments):
        events.append("goto")

    async def wait_observation(actor, predicate, description):
        assert predicate(await actor.request("observe"))

    async def offer(actor, source, recipients, stage, prepared, helper):
        await stage()
        events.append("offer")
        prepared.update(recipient=recipients[0], offer={}, offer_observed_at_ns=1)

    async def forbidden_binding(*arguments):
        pytest.fail("A post-offer full-journal health read consumed native offer lifetime")

    from pathlib import Path
    helper = SimpleNamespace(__file__=__file__)
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", SimpleNamespace(
        contract_evidence=helper, npc_contracts=object(),
        setup=SimpleNamespace(goto=goto, wait_observation=wait_observation)))
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.combat_support",
                        SimpleNamespace(native_binding=forbidden_binding))
    monkeypatch.setattr(message_contract, "native_command_text", command)
    monkeypatch.setattr(message_contract, "prepare_message_offer", offer)
    monkeypatch.setattr(message_contract, "NativeBindingCursor",
                        lambda *args: SimpleNamespace(poll=lambda: residents))
    actor = SimpleNamespace(out=Path("unused-native-output"), request=observe)
    result = asyncio.run(message_contract.initialize_message(actor, actor, {
        "player_state": {"position": [0, 0, 0]},
        "message_contract": {
            "giver_position": [2, 0, 0], "recipient_position": [8, 0, 0],
            "distractor_positions": [[8, 3, 0], [8, -3, 0]],
        },
    }))
    assert result["recipient"]["uid"] == 104
    assert len(result["distractors"]) == 2
    assert events.count("offer") == 1
    assert result["preparation_timing"]["participants_staged_at_ns"] > 1
