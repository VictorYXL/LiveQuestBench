"""Snapshot projection preserves evaluator evidence without retaining setup history."""

import json
import os

import pytest

from game.veloren.evaluators.deaths import death_snapshot
from game.veloren.runtime.journal import snapshot_binding, snapshot_rows


def journal_rows():
    binding = {"uid": 73, "server_entity": "player-generation", "health": 100, "dead": False}
    values = [
        ("opened", {"run_id": "game", "nonce": "process"}),
        ("combat_entity_bindings", {"bindings": [binding]}),
        ("rtsim_population", {"unused": "setup"}),
        ("health_effect_applied", {"unused": "before admission"}),
        ("combat_entity_bindings", {"bindings": [{**binding, "equipment": {"sword": "new"}}]}),
        ("health_effect_applied", {"unused": "during play"}),
        ("native_entity_death", {"uid": 73, "entity": "player-generation"}),
        ("rtsim_population", {"unused": "terminal"}),
    ]
    return [
        {"schema": "rpg-native-oracle", "version": "1.1", "private": True,
         "sequence": index, "event": event, "data": data}
        for index, (event, data) in enumerate(values)
    ]


def write_rows(path, rows):
    path.write_bytes(b"".join(json.dumps(row).encode() + b"\n" for row in rows))


def test_opening_retains_exact_death_binding_and_boundary(tmp_path):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    projected = snapshot_rows(path, "game")
    assert [row["sequence"] for row in projected] == [0, 4, 7]
    assert death_snapshot(projected, {"uid": 73}) == death_snapshot(rows, {"uid": 73})


@pytest.mark.parametrize("encounters", [False, True])
def test_terminal_preserves_deaths_and_encounter_history(tmp_path, encounters):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    registry = death_snapshot(rows[:4], {"uid": 73})["registry"]
    projected = snapshot_rows(path, "game", after_sequence=3, encounters=encounters)
    assert death_snapshot(projected, {"uid": 73}, registry) == death_snapshot(rows, {"uid": 73}, registry)
    assert [row["sequence"] for row in projected] == ([0, 4, 5, 6, 7] if encounters else [0, 4, 6, 7])
    if encounters:
        events = {"combat_entity_bindings", "health_effect_applied", "native_entity_death"}
        assert [row for row in projected if row["sequence"] > 3 and row["event"] in events] == [
            row for row in rows if row["sequence"] > 3 and row["event"] in events
        ]


@pytest.mark.parametrize("after_sequence", [None, 3])
def test_contracts_preserve_complete_helper_history(tmp_path, after_sequence):
    rows = journal_rows()
    for index, event in enumerate((
        "loaded_actor_bindings", "quest_states", "quest_settlement", "quest_reward_created",
        "dialogue_sender_removal", "dialogue_item_transfer", "quest_reward_delivery_rejected",
    ), 1):
        rows[index]["event"] = event
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    assert snapshot_rows(path, "game", after_sequence=after_sequence, contracts=True) == rows


@pytest.mark.parametrize("field,value", [
    ("schema", "wrong"), ("version", "1.0"), ("private", False), ("sequence", 99),
    ("event", "opened"),
])
def test_discarded_rows_are_still_validated(tmp_path, field, value):
    rows = journal_rows()
    rows[2][field] = value
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    with pytest.raises(ValueError):
        snapshot_rows(path, "game")


def test_partial_last_line_is_not_a_complete_event(tmp_path):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    with path.open("ab") as stream:
        stream.write(b'{"unfinished":')
    assert snapshot_rows(path, "game")[-1] == rows[-1]
    with pytest.raises(ValueError, match="run mismatch"):
        snapshot_rows(path, "different-run")
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="run mismatch"):
        snapshot_rows(path, "game")


def test_snapshot_does_not_chase_concurrent_appends(tmp_path, monkeypatch):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    original_stat = os.fstat
    appended = {**rows[-1], "sequence": len(rows)}

    def stat_then_append(fd):
        boundary = original_stat(fd)
        with path.open("ab") as stream:
            stream.write(json.dumps(appended).encode() + b"\n")
        return boundary

    monkeypatch.setattr(os, "fstat", stat_then_append)
    assert snapshot_rows(path, "game")[-1] == rows[-1]
    monkeypatch.setattr(os, "fstat", original_stat)
    assert snapshot_rows(path, "game")[-1] == appended


@pytest.mark.parametrize("after_sequence", [None, 3])
def test_prevalidated_setup_prefix_preserves_native_snapshot_evidence(tmp_path, after_sequence):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows[:4])
    prefix = {}
    snapshot_rows(path, "game", prepare_prefix=prefix)
    with path.open("ab") as stream:
        stream.write(b"".join(json.dumps(row).encode() + b"\n" for row in rows[4:]))
    options = dict(after_sequence=after_sequence, encounters=True, equipment_uid=73)
    assert snapshot_rows(path, "game", prefix=prefix, **options) == snapshot_rows(path, "game", **options)
    rows[-1]["sequence"] += 1
    write_rows(path, rows)
    with pytest.raises(ValueError, match="sequence mismatch"):
        snapshot_rows(path, "game", prefix=prefix, **options)


