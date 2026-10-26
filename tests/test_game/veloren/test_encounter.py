"""Identity-bound combat evidence, counterexamples and bounded public skills."""

from copy import deepcopy
from collections import deque
import math

import pytest

from game.veloren.evaluators.encounter import damage_checks, encounter_checks
from game.veloren.evaluators.expedition import expedition_checks
from game.veloren.fixture import validate_fixture
from game.veloren.structured_tools.interface import COMBAT_TOOLS, FIELDS, validate_tool, project
from benchmark.config import load_task
from pathlib import Path
from game.veloren.evaluators.deaths import death_snapshot, death_metrics


def test_market_hunting_yard_is_separated_and_connected_in_both_tracks():
    from game.veloren.fixture import solid_voxels

    root = Path(__file__).resolve().parents[3] / "config/veloren/tasks"
    st = load_task(root / "structured_tools/market_hunt_return.yaml")
    vm = load_task(root / "visual_motor/market_hunt_return.yaml")
    assert validate_fixture(st.fixture) == validate_fixture(vm.fixture)
    assert st.task == vm.task
    assert st.time_limit_seconds == vm.time_limit_seconds == 1200
    fixture = st.fixture
    target = fixture["encounters"][0]["position"]
    assert math.dist(target, fixture["merchant"]["position"]) > 80
    assert 80 < math.dist(target, fixture["player_state"]["position"]) < 96
    voxels = solid_voxels(fixture)
    walkable = {(x, y) for x, y, z in voxels if z == 500
                and (x, y, 501) not in voxels and (x, y, 502) not in voxels}
    start = tuple(math.floor(value) for value in fixture["player_state"]["position"][:2])
    goal = tuple(math.floor(value) for value in target[:2])
    reached, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbor in walkable and neighbor not in reached:
                reached.add(neighbor)
                queue.append(neighbor)
    assert goal in reached
    assert all((x, y) in reached for x in range(18727, 18785) for y in range(10820, 10826))
    merchant = tuple(math.floor(value) for value in fixture["merchant"]["position"][:2])
    assert merchant not in reached
    assert (18710, 10806) in reached
    assert math.dist([18710.5, 10806.5, 501], fixture["merchant"]["position"]) <= 3
    assert (18710, 10808, 501) in voxels
    assert (18710, 10808, 502) not in voxels
    assert (18710, 10808, 503) in voxels


def test_dual_encounter_divider_blocks_opening_sightlines_without_sealing_targets():
    from game.veloren.fixture import solid_voxels

    root = Path(__file__).resolve().parents[3] / "config/veloren/tasks"
    st = load_task(root / "structured_tools/dual_legoom.yaml")
    vm = load_task(root / "visual_motor/dual_legoom.yaml")
    assert validate_fixture(st.fixture) == validate_fixture(vm.fixture)
    assert st.task == vm.task
    assert st.evaluator_parameters == vm.evaluator_parameters == {"roles": ["west_legoom", "east_legoom"]}
    assert st.time_limit_seconds == vm.time_limit_seconds == 300
    fixture = st.fixture
    voxels = solid_voxels(fixture)
    start = fixture["player_state"]["position"]
    for enemy in fixture["encounters"]:
        target = enemy["position"]
        fraction = (10815.5 - start[1]) / (target[1] - start[1])
        crossing_x = math.floor(start[0] + fraction * (target[0] - start[0]))
        assert all((crossing_x, 10815, z) in voxels for z in (501, 502, 503))
        route = [(x, 10806) for x in range(18708, 18721)]
        route += [(18720, y) for y in range(10806, 10821)]
        route += [(x, 10820) for x in range(math.floor(target[0]), 18721)]
        assert all((x, y, 500) in voxels and (x, y, 501) not in voxels
                   and (x, y, 502) not in voxels for x, y in route)
    assert fixture["player_state"]["health"] == 100
    assert fixture["player_state"]["inventory"] == {"common.items.consumable.potion_minor": 2}


