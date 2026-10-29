import json

import pytest

from game.veloren.native_bindings import NativeBindingCursor


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
