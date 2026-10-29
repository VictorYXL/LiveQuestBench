from copy import deepcopy
from pathlib import Path

import pytest

from benchmark.config import load_task
from benchmark.factory import make_game
from game.veloren.evaluators.encounter_supplies import encounter_supply_checks
from tests.test_game.veloren.test_encounter import evidence


POTION = "common.items.consumable.potion_minor"
PARAMETERS = {
    "roles": ["enemy"], "supplies": [{"item": POTION, "amount": 3}],
    "required_attack": {"source": "Projectile", "tool": "Bow", "lethal": True},
    "inventory": [{"item": POTION, "min_count": 1}],
}


def event(sequence, kind, **data):
    return {"schema": "rpg-native-oracle", "version": "1.1", "private": True,
            "sequence": sequence, "event": kind, "data": data}


def snapshots(*, collect=True, replacement=False):
    initial, final = evidence()
    initial["inventory"] = {"items": []}
    final["inventory"] = {"items": [{"item": {"id": {"Simple": POTION}, "amount": 1}}]}
    registry = {
        "run_id": "run", "nonce": "nonce", "opening_sequence": 10,
        "actor": {"uid": 1, "server_entity": "player-generation-1"},
        "sources": [{"uid": 9, "entity": "original-source", "item": POTION,
                     "amount": 3, "created_sequence": 1, "spawned_at": 0, "lifetime_seconds": 300}],
    }
    initial["private_pickup_evidence"] = {
        "schema": "livequest-source-pickups/1", "registry": registry,
        "through_sequence": 10, "events": [],
    }
    final["private_pickup_evidence"] = deepcopy(initial["private_pickup_evidence"])
    data = {"item": {"Simple": POTION}, "source_uid": 99 if replacement else 9,
            "source_entity": "substitute" if replacement else "original-source", "amount": 3}
    if collect:
        pickup = event(11, "item_pickup_applied", **data, server_time=5,
                       source_amount_before=3, source_amount_after=0,
                       collector_uid=1, collector_entity="player-generation-1")
    else:
        pickup = event(11, "item_drop_expired", **data, server_time=301,
                       spawned_at=0, lifetime_seconds=300)
    final["private_pickup_evidence"].update(events=[pickup], through_sequence=14)
    effect, death = final["private_encounter_evidence"]["events"]
    effect.update(sequence=13)
    effect["data"].update(cause={"Attack": "Projectile"}, instance=7, change_time=400)
    death.update(sequence=14)
    death["data"]["cause"] = {
        "amount": -25, "by": {"Solo": 1}, "cause": {"Attack": "Projectile"}, "instance": 7, "time": 400,
    }
    queued = event(12, "attack_health_effect_queued", source_uid=1,
                   source_entity="player-generation-1", target_uid=2,
                   target_entity="enemy-generation-1", instance=7, requested_amount=-25,
                   server_time=400, attack_source="Projectile", ability={"tool": "Bow"})
    final["private_encounter_evidence"].update(events=[queued, effect, death], through_sequence=14)
    return initial, final


def test_collect_first_can_finish_after_ground_expiry_and_consume_two_potions():
    result = encounter_supply_checks(*snapshots(), **PARAMETERS)
    assert result["success"]
    collection = next(c for c in result["checks"] if c["kind"] == "original_supply_collection")
    assert collection["guaranteed_collected"] == 3
    assert result["native_pickup_events"][0]["data"]["server_time"] == 5


@pytest.mark.parametrize("kwargs", [{"collect": False}, {"replacement": True}])
def test_skipping_or_replacing_original_stock_fails_despite_bow_kill_and_retained_potion(kwargs):
    result = encounter_supply_checks(*snapshots(**kwargs), **PARAMETERS)
    assert not result["success"]
    assert not next(c for c in result["checks"] if c["kind"] == "original_supply_collection")["passed"]


def test_collection_does_not_replace_native_bow_lethal_requirement():
    initial, final = snapshots()
    final["private_encounter_evidence"]["events"][0]["data"]["ability"]["tool"] = "Staff"
    result = encounter_supply_checks(initial, final, **PARAMETERS)
    assert not result["success"]
    assert next(c for c in result["checks"] if c["kind"] == "original_supply_collection")["passed"]


@pytest.mark.parametrize("change", ["world", "player", "boundary", "amount"])
def test_joint_evidence_rejects_cross_world_actor_boundary_or_source_changes(change):
    initial, final = snapshots()
    registry = initial["private_pickup_evidence"]["registry"]
    if change == "world":
        registry["nonce"] = "another-world"
    elif change == "player":
        registry["actor"]["server_entity"] = "replacement-player"
        final["private_pickup_evidence"]["events"][0]["data"]["collector_entity"] = "replacement-player"
    elif change == "boundary":
        final["private_pickup_evidence"]["through_sequence"] = 15
    else:
        registry["sources"][0]["amount"] = 2
        final["private_pickup_evidence"]["events"][0]["data"].update(amount=2, source_amount_before=2)
    final["private_pickup_evidence"]["registry"] = deepcopy(registry)
    with pytest.raises(ValueError):
        encounter_supply_checks(initial, final, **PARAMETERS)


def test_admitted_binding_requires_native_sources_in_both_profiles(tmp_path):
    tasks = [load_task(Path("config/veloren/tasks") / track /
                       "moving_target_bow_hunt_open_court_v3.yaml")
             for track in ("structured_tools", "visual_motor")]
    assert tasks[0].fixture == tasks[1].fixture
    for index, task in enumerate(tasks):
        make_game(task, tmp_path / str(index), headless=True, recording=False, recording_fps=5)
        task.fixture["pickup_evidence"] = False
        with pytest.raises(ValueError, match="matching native fixture sources"):
            make_game(task, tmp_path / f"bad-{index}", headless=True, recording=False, recording_fps=5)
        task.fixture["pickup_evidence"] = True
        task.evaluator_parameters["roles"] = ["substituted-target"]
        with pytest.raises(ValueError, match="Scored encounter roles"):
            make_game(task, tmp_path / f"bad-role-{index}", headless=True, recording=False, recording_fps=5)