def test_native_death_accounting_counts_repeated_deaths_not_other_actors():
    identity = {"uid": 1, "native_character_id": 7}
    rows = [
        {"event": "opened", "sequence": 0, "data": {"run_id": "run", "nonce": "nonce"}},
        {"event": "combat_entity_bindings", "sequence": 1, "data": {"bindings": [
            {"uid": 1, "server_entity": "player", "health": 100, "dead": False},
        ]}},
    ]
    initial = {"self_identity": identity, "private_death_evidence": death_snapshot(rows, identity)}
    for sequence, uid in ((2, 1), (3, 99), (4, 1)):
        rows.append({"schema": "rpg-native-oracle", "version": "1.1", "private": True,
                     "event": "native_entity_death", "sequence": sequence,
                     "host_unix_ns": str(1000000000 + sequence),
                     "data": {"uid": uid, "entity": "player" if uid == 1 else "enemy"}})
    registry = initial["private_death_evidence"]["registry"]
    final = {"self_identity": identity, "private_death_evidence": death_snapshot(rows, identity, registry)}
    assert death_metrics(initial, final)["deaths"]["count"] == 2
    assert death_metrics(initial, initial)["deaths"]["count"] == 0
    for mutate in (
        lambda evidence: evidence["events"].reverse(),
        lambda evidence: evidence["events"][0]["data"].update(entity="replacement"),
        lambda evidence: evidence["events"][0].update(host_unix_ns=None),
        lambda evidence: evidence.update(through_sequence=1),
    ):
        changed = deepcopy(final)
        mutate(changed["private_death_evidence"])
        with pytest.raises(ValueError):
            death_metrics(initial, changed)
    with pytest.raises(ValueError, match="identity changed"):
        death_snapshot(rows, {"uid": 1, "native_character_id": 8}, registry)
    rows[1]["data"]["bindings"][0]["server_entity"] = "replacement"
    with pytest.raises(ValueError, match="identity changed"):
        death_snapshot(rows, identity, registry)


def test_respawn_is_native_parameter_free_and_death_evidence_is_private():
    assert validate_tool("RespawnTool", {}) == ("respawn", {})
    with pytest.raises(ValueError):
        validate_tool("RespawnTool", {"position": [0, 0, 0]})
    assert "RespawnTool" in COMBAT_TOOLS
    assert "private_death_evidence" not in FIELDS


def evidence():
    source = {"uid": 1, "server_entity": "player-generation-1", "health": 100, "dead": False}
    target = {"uid": 2, "server_entity": "enemy-generation-1", "health": 25,
              "dead": False, "alignment": "Enemy"}
    registry = {"run_id": "run", "nonce": "nonce", "opening_sequence": 10,
                "source": source, "targets": [{"role": "enemy", "binding": target}]}
    initial = {
        "self_identity": {"uid": 1}, "survival": {"health": {"current": 100, "dead": False}},
        "private_encounter_evidence": {"schema": "livequest-encounter/1", "registry": registry,
                                       "through_sequence": 10, "events": []},
    }
    final = deepcopy(initial)
    events = [
        {"event": "health_effect_applied", "sequence": 11, "data": {
            "changed": True, "requested_amount": -25, "before": 25, "after": 0,
            "contributor": {"Solo": 1}, "contributor_entity": source["server_entity"],
            "target_uid": 2, "target_entity": target["server_entity"],
        }},
        {"event": "native_entity_death", "sequence": 12,
         "data": {"uid": 2, "entity": target["server_entity"]}},
    ]
    for event in events:
        event.update(schema="rpg-native-oracle", version="1.1", private=True)
    final["private_encounter_evidence"].update(events=events, through_sequence=12)
    return initial, final


def test_actual_death_and_own_damage_are_both_required():
    initial, final = evidence()
    assert encounter_checks(initial, final, roles=["enemy"])["success"]
    damage_only = deepcopy(final)
    damage_only["private_encounter_evidence"]["events"].pop()
    assert damage_checks(initial, damage_only, roles=["enemy"])["success"]
    assert not encounter_checks(initial, damage_only, roles=["enemy"])["success"]
    for field, value in (
        ("contributor", {"Solo": 99}), ("contributor_entity", "reused-player-generation"),
        ("target_entity", "reused-enemy-generation"), ("changed", False),
        ("requested_amount", 0), ("after", 25),
    ):
        changed = deepcopy(final)
        changed["private_encounter_evidence"]["events"][0]["data"][field] = value
        assert not encounter_checks(initial, changed, roles=["enemy"])["success"]
        assert not damage_checks(initial, changed, roles=["enemy"])["success"]


    for index in (0, 1):
        changed = deepcopy(final)
        changed["private_encounter_evidence"]["events"].pop(index)
        assert not encounter_checks(initial, changed, roles=["enemy"])["success"]
    for field, value in (("uid", 99), ("entity", "different-generation")):
        changed = deepcopy(final)
        changed["private_encounter_evidence"]["events"][1]["data"][field] = value
        assert not encounter_checks(initial, changed, roles=["enemy"])["success"]
    changed = deepcopy(final)
    changed["survival"]["health"]["current"] = 0
    assert not encounter_checks(initial, changed, roles=["enemy"])["success"]


