import json

import pytest

from checks.minecraft_original_terminal_reconciliation import classify_formal, condition, public_trace


def test_condition_normalizes_serialized_tuples_but_preserves_mechanics():
    current = {"source": {"path": "new.yaml", "sha256": "same"},
               "fixture": {"world_path": "new-world", "difficulty": "easy"},
               "tools": ("MoveTool",)}
    archived = json.loads(json.dumps(current))
    archived["source"]["path"] = "old.yaml"
    archived["fixture"]["world_path"] = "old-world"
    assert condition(current) == condition(archived)
    archived["fixture"]["difficulty"] = "hard"
    assert condition(current) != condition(archived)
    assert current["source"]["path"] == "new.yaml"


def test_external_termination_is_not_model_failure():
    result = {"status": "running", "measurement": "unavailable", "task_outcome": "unknown"}
    assert classify_formal(result, {"finished_at": 123, "returncode": -15}, False) == (
        "interrupted_unavailable_not_a_model_failure")
    assert result["task_outcome"] == "unknown"
    assert classify_formal(result, {}, False) == "unresolved_measurement"


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_valid_measurements_are_preserved(outcome):
    result = {"status": "completed", "measurement": "valid", "task_outcome": outcome}
    assert classify_formal(result, {"finished_at": 123, "returncode": -15}, True) == (
        "recorded_valid_" + outcome)
    with pytest.raises(ValueError, match="terminal snapshot"):
        classify_formal(result, {}, False)


def trace_fixture(root):
    commands = root / "commands"
    commands.mkdir()
    (commands / "000.json").write_text(json.dumps({
        "commands": [{"name": "wait", "arguments": {"milliseconds": 1}}]}))
    (commands / "001.json").write_text('{"finish": true}')
    image = root / "frame-000-Player.png"
    image.write_bytes(b"archived screenshot")
    response = {
        "success": True, "elapsed_seconds": 1,
        "results": [{"operation": "wait", "started_at_ns": 10, "finished_at_ns": 20}],
        "images": {"Player": {"path": str(image), "captured_at_ns": 21}},
    }
    (root / "response-000.json").write_text(json.dumps(response))
    result = {"public_batches": 1, "controller_finished": True,
              "elapsed_seconds": 2, "time_limit_seconds": 3}
    return result, {"begin_acknowledged_at_ns": 5, "end_requested_at_ns": 30}, response


def test_trace_requires_same_episode_acknowledged_public_actions(tmp_path):
    result, boundaries, response = trace_fixture(tmp_path)
    assert public_trace(tmp_path, result, boundaries)["validated_batches"] == 1
    response["results"][0]["finished_at_ns"] = 31
    (tmp_path / "response-000.json").write_text(json.dumps(response))
    with pytest.raises(AssertionError):
        public_trace(tmp_path, result, boundaries)
    (tmp_path / "response-000.json").unlink()
    with pytest.raises(FileNotFoundError):
        public_trace(tmp_path, result, boundaries)


def test_trace_rejects_receipt_mismatch_and_over_budget(tmp_path):
    result, boundaries, response = trace_fixture(tmp_path)
    response["results"][0]["operation"] = "key_down"
    (tmp_path / "response-000.json").write_text(json.dumps(response))
    with pytest.raises(AssertionError):
        public_trace(tmp_path, result, boundaries)
    response["results"][0]["operation"] = "wait"
    (tmp_path / "response-000.json").write_text(json.dumps(response))
    result["elapsed_seconds"] = 4
    with pytest.raises(AssertionError):
        public_trace(tmp_path, result, boundaries)


def test_rejected_nonpublic_key_is_not_mistaken_for_executed_action(tmp_path):
    result, boundaries, response = trace_fixture(tmp_path)
    (tmp_path / "commands/000.json").write_text(json.dumps({
        "commands": [{"name": "key_down", "arguments": {"key": "f3"}}]}))
    response.update(success=False, error="Unsupported key", executed_commands=0)
    response.pop("results")
    (tmp_path / "response-000.json").write_text(json.dumps(response))
    trace = public_trace(tmp_path, result, boundaries)
    assert trace["admitted_batches"] == 0
    assert trace["rejected_before_execution"] == [
        {"index": 0, "error": "Unsupported key", "executed_commands": 0}]
    response["executed_commands"] = 1
    (tmp_path / "response-000.json").write_text(json.dumps(response))
    with pytest.raises(AssertionError):
        public_trace(tmp_path, result, boundaries)
