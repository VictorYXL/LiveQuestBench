"""Consequential endpoint checks: exact thresholds, evidence tampering and identity."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory
from game.veloren.evaluators.endpoints import known_recipes, state_checks, validate_state


@pytest.mark.parametrize("book", [
    {"total": 2, "omitted": 1, "items": [{"recipe": "a"}]},
    {"total": 2, "omitted": 0, "items": [{"recipe": "a"}]},
    {"total": 2, "omitted": 0, "items": [{"recipe": "a"}, {"recipe": "a"}]},
    {"total": True, "omitted": 0, "items": [{"recipe": "a"}]},
    {"items": [{"recipe": "a"}]},
])
def test_recipe_checks_reject_incomplete_or_inconsistent_evidence(book):
    with pytest.raises(ValueError, match="recipe"):
        known_recipes({"known_recipes": book})


def test_state_checks_require_simultaneous_endpoint_conditions():
    row = {
        "survival": {"health": {"current": 50}},
        "inventory": {"items": [{"item": {"id": {"Simple": "apple"}, "amount": 2}}],
                      "equipment": {"chest": {"id": {"Simple": "shirt"}}}},
        "known_recipes": {"total": 1, "omitted": 0, "items": [{"recipe": "a"}]},
        "position": [3, 4, 10], "velocity": [0, 0, 0], "on_ground": True,
    }
    requirements = {
        "inventory": [{"item": "apple", "min_count": 2, "max_count": 2, "min_delta": 0}],
        "equipment": {"chest": "shirt"}, "recipes": ["a"], "min_health": 50,
        "position": {"target": [0, 0, 10], "horizontal_tolerance": 5,
                     "vertical_tolerance": 0, "max_speed": 0},
    }
    validate_state(**requirements)
    assert known_recipes(row) == {"a"}  # Native known-recipe rows do not carry character_known.
    assert state_checks(row, row, **requirements)["success"]
    for key, value in (
        ("survival", {"health": {"current": 49}}),
        ("inventory", {**row["inventory"], "equipment": {"chest": None}}),
        ("known_recipes", {"total": 0, "omitted": 0, "items": []}),
        ("position", [3, 4, 10.01]), ("velocity", [.01, 0, 0]), ("on_ground", False),
    ):
        final = deepcopy(row)
        final[key] = value
        assert not state_checks(row, final, **requirements)["success"]


def test_truncated_recipe_book_can_only_prove_explicit_entries():
    row = {"known_recipes": {"total": 2, "omitted": 1, "items": [{"recipe": "a"}]}}
    assert known_recipes(row, required=["a"]) == {"a"}
    with pytest.raises(ValueError, match="Truncated"):
        known_recipes(row, required=["b"])


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
    assert evaluate_inventory(before, after, item="apple", min_delta=2)["success"]
    assert evaluate_inventory(before, after, item="absent", min_delta=0)["success"]
    assert evaluate_health(before, after, min_delta=20)["success"]
    for kwargs in ({}, {"min_count": True}, {"min_delta": -1}):
        with pytest.raises(ValueError):
            evaluate_inventory(before, after, item="apple", **kwargs)
    for kwargs in ({}, {"min_health": True}, {"min_delta": float("nan")}):
        with pytest.raises(ValueError):
            evaluate_health(before, after, **kwargs)
    row = json.loads((after / "observation.json").read_text())
    row["inventory"]["items"][0]["item"]["amount"] = 0
    row["survival"]["health"]["current"] = 20
    data = json.dumps(row).encode()
    (after / "observation.json").write_bytes(data)
    meta = json.loads((after / "_livequest_snapshot.json").read_text())
    meta["sha256"] = hashlib.sha256(data).hexdigest()
    (after / "_livequest_snapshot.json").write_text(json.dumps(meta))
    assert evaluate_inventory(before, after, item="apple", min_count=0)["success"]
    assert not evaluate_inventory(before, after, item="apple", min_count=0, min_delta=0)["success"]
    assert evaluate_health(before, after, min_health=20)["success"]
    assert not evaluate_health(before, after, min_health=20, min_delta=0)["success"]
    assert evaluate_health(before, after, min_delta=-20)["success"]
    with pytest.raises(ValueError):
        evaluate_displacement(before, after, min_distance=float("nan"))
    (after / "observation.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        evaluate_displacement(before, after)
