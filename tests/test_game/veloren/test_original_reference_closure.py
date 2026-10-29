import hashlib
import json

import pytest

from checks.veloren_original_reference_closure import CURRENT_LOAD_PAIR, load_archived_pair


def snapshots(root, *, schema="veloren-endpoint-v1", downed=False):
    paths = []
    for index, phase in enumerate(("ready", "ended")):
        path = root / phase
        path.mkdir()
        row = {
            "session_id": "original-native-session",
            "self_identity": {"uid": 12},
            "survival": {"health": {"current": 0.5, "dead": False}},
        }
        if downed is not None:
            row["survival"]["health"]["downed"] = downed
        raw = json.dumps(row).encode()
        (path / "observation.json").write_bytes(raw)
        (path / "_livequest_snapshot.json").write_text(json.dumps({
            "schema": schema, "phase": phase, "session_id": row["session_id"],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "capture_started_at_ns": index * 10, "captured_at_ns": index * 10 + 1,
        }))
        paths.append(path)
    return paths


def test_legacy_replay_preserves_original_bytes_and_production_schema(tmp_path):
    before, after = snapshots(tmp_path)
    original = {p: p.read_bytes() for directory in (before, after) for p in directory.iterdir()}
    first, last = load_archived_pair(before, after)
    assert first["survival"]["health"] == last["survival"]["health"]
    assert last["survival"]["health"]["current"] == 0.5
    assert all(p.read_bytes() == raw for p, raw in original.items())
    with pytest.raises(ValueError, match="Invalid endpoint"):
        CURRENT_LOAD_PAIR(before, after)


def test_replay_does_not_invent_missing_downed_flag(tmp_path):
    before, after = snapshots(tmp_path, downed=None)
    with pytest.raises(ValueError, match="explicit native health.downed"):
        load_archived_pair(before, after)


@pytest.mark.parametrize("schema", ["veloren-endpoint-v1", "veloren-endpoint"])
def test_replay_keeps_checksum_guard_for_both_schemas(tmp_path, schema):
    before, after = snapshots(tmp_path, schema=schema)
    with (after / "observation.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="checksum"):
        load_archived_pair(before, after)
