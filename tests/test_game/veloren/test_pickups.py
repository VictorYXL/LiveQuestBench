import copy

import pytest

from game.veloren.evaluators.pickups import collection_checks, pickup_snapshot, team_collection_checks
from game.veloren.runtime.journal import snapshot_rows
from tests.test_game.veloren.test_journal import journal_rows, write_rows


ITEM = "common.items.food.cheese"


def event(sequence, kind, **data):
    return {
        "schema": "rpg-native-oracle", "version": "1.1", "private": True,
        "sequence": sequence, "event": kind,
        "data": {"item": {"Simple": ITEM}, "server_time": 30.0, **data},
    }


def initial():
    rows = journal_rows()[:1]
    rows[0]["data"]["nonce"] = "native-process"
    rows.append(event(1, "item_drop_created", source_uid=9, source_entity="original",
                      amount=3, spawned_at=10, lifetime_seconds=300))
    rows.append({**rows[0], "sequence": 2, "event": "boundary"})
    snapshot = pickup_snapshot(rows, [{"uid": 9, "item": ITEM, "amount": 3}],
                               {"uid": 7, "server_entity": "player"}, 20)
    return {"private_pickup_evidence": snapshot}


def pickup(sequence, *, uid=9, entity="original", amount=3, before=3, after=0, owner=7):
    return event(sequence, "item_pickup_applied", source_uid=uid, source_entity=entity,
                 amount=amount, source_amount_before=before, source_amount_after=after,
                 collector_uid=owner, collector_entity="player" if owner == 7 else "other")


def score(events):
    first = initial()
    last = copy.deepcopy(first)
    last["private_pickup_evidence"].update(events=events, through_sequence=events[-1]["sequence"])
    return collection_checks(first, last)["checks"][0]


def test_only_actual_original_source_collection_qualifies():
    assert score([pickup(3)])["passed"]
    assert not score([pickup(3, uid=10, entity="substitute")])["passed"]
    assert not score([pickup(3, owner=8)])["passed"]


def test_complete_mixed_stack_across_partial_pickups_proves_all_original_units():
    mixed = event(3, "item_drop_merged_on_creation", target_uid=9, target_entity="original",
                  incoming_amount=1, target_amount_before=3, target_amount_after=4)
    first = pickup(4, amount=1, before=4, after=3)
    assert score([mixed, first])["guaranteed_collected"] == 0
    assert score([mixed, first, pickup(5)])["passed"]
    stolen = pickup(4, amount=1, before=4, after=3, owner=8)
    assert score([mixed, stolen, pickup(5)])["guaranteed_collected"] == 2


def test_original_lineage_survives_native_entity_merge():
    merged = event(3, "item_drop_merged", source_uid=9, source_entity="original", source_amount=3,
                   target_uid=10, target_entity="merged", target_amount_before=1, target_amount_after=4)
    assert score([merged, pickup(4, uid=10, entity="merged", amount=4, before=4)])["passed"]
    with pytest.raises(ValueError, match="retired"):
        score([merged, pickup(4)])


def test_native_expiry_records_loss_not_missing_entity_guess():
    expired = event(4, "item_drop_expired", source_uid=9, source_entity="original", amount=2,
                    spawned_at=10, lifetime_seconds=300, server_time=311)
    assert score([pickup(3, amount=1, after=2), expired])["guaranteed_collected"] == 1
    with pytest.raises(ValueError, match="retired"):
        score([pickup(3, amount=1, after=2), expired, pickup(5, amount=2, before=2)])


@pytest.mark.parametrize("change", ["generation", "quantity", "ordering", "world"])
def test_pickup_receipts_fail_closed_on_invalid_scope_or_conservation(change):
    first = initial()
    last = copy.deepcopy(first)
    row = pickup(3)
    if change == "generation":
        row["data"]["source_entity"] = "another-generation"
    elif change == "quantity":
        row["data"]["amount"] = 4
    elif change == "ordering":
        row["sequence"] = 2
    else:
        last["private_pickup_evidence"]["registry"]["nonce"] = "different-process"
    last["private_pickup_evidence"].update(events=[row], through_sequence=3)
    with pytest.raises(ValueError):
        collection_checks(first, last)


def test_pickup_projection_keeps_creation_before_opening_and_native_terminal_events(tmp_path):
    rows = journal_rows()
    rows[2] = event(2, "item_drop_created", source_uid=9, source_entity="original", amount=3,
                    spawned_at=10, lifetime_seconds=300)
    rows[5] = pickup(5)
    rows[6] = event(6, "item_drop_expired", source_uid=10, source_entity="other",
                    amount=1, spawned_at=0, lifetime_seconds=300, server_time=301)
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    projected = snapshot_rows(path, "game", after_sequence=4, pickups=True)
    assert [row["sequence"] for row in projected] == [0, 2, 4, 5, 6, 7]
    assert [row["sequence"] for row in snapshot_rows(path, "game", after_sequence=4)] == [0, 4, 7]


def test_independent_peer_can_collect_but_another_native_world_cannot():
    first = {"Alpha": initial(), "Beta": {}}
    for role, uid, entity in (("Alpha", 7, "player"), ("Beta", 8, "other")):
        identity = {"uid": uid, "lifecycle": role}
        first[role].update(self_identity=identity, private_death_evidence={"registry": {
            "identity": identity, "uid": uid, "server_entity": entity,
            "run_id": "game", "nonce": "native-process",
        }})
    last = copy.deepcopy(first)
    last["Alpha"]["private_pickup_evidence"].update(events=[pickup(3, owner=8)], through_sequence=3)
    required = [{"item": ITEM, "amount": 3}]
    assert team_collection_checks(first, last, supplies=required)["success"]
    first["Beta"]["private_death_evidence"]["registry"]["nonce"] = "another-world"
    last["Beta"]["private_death_evidence"]["registry"]["nonce"] = "another-world"
    with pytest.raises(ValueError, match="original world"):
        team_collection_checks(first, last, supplies=required)