def test_companion_requires_original_living_owned_identity_not_replacement_or_disappearance():
    initial, final = evidence()
    pet = {"uid": 3, "server_entity": "sheep-generation-1", "alignment": {"Owned": 1},
           "group": 7, "health": 40, "maximum_health": 40, "dead": False}
    target = {"uid": 3, "lifecycle": "client-sheep-generation-1"}
    public = {"uid": 3, "control_target": target, "position": [3, 0, 0], "group": 7,
              "same_native_group": True, "companion": {"owned_by_actor": True},
              "health": {"current": 40, "dead": False}}
    for row in (initial, final):
        row.update(position=[0, 0, 0], nearby_entities=[deepcopy(public)])
        row["private_encounter_evidence"]["registry"]["source"]["group"] = 7
        row["private_encounter_evidence"]["registry"]["companion"] = {
            "binding": deepcopy(pet), "player_target": deepcopy(target),
        }
        row["private_encounter_evidence"]["companion_binding"] = deepcopy(pet)
    parameters = {"roles": ["enemy"], "companion": {"max_distance": 4, "min_health": 1}}
    assert encounter_checks(initial, final, **parameters)["success"]
    for change in (
        lambda row: row.update(nearby_entities=[]),
        lambda row: row["nearby_entities"][0]["companion"].update(owned_by_actor=False),
        lambda row: row["nearby_entities"][0].update(position=[4.01, 0, 0]),
        lambda row: row["private_encounter_evidence"]["companion_binding"].update(server_entity="replacement"),
    ):
        changed = deepcopy(final)
        change(changed)
        assert not encounter_checks(initial, changed, **parameters)["success"]
    death = deepcopy(final["private_encounter_evidence"]["events"][-1])
    death.update(sequence=13, data={"uid": 3, "entity": "sheep-generation-1"})
    final["private_encounter_evidence"]["events"].append(death)
    final["private_encounter_evidence"]["through_sequence"] = 13
    assert not encounter_checks(initial, final, **parameters)["success"]


def test_native_contract_requires_activation_then_bound_kill_and_actual_reward_chain():
    from game.veloren.evaluators.contract import contract_checks

    initial, final = evidence()
    player, giver, target = {"Character": 3}, {"Npc": 4}, {"Npc": 5}
    control = {"uid": 1, "lifecycle": "player-client"}
    target_ref = {"uid": 2, "lifecycle": "enemy-client"}
    registry = {
        "run_id": "run", "nonce": "nonce", "opening_sequence": 10, "preexisting_quest_ids": [],
        "helper_sha256": "a" * 64, "giver_actor": giver, "target_actor": target,
        "player": {"uid": 1, "server_entity": "player-generation-1", "actor": player,
                   "client_session_id": "session", "client_actor": control},
    }
    for row in (initial, final):
        row.update(session_id="session", control_actor=control,
                   nearby_entities=[{"uid": 2, "control_target": target_ref}])
        row["private_encounter_evidence"]["registry"]["targets"][0]["role"] = "contract_target"
        row["private_contract_evidence"] = {
            "schema": "livequest-native-contract/1", "registry": deepcopy(registry),
            "through_sequence": 10, "candidates": [], "player_deaths": [],
        }
    for event in final["private_encounter_evidence"]["events"]:
        event["sequence"] += 1
    final["private_encounter_evidence"]["through_sequence"] = 20
    proof = final["private_contract_evidence"]
    proof["through_sequence"] = 20
    assert not contract_checks(initial, final)["success"]
    quest = {"kind": {"Slay": {"slayer": player, "target": target}}, "arbiter": giver, "res": 0}
    proof["candidates"] = [{
        "activation_sequence": 11, "quest": {"quest_id": 99, "quest": quest, "resolution": None},
        "slay": {"native_target_death": True, "player_contribution": True, "death_sequences": [14],
                 "contribution_sequences": [12], "client_uid_lifecycle_links": [target_ref]},
        "reward": {"resolution": True, "actual_reward_inserted": True, "chains": [{
            "transaction_id": "nonce:1", "quest_id": 99, "settlement_sequence": 15, "creation_sequence": 16,
            "removal_sequences": [17], "insertion_sequences": [18],
            "item": {"Simple": "common.items.utility.coins"}, "amount": 1000,
            "native_quest_before": quest, "native_quest_at_settlement": {**quest, "res": 2},
        }]},
    }]
    assert contract_checks(initial, final)["success"]
    for change in (
        lambda row: row["candidates"][0]["reward"].update(actual_reward_inserted=False),
        lambda row: row["candidates"][0]["reward"]["chains"][0].update(amount=999),
        lambda row: row["candidates"][0]["reward"]["chains"][0].update(transaction_id="different-run:1"),
        lambda row: row["candidates"][0]["slay"].update(client_uid_lifecycle_links=[]),
        lambda row: row.update(player_deaths=[19]),
    ):
        changed = deepcopy(final)
        change(changed["private_contract_evidence"])
        assert not contract_checks(initial, changed)["success"]
    proof["candidates"][0]["slay"]["contribution_sequences"] = [11]
    with pytest.raises(ValueError, match="sequence"):
        contract_checks(initial, final)


