import asyncio
import hashlib
import json

import pytest

from agent_framework.llm_client.base_client import BaseLLMClient, LLMResponse, Message
from benchmark.archive import archive_episode, restore_episode, retire_originals, seal_episode, verify_archive
from benchmark.compact import CompactLog, read_records
from benchmark.results import EpisodeLog, write_json


def test_shared_history_roundtrip_and_literal_references(tmp_path):
    log = CompactLog(tmp_path)
    messages = [{"role": "user", "content": "a large unchanged observation " * 2000}]
    rows = []
    for index in range(12):
        row = {"messages": messages[:], "attempt": index,
               "native": {"messages": messages[:]},
               "collision": {"$lqb_ref": "not a real reference", "$lqb_literal": [1, None]},
               "escaped_unicode": "\ud800",
               "provider_data": {"output": ["opaque", {"tool_call_id": "call-1"}]}}
        rows.append(row)
        log.write("query", row)
        messages = [*messages, {"role": "assistant", "content": str(index)}]
    assert list(read_records(tmp_path / "query.compact.jsonl")) == rows
    full_bytes = sum(len(json.dumps(row).encode()) for row in rows)
    compact_bytes = sum(p.stat().st_size for p in tmp_path.rglob("*") if p.is_file())
    assert compact_bytes < full_bytes / 5
    obj = next((tmp_path / "objects").iterdir())
    obj.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="mismatch"):
        list(read_records(tmp_path / "query.compact.jsonl"))


def test_compact_retries_do_not_change_model_inputs(tmp_path):
    log = EpisodeLog(tmp_path, storage_profile="compact")
    image = b"\x89PNG\r\n\x1a\n" + b"frame" * 500
    message = Message("user", [{"type": "image", "data": image, "mime_type": "image/png"}])

    class Client(BaseLLMClient):
        calls = 0

        async def _request_impl(self, messages, **kwargs):
            assert messages[0] is message and messages[0].content[0]["data"] is image
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError()
            return LLMResponse(content="done", finish_reason="stop")

        async def close(self):
            pass

    client = Client(max_attempts=2, retry_backoff=0, on_request=log.request)
    client.on_query = log.query
    asyncio.run(client.chat([message]))
    rows = list(read_records(log.directory / "query.compact.jsonl"))
    assert [row["event"] for row in rows] == ["prompt", "error", "prompt", "response"]
    assert rows[0]["messages"] == rows[2]["messages"]
    assert log.accounting()["request_attempts"] == 2
    images = list((log.directory / "images").iterdir())
    assert len(images) == 1 and images[0].read_bytes() == image
    assert not list(log.directory.glob("*.log"))


def test_archive_roundtrip_and_corruption_preserve_originals(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(tmp_path / "results/result.json", {
        "status": "error", "finished_at_ns": 1,
        "errors": [{"stage": "execution", "type": "TimeoutError"}],
    })
    original = (b'{"event":"sample","data":"repetitive"}\n' * 2000) + b'{"partial":'
    raw = tmp_path / "native.jsonl"
    raw.write_bytes(original)
    with pytest.raises(FileNotFoundError):
        archive_episode(tmp_path)
    seal_episode(tmp_path)
    report = archive_episode(tmp_path)
    assert report["files"][0]["compressed_bytes"] < len(original) / 5
    assert raw.read_bytes() == original
    assert verify_archive(tmp_path) == report
    retire_originals(tmp_path)
    assert not raw.exists()
    restore_episode(tmp_path)
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest()
    (tmp_path / "native.jsonl.gz").write_bytes(b"bad gzip")
    with pytest.raises(OSError):
        verify_archive(tmp_path)
    assert raw.read_bytes() == original


def test_retirement_rejects_changed_source_before_deleting_any_file(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(tmp_path / "results/result.json", {
        "status": "completed", "finished_at_ns": 1, "errors": [],
    })
    first, second = tmp_path / "agent.jsonl", tmp_path / "native.jsonl"
    first.write_text("first\n")
    second.write_text("second\n")
    seal_episode(tmp_path)
    archive_episode(tmp_path)
    second.write_text("changed\n")
    with pytest.raises(ValueError, match="changed"):
        retire_originals(tmp_path)
    assert first.read_text() == "first\n" and second.read_text() == "changed\n"


def test_reject_cleanup_failure_and_partial_compact_record(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(tmp_path / "results/result.json", {
        "status": "error", "finished_at_ns": 1, "errors": [{"stage": "game_cleanup"}],
    })
    with pytest.raises(ValueError, match="cleanup"):
        seal_episode(tmp_path)
    path = tmp_path / "query.compact.jsonl"
    path.write_bytes(b'{"schema":')
    with pytest.raises(ValueError, match="Incomplete"):
        list(read_records(path))
    with pytest.raises(ValueError, match="requires"):
        EpisodeLog(tmp_path, storage_profile="compact", record_chat=False)


def test_interrupted_archive_keeps_original_and_rejects_retirement(tmp_path, monkeypatch):
    (tmp_path / "results").mkdir()
    write_json(tmp_path / "results/result.json", {
        "status": "cancelled", "finished_at_ns": 1, "errors": [],
    })
    raw = tmp_path / "native.jsonl"
    raw.write_bytes(b"original evidence\n")
    seal_episode(tmp_path)

    def interrupt(*args, **kwargs):
        raise OSError("simulated storage interruption")

    monkeypatch.setattr("benchmark.archive.shutil.copyfileobj", interrupt)
    with pytest.raises(OSError, match="interruption"):
        archive_episode(tmp_path)
    assert raw.read_bytes() == b"original evidence\n"
    with pytest.raises(ValueError, match="incomplete"):
        retire_originals(tmp_path)
