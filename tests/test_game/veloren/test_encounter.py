"""Identity-bound combat evidence, counterexamples and bounded public skills."""

from copy import deepcopy

import pytest

from game.veloren.evaluators.encounter import damage_checks, encounter_checks
from game.veloren.evaluators.expedition import expedition_checks
from game.veloren.fixture import validate_fixture
from game.veloren.structured_tools.interface import COMBAT_TOOLS, FIELDS, validate_tool, project
from benchmark.config import load_task
from pathlib import Path


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