def test_expedition_requires_native_preparation_before_first_damage():
    initial, final = evidence()
    chest = "common.items.armor.hide.rawhide.chest"
    equipment = [{"slot": {"Armor": "Chest"}, "item": {"Simple": chest}}]
    for row in (initial, final):
        row.update(position=[0, 0, 0], velocity=[0, 0, 0], on_ground=True,
                   inventory={"equipment": {"chest": {"id": {"Simple": chest}}}})
        row["private_encounter_evidence"]["registry"]["source"]["equipment"] = []
        row["private_encounter_evidence"]["equipment_samples"] = []
    final["private_encounter_evidence"]["equipment_samples"] = [{
        "uid": 1, "server_entity": "player-generation-1", "sequence": 11, "equipment": equipment,
    }]
    for event in final["private_encounter_evidence"]["events"]:
        event["sequence"] += 1
    final["private_encounter_evidence"]["through_sequence"] = 13
    parameters = {"roles": ["enemy"], "chest_item": chest, "equipment": {"chest": chest},
                  "position": {"target": [0, 0, 0], "horizontal_tolerance": 1,
                               "vertical_tolerance": .5, "max_speed": .1}}
    assert expedition_checks(initial, final, **parameters)["success"]
    for samples in ([], [dict(final["private_encounter_evidence"]["equipment_samples"][0], sequence=12)]):
        changed = deepcopy(final)
        changed["private_encounter_evidence"]["equipment_samples"] = samples
        assert not expedition_checks(initial, changed, **parameters)["success"]
    for update in ({"server_entity": "other-generation"}, {"sequence": 10}, {"sequence": 14}):
        changed = deepcopy(final)
        changed["private_encounter_evidence"]["equipment_samples"][0].update(update)
        with pytest.raises(ValueError):
            expedition_checks(initial, changed, **parameters)
    final["position"][0] = 2
    assert not expedition_checks(initial, final, **parameters)["success"]


def test_expedition_catalog_admits_paired_native_fixtures():
    root = Path(__file__).resolve().parents[3] / "config/veloren/tasks"
    st = load_task(root / "structured_tools/provisioned_hunt_return.yaml")
    vm = load_task(root / "visual_motor/provisioned_hunt_return.yaml")
    assert validate_fixture(st.fixture) == validate_fixture(vm.fixture)
    assert st.evaluator_parameters == vm.evaluator_parameters


def test_registry_events_and_multiple_targets_are_not_silently_accepted():
    initial, final = evidence()
    for mutate in (
        lambda row: row["registry"].update(nonce="different"),
        lambda row: row.update(through_sequence=11),
        lambda row: row["events"][0].update(sequence=9),
        lambda row: row["events"][0].update(private=False),
        lambda row: row["events"].reverse(),
    ):
        changed = deepcopy(final)
        mutate(changed["private_encounter_evidence"])
        with pytest.raises(ValueError):
            encounter_checks(initial, changed, roles=["enemy"])
    with pytest.raises(ValueError):
        encounter_checks(initial, final, roles=["enemy", "missing"])
    for row in (initial, final):
        extra = deepcopy(row["private_encounter_evidence"]["registry"]["targets"][0])
        extra["role"] = "second"
        extra["binding"].update(uid=3, server_entity="second-enemy")
        row["private_encounter_evidence"]["registry"]["targets"].append(extra)
    assert not encounter_checks(initial, final, roles=["enemy", "second"])["success"]


