import hashlib
import json

from game.veloren.runtime.records import write_authoring_detail, write_fixture_record


def test_readiness_does_not_serialize_bulk_authoring(tmp_path):
    initialized = {
        "construction": object(),
        "blocks": object(),
        "fixture": {"player_state": {"health": 100}},
        "encounters": [{"binding": {"uid": 12, "health": 110}}],
        "opening": {"position": [1, 2, 3]},
    }
    write_fixture_record(tmp_path, initialized, {"sha256": "world"})
    record = json.loads((tmp_path / "fixture.json").read_text())
    assert record["encounters"] == initialized["encounters"]
    assert record["opening"] == initialized["opening"]
    assert record["authoring_detail"]["phase"] == "deferred_until_native_cleanup"
    assert not (tmp_path / "fixture-authoring.json").exists()


def test_cleanup_preserves_full_authoring_with_verifiable_reference(tmp_path):
    initialized = {
        "construction": {"native_receipts": [{"effect_status": "applied"}]},
        "blocks": [{"position": [1, 2, 3], "receipt": {"native_sequence": 42}}],
        "fixture": {"player_state": {"health": 100}},
    }
    digest = write_authoring_detail(tmp_path, initialized)
    write_fixture_record(tmp_path, initialized, {"sha256": "world"}, digest)
    record = json.loads((tmp_path / "fixture.json").read_text())
    raw = (tmp_path / record["authoring_detail"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record["authoring_detail"]["sha256"]
    assert json.loads(raw) == {key: initialized[key] for key in ("construction", "blocks")}
    assert record["authoring_detail"]["phase"] == "written"
