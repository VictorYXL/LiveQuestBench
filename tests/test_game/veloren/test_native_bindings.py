import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from game.veloren.native_bindings import NativeBindingCursor, combat_binding


def event(sequence, kind, data):
    return json.dumps({"schema": "rpg-native-oracle", "version": "1.1",
                       "private": True, "sequence": sequence, "event": kind,
                       "data": data}).encode() + b"\n"


def test_incremental_bindings_wait_for_complete_append_and_replace_old_lifecycle(tmp_path):
    path = tmp_path / "oracle.ndjson"
    path.touch()
    cursor = NativeBindingCursor(path, "market")
    assert cursor.poll() == []
    initial = event(0, "opened", {"run_id": "market"}) + event(
        1, "loaded_actor_bindings", {"bindings": [{"rtsim_uid": 1798, "uid": 166}]})
    path.write_bytes(initial)
    assert cursor.poll() == [{"rtsim_uid": 1798, "uid": 166}]
    replacement = event(2, "loaded_actor_bindings",
                        {"bindings": [{"rtsim_uid": 1798, "uid": 171}]})
    with path.open("ab") as stream:
        stream.write(replacement[:-1])
    assert cursor.poll() == [{"rtsim_uid": 1798, "uid": 166}]
    assert cursor.offset == len(initial)
    with path.open("ab") as stream:
        stream.write(b"\n")
    assert cursor.poll() == [{"rtsim_uid": 1798, "uid": 171}]
    assert cursor.poll() == [{"rtsim_uid": 1798, "uid": 171}]
    assert cursor.sequence == 3
    with path.open("ab") as stream:
        stream.write(event(3, "loaded_actor_bindings", {"bindings": []}))
    assert cursor.poll() == []


@pytest.mark.parametrize(("rows", "error"), [
    (event(0, "opened", {"run_id": "another-run"}), "run mismatch"),
    (event(0, "loaded_actor_bindings", {"bindings": []}), "run mismatch"),
    (event(0, "opened", {"run_id": "market"}) + event(2, "snapshot", {}), "sequence"),
    (event(0, "opened", {"run_id": "market"}) + event(1, "opened", {"run_id": "market"}),
     "Multiple native processes"),
])
def test_incremental_bindings_keep_native_run_and_sequence_validation(tmp_path, rows, error):
    path = tmp_path / "oracle.ndjson"
    path.write_bytes(rows)
    with pytest.raises(ValueError, match=error):
        NativeBindingCursor(path, "market").poll()


def test_incremental_bindings_reject_truncation_after_consumed_records(tmp_path):
    path = tmp_path / "oracle.ndjson"
    path.write_bytes(event(0, "opened", {"run_id": "market"}))
    cursor = NativeBindingCursor(path, "market")
    cursor.poll()
    path.write_bytes(b"")
    with pytest.raises(ValueError, match="truncated"):
        cursor.poll()


def test_combat_binding_reuses_cursor_and_reads_new_injury_without_stale_uid(tmp_path):
    path = tmp_path / "private-native-oracle.ndjson"
    path.write_bytes(event(0, "opened", {"run_id": tmp_path.name}) + event(
        1, "combat_entity_bindings", {"bindings": [{"uid": 7, "health": 30}]}) + event(
        2, "loaded_actor_bindings", {"bindings": [{"uid": 7, "health": 999}]}))
    actor = SimpleNamespace(out=tmp_path)
    assert asyncio.run(combat_binding(actor, 7))["health"] == 30
    cursor = actor._native_combat_binding_cursor
    with path.open("ab") as stream:
        stream.write(event(3, "combat_entity_bindings", {"bindings": [{"uid": 7, "health": 18}]}))
    assert asyncio.run(combat_binding(actor, 7))["health"] == 18
    assert actor._native_combat_binding_cursor is cursor
    with path.open("ab") as stream:
        stream.write(event(4, "combat_entity_bindings", {"bindings": []}))
    with pytest.raises(RuntimeError, match="binding unavailable"):
        asyncio.run(combat_binding(actor, 7, timeout=.01))


def test_combat_binding_rejects_ambiguous_latest_snapshot(tmp_path):
    path = tmp_path / "private-native-oracle.ndjson"
    path.write_bytes(event(0, "opened", {"run_id": tmp_path.name}) + event(
        1, "combat_entity_bindings", {"bindings": [{"uid": 7}, {"uid": 7}]}))
    with pytest.raises(ValueError, match="ambiguous"):
        asyncio.run(combat_binding(SimpleNamespace(out=tmp_path), 7))


def test_incremental_bindings_reject_equal_length_rotation(tmp_path):
    path = tmp_path / "oracle.ndjson"
    payload = event(0, "opened", {"run_id": "market"})
    path.write_bytes(payload)
    cursor = NativeBindingCursor(path, "market")
    cursor.poll()
    replacement = tmp_path / "replacement.ndjson"
    replacement.write_bytes(payload)
    replacement.replace(path)
    with pytest.raises(ValueError, match="replaced"):
        cursor.poll()


@pytest.mark.parametrize("truncate", [False, True])
def test_incremental_bindings_use_descriptor_boundary(tmp_path, monkeypatch, truncate):
    path = tmp_path / "oracle.ndjson"
    initial = event(0, "opened", {"run_id": "market"})
    suffix = event(1, "loaded_actor_bindings", {"bindings": [{"uid": 7}]})
    path.write_bytes(initial)
    cursor = NativeBindingCursor(path, "market")
    cursor.poll()
    path.write_bytes(initial + suffix)
    appended = event(2, "loaded_actor_bindings", {"bindings": []})
    original_stat = os.fstat

    def stat_then_change(fd):
        boundary = original_stat(fd)
        if truncate:
            path.write_bytes(initial + suffix[:len(suffix) // 2])
        else:
            with path.open("ab") as stream:
                stream.write(appended)
        return boundary

    monkeypatch.setattr(os, "fstat", stat_then_change)
    if truncate:
        with pytest.raises(ValueError, match="truncated during poll"):
            cursor.poll()
    else:
        assert cursor.poll() == [{"uid": 7}]
        assert cursor.offset == len(initial + suffix)
        monkeypatch.setattr(os, "fstat", original_stat)
        assert cursor.poll() == []