def test_player_death_before_terminal_recovery_is_failure():
    initial, final = evidence()
    death = deepcopy(final["private_encounter_evidence"]["events"][-1])
    death.update(sequence=13, data={"uid": 1, "entity": "player-generation-1"})
    final["private_encounter_evidence"]["events"].append(death)
    final["private_encounter_evidence"]["through_sequence"] = 13
    assert not encounter_checks(initial, final, roles=["enemy"])["success"]
    assert not damage_checks(initial, final, roles=["enemy"])["success"]


def test_group_damage_preserves_actor_identity_and_must_precede_death():
    initial, final = evidence()
    events = final["private_encounter_evidence"]["events"]
    events[0]["data"]["contributor"] = {"Group": {"entity_uid": 1, "group": 7}}
    assert encounter_checks(initial, final, roles=["enemy"])["success"]
    events[0]["data"]["contributor"]["Group"]["entity_uid"] = 99
    assert not encounter_checks(initial, final, roles=["enemy"])["success"]
    events[0]["data"]["contributor"]["Group"]["entity_uid"] = 1
    events[0]["sequence"], events[1]["sequence"] = 12, 11
    events.reverse()
    assert not encounter_checks(initial, final, roles=["enemy"])["success"]


def test_combat_does_not_override_reserve_or_destination_requirements():
    initial, final = evidence()
    for row in (initial, final):
        row.update(inventory={"items": []}, position=[0, 0, 0], velocity=[0, 0, 0], on_ground=True)
    state = {"inventory": [{"item": "potion", "min_count": 1}],
             "position": {"target": [0, 0, 0], "horizontal_tolerance": 1,
                          "vertical_tolerance": .5, "max_speed": .1}}
    assert not encounter_checks(initial, final, roles=["enemy"], **state)["success"]
    final["inventory"]["items"] = [{"item": {"id": {"Simple": "potion"}, "amount": 1}}]
    assert encounter_checks(initial, final, roles=["enemy"], **state)["success"]
    final["position"][2] = 10
    assert not encounter_checks(initial, final, roles=["enemy"], **state)["success"]


def test_public_projection_never_contains_private_encounter_registry():
    row = {name: {} for name in FIELDS}
    row["private_encounter_evidence"] = {"secret": True}
    row["private_motion_evidence"] = {"secret": True}
    assert "private_encounter_evidence" not in project(row)
    assert "private_motion_evidence" not in project(row)


def test_public_combat_tools_are_bounded_and_never_autoaim():
    assert "StrikeTool" not in COMBAT_TOOLS
    assert validate_tool("StrikeTool", {"x": 1, "y": 2, "z": 3, "duration_ticks": 10}) == (
        "aimed_attack", {"x": 1, "y": 2, "z": 3, "duration_ticks": 10})
    with pytest.raises(ValueError):
        validate_tool("StrikeTool", {"x": 1, "y": 2, "z": 3, "duration_ticks": 61})
    assert validate_tool("LookTool", {"x": 1, "y": 2, "z": 3}) == ("look_at", {"position": [1, 2, 3]})
    assert validate_tool("AttackTool", {"channel": "primary", "duration_ticks": 60}) == (
        "attack_primary", {"duration_ticks": 60},
    )
    for args in (
        {"channel": "primary", "duration_ticks": 61},
        {"channel": "primary", "duration_ticks": True},
        {"channel": "primary", "duration_ticks": 10, "target_uid": 2},
    ):
        with pytest.raises(ValueError):
            validate_tool("AttackTool", args)
    with pytest.raises(ValueError):
        validate_tool("WieldTool", {"wield": 1})


