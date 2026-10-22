"""Consequential endpoint checks: exact thresholds, evidence tampering and identity."""

import hashlib
import json
from pathlib import Path

import pytest

from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory


def test_endpoint_thresholds_and_integrity(tmp_path: Path) -> None:
    for name, phase, position, amount, health, timestamp in (
        ("before", "ready", [0, 0, 10], 1, 40, 1),
        ("after", "ended", [3, 4, 100], 3, 60, 3),
    ):
        path = tmp_path / name
        path.mkdir()
        data = json.dumps({"session_id": "same", "self_identity": {"uid": 1}, "position": position,
                           "inventory": {"items": [{"item": {"id": {"Simple": "apple"}, "amount": amount}}]},
                           "survival": {"health": {"current": health}}}).encode()
        (path / "observation.json").write_bytes(data)
        (path / "_livequest_snapshot.json").write_text(json.dumps({
            "schema": "veloren-endpoint-v1", "phase": phase, "session_id": "same",
            "capture_started_at_ns": timestamp, "captured_at_ns": timestamp + 1,
            "sha256": hashlib.sha256(data).hexdigest(),
        }))
    before, after = tmp_path / "before", tmp_path / "after"
    assert evaluate_displacement(before, after, min_distance=5)["success"]
    assert not evaluate_displacement(before, after, min_distance=5.01)["success"]
    assert evaluate_health(before, after, min_health=60, min_delta=20)["success"]
    assert not evaluate_health(before, after, min_health=60, min_delta=21)["success"]
    assert evaluate_inventory(before, after, item="apple", min_count=3, min_delta=2)["success"]
    assert not evaluate_inventory(before, after, item="apple", min_count=3, min_delta=3)["success"]
    with pytest.raises(ValueError):
        evaluate_displacement(before, after, min_distance=float("nan"))
    (after / "observation.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        evaluate_displacement(before, after)