def test_prefix_rejects_replaced_truncated_or_incompatible_journal(tmp_path):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    prefix = {}
    snapshot_rows(path, "game", prepare_prefix=prefix)
    for options in ({"contracts": True}, {"after_sequence": 1}):
        with pytest.raises(ValueError, match="does not cover"):
            snapshot_rows(path, "game", prefix=prefix, **options)
    with pytest.raises(ValueError, match="does not cover"):
        snapshot_rows(path, "another-run", prefix=prefix)
    write_rows(path, rows[:2])
    with pytest.raises(ValueError, match="truncated"):
        snapshot_rows(path, "game", prefix=prefix)
    replacement = tmp_path / "replacement.ndjson"
    write_rows(replacement, rows)
    replacement.replace(path)
    with pytest.raises(ValueError, match="replaced"):
        snapshot_rows(path, "game", prefix=prefix)


@pytest.mark.parametrize("prepare_pickups", [False, True])
def test_prefix_preserves_original_pickup_lineage_across_readiness(tmp_path, prepare_pickups):
    rows = journal_rows()
    events = ("item_drop_created", "item_drop_merged_on_creation", "item_drop_merged",
              "item_pickup_applied", "item_drop_expired")
    for row, event in zip(rows[2:], events):
        row.update(event=event, data={"source": "original"})
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows[:4])
    prefix = {}
    snapshot_rows(path, "game", pickups=prepare_pickups, prepare_prefix=prefix)
    with path.open("ab") as stream:
        stream.write(b"".join(json.dumps(row).encode() + b"\n" for row in rows[4:]))
    projected = snapshot_rows(path, "game", prefix=prefix, pickups=True, after_sequence=3)
    assert projected == snapshot_rows(path, "game", pickups=True, after_sequence=3)
    assert [row["event"] for row in projected if row["event"] in events] == list(events)


def test_prefix_resumes_at_last_complete_row_not_partial_tail(tmp_path):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows[:4])
    encoded = json.dumps(rows[4]).encode() + b"\n"
    with path.open("ab") as stream:
        stream.write(encoded[:20])
    prefix = {}
    snapshot_rows(path, "game", prepare_prefix=prefix)
    with path.open("ab") as stream:
        stream.write(encoded[20:])
    assert snapshot_rows(path, "game", prefix=prefix) == snapshot_rows(path, "game")


def test_setup_binding_uses_latest_suffix_not_stale_prepared_entity(tmp_path):
    rows = journal_rows()
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows[:4])
    prefix = {}
    snapshot_rows(path, "game", prepare_prefix=prefix)
    latest = {**rows[4], "data": {"bindings": [
        {"uid": 73, "server_entity": "new-generation", "health": 90, "dead": False},
    ]}}
    with path.open("ab") as stream:
        stream.write(json.dumps(latest).encode() + b"\n")
    assert snapshot_binding(path, "game", 73, prefix=prefix) == latest["data"]["bindings"][0]
    assert snapshot_binding(path, "game", 73, prefix=prefix) == snapshot_binding(path, "game", 73)
    for bindings in ([], latest["data"]["bindings"] * 2):
        with path.open("ab") as stream:
            stream.write(json.dumps({**latest, "sequence": 5 if not bindings else 6,
                                     "data": {"bindings": bindings}}).encode() + b"\n")
        if bindings:
            with pytest.raises(ValueError, match="ambiguous"):
                snapshot_binding(path, "game", 73, prefix=prefix)
        else:
            assert snapshot_binding(path, "game", 73, prefix=prefix) is None


@pytest.mark.parametrize("contracts", [False, True])
def test_repeated_world_bindings_keep_equipment_changes_and_exact_latest_state(tmp_path, contracts):
    rows = journal_rows()
    player = {"uid": 73, "server_entity": "player-generation", "health": 100, "dead": False,
              "equipment": {"chest": "old"}}
    other = {**player, "uid": 99, "server_entity": "other-generation"}
    rows = [rows[0], {**rows[1], "data": {"bindings": [player, other]}}]
    for index in range(2, 102):
        chest = "new" if 25 <= index < 75 else "old"
        rows.append({
            **rows[1], "sequence": index, "data": {"bindings": [
                {**player, "health": 100 - index / 10, "equipment": {"chest": chest}},
                {**other, "health": index, "equipment": {"chest": f"other-{index}"}},
            ]},
        })
    path = tmp_path / "journal.ndjson"
    write_rows(path, rows)
    projected = snapshot_rows(path, "game", after_sequence=1, encounters=True, contracts=contracts,
                              equipment_uid=73)
    assert [row["sequence"] for row in projected] == ([0, 1, 25, 75, 101] if contracts else [0, 25, 75, 101])
    assert projected[-1] == rows[-1]
    transitions = [row for row in projected if row["sequence"] in (25, 75)]
    assert [row["data"]["bindings"] for row in transitions] == [
        [rows[index]["data"]["bindings"][0]] for index in (25, 75)
    ]
    registry = death_snapshot(rows[:2], {"uid": 73})["registry"]
    assert death_snapshot(projected, {"uid": 73}, registry) == death_snapshot(rows, {"uid": 73}, registry)