def test_settlement_projection_preserves_dialogue_ids_without_expanding_old_profiles():
    from game.veloren.structured_tools.interface import EXPEDITION_TOOLS

    assert "TalkTool" not in EXPEDITION_TOOLS
    row = {name: {} for name in FIELDS}
    identifier = 2**64 - 1
    row.update(
        dialogue={"sender_uid": 7, "sender": {"uid": 7, "lifecycle": "incarnation:Entity(7, 1)"},
                  "dialogue_id": identifier, "received_client_tick": 8, "kind": "Question", "tag": 9,
                  "text": "Where?", "responses": [{"response_id": 2, "text": "Workshop", "content": "not projected"}],
                  "dialogue": {"not": "projected"}},
        dialogue_markers=[], social_and_trade={"pending_trade": None, "players": ["not projected"]},
        last_trade_result=None, private_encounter_evidence={"not": "projected"},
    )
    assert "dialogue" not in project(row)
    public = project(row, rpg=True)
    assert public["dialogue"]["dialogue_id"] == str(identifier)
    assert "dialogue" not in public["dialogue"] and "social_and_trade" not in public
    assert "private_encounter_evidence" not in public and public["pending_trade"] is None
    assert public["dialogue"]["responses"] == [{"response_id": 2, "text": "Workshop"}]
    args = {"sender_uid": 7, "dialogue_id": str(identifier), "tag": 9, "response_id": 2}
    native, converted = validate_tool("DialogueResponseTool", args)
    assert native == "dialogue_action" and converted["dialogue_id"] == identifier
    assert converted["operation"] == "respond"
    for value in (identifier, str(2**64), "-1", "1e3", "abc"):
        with pytest.raises(ValueError):
            validate_tool("DialogueResponseTool", {**args, "dialogue_id": value})


def test_native_settlement_fixture_does_not_hide_an_authored_platform():
    from game.veloren.fixture import solid_voxels

    root = Path(__file__).resolve().parents[3]
    fixture = load_task(root / "config/veloren/tasks/structured_tools/known_food.yaml").fixture
    fixture.pop("platform")
    fixture["native_site"] = "Spausalm"
    fixture["player_state"]["position"] = [18703.5, 10799.5, 382]
    assert solid_voxels(validate_fixture(fixture)) == set()
    with pytest.raises(ValueError, match="exactly one"):
        validate_fixture({**fixture, "platform": {}})
    with pytest.raises(ValueError, match="do not author"):
        validate_fixture({**fixture, "encounters": []})


def test_merchant_lifecycle_is_bound_in_the_player_client_not_the_admin_client():
    from game.veloren.settlement import bind_merchant, quoted_stack, verify_merchant

    admin = {"uid": 7, "lifecycle": "admin:Entity(1, 1)"}
    player = {"uid": 7, "lifecycle": "player:Entity(12, 1)"}
    row = {"nearby_entities": [{"uid": 7, "control_target": player, "health": {"current": 100, "dead": False}}]}
    prepared = bind_merchant(row, {"uid": 7, "administrator_target": admin})
    assert prepared["player_target"] == player
    verify_merchant(row, prepared)
    changed = deepcopy(row)
    changed["nearby_entities"][0]["control_target"]["lifecycle"] = "player:Entity(12, 2)"
    with pytest.raises(RuntimeError, match="lifecycle"):
        verify_merchant(changed, prepared)
    books = [{"slot": slot, "amount": 1, "id": {"Simple": "book"}, "unit_site_value": 33.33}
             for slot in (589836, 0)]
    assert quoted_stack(books, "book")["slot"] == 0
    with pytest.raises(RuntimeError, match="no quoted stack"):
        quoted_stack(books, "missing")


def test_encounter_fixture_rejects_ambiguous_or_unsupported_enemies():
    root = Path(__file__).resolve().parents[3]
    fixture = load_task(root / "config/veloren/tasks/structured_tools/dual_legoom.yaml").fixture
    assert len(validate_fixture(fixture)["encounters"]) == 2
    for mutate in (
        lambda rows: rows[1].update(role=rows[0]["role"]),
        lambda rows: rows[0].update(asset="common.entity.invalid"),
        lambda rows: rows[0].update(position=fixture["player_state"]["position"]),
    ):
        changed = deepcopy(fixture)
        mutate(changed["encounters"])
        with pytest.raises(ValueError):
            validate_fixture(changed)


def test_encounter_catalog_pairs_share_fixtures_and_simultaneous_requirements():
    root = Path(__file__).resolve().parents[3] / "config/veloren/tasks"
    for name in ("defeat_legoom", "dual_legoom", "combat_supply_return"):
        st = load_task(root / "structured_tools" / f"{name}.yaml")
        vm = load_task(root / "visual_motor" / f"{name}.yaml")
        assert st.fixture == vm.fixture
        assert st.evaluator_parameters == vm.evaluator_parameters
        assert st.time_limit_seconds == vm.time_limit_seconds
    material = "common.items.crafting_ing.leather.simple_leather"
    assert st.fixture["supplies"][0]["item"] == material
    assert {"item": material, "min_count": 1, "min_delta": 1} in st.evaluator_parameters["inventory"]
    assert st.evaluator_parameters["position"]["target"] == st.fixture["player_state"]["position"]
