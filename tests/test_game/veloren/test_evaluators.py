"""Consequential endpoint checks: exact thresholds, evidence tampering and identity."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from game.veloren.evaluators.endpoints import evaluate_displacement, evaluate_health, evaluate_inventory
from game.veloren.evaluators.endpoints import known_recipes, state_checks, validate_state


def test_merchant_lookup_skips_native_entities_without_names():
    from game.veloren.settlement import nearby_merchants

    merchant = {"name_text": "Wesab (Merchant)", "distance": 3}
    assert nearby_merchants({"nearby_entities": [
        {"name_text": None, "distance": 1}, merchant, {"name_text": "Other (Merchant)", "distance": 5},
    ]}) == [merchant]


def test_skill_goal_requires_learned_native_skill_and_current_eligible_slot():
    row = {
        "survival": {"health": {"current": 100}},
        "skill_tree": {"groups": [{"group": {"Weapon": "Sword"},
                                  "skills": [{"skill": {"Sword": "DefensiveRiposte"}, "learned_level": None}]}]},
        "auxiliary_abilities": {"active_set": ["Empty"] * 5, "available": []},
        "inventory": {"equipment": {"active_mainhand": {"id": {"Simple": "starter_sword"}}}},
    }
    goal = {"sword_skills": ["DefensiveRiposte"],
            "auxiliary_ability": {"slot": 0, "mainhand_index": 10},
            "equipment": {"active_mainhand": "starter_sword"}}
    validate_state(**goal)
    assert not state_checks(row, row, **goal)["success"]
    row["skill_tree"]["groups"][0]["skills"][0]["learned_level"] = 1
    row["auxiliary_abilities"]["active_set"][0] = {"MainWeapon": 10}
    assert not state_checks(row, row, **goal)["success"]
    row["auxiliary_abilities"]["available"] = [{"MainWeapon": 10}]
    assert state_checks(row, row, **goal)["success"]
    row["inventory"]["equipment"]["active_mainhand"]["id"] = {"Simple": "hammer"}
    assert not state_checks(row, row, **goal)["success"]
    with pytest.raises(ValueError, match="missing or duplicated"):
        state_checks(row, row, sword_skills=["Unknown"])
    with pytest.raises(ValueError, match="slot"):
        validate_state(auxiliary_ability={"slot": True, "mainhand_index": 10})


def test_aged_supply_opening_requires_original_live_pickup_and_remaining_time():
    from game.veloren.fixture import verify_aged_supplies

    item = {"id": {"Simple": "cheese"}, "amount": 4}
    entity = {"uid": 7, "control_target": {"uid": 7, "lifecycle": "generation:1"}, "pickup": item}
    initialized = {
        "fixture": {"supplies": [{"pre_age_seconds": 210}]},
        "supplies": [{"uid": 7, "entity": entity, "item": "cheese", "amount": 4,
                      "player_target": deepcopy(entity["control_target"]),
                      "expiry_game_time_estimate": 300}],
    }
    row = {"nearby_entities": [deepcopy(entity)], "survival": {"buff_clock": {"now": 285}}}
    verify_aged_supplies(initialized, row)
    row["survival"]["buff_clock"]["now"] = 285.01
    with pytest.raises(RuntimeError, match="identity-matched"):
        verify_aged_supplies(initialized, row)
    row["survival"]["buff_clock"]["now"] = 220
    row["nearby_entities"][0]["control_target"]["lifecycle"] = "generation:2"
    with pytest.raises(RuntimeError, match="identity-matched"):
        verify_aged_supplies(initialized, row)


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


def test_alive_only_health_floor_accepts_native_fraction_but_preserves_legacy_default():
    row = {"survival": {"health": {"current": 0.390625, "dead": False}}}
    validate_state(min_health=0)
    assert state_checks(row, row, min_health=0)["success"]
    assert not state_checks(row, row)["success"]
    with pytest.raises(ValueError, match="nonnegative"):
        validate_state(min_health=-1)
    for survival in (
        {"health": {"current": 0, "dead": False}},
        {"health": {"current": -0.1, "dead": False}},
        {"health": {"current": 0.390625, "dead": True}},
        {"health": {"current": 0.390625, "dead": False}, "dead": True},
    ):
        final = {"survival": survival}
        assert not state_checks(row, final, min_health=0)["success"]


@pytest.mark.parametrize("mode", ["structured_tools", "visual_motor"])
def test_glide_return_accepts_both_sides_of_the_visible_arch(mode):
    from benchmark.config import load_task

    root = Path(__file__).resolve().parents[3]
    task = load_task(root / f"tests/fixtures/learning/config/veloren/tasks/{mode}/glide_route_transfer.yaml")
    pillars = [block["origin"] for block in task.fixture["blocks"] if block["size"] == [1, 1, 3]]
    left, right = pillars
    center = [(left[0] + right[0]) / 2 + .5, (left[1] + right[1]) / 2 + .5, left[2]]
    row = {"survival": {"health": {"current": 100}},
           "velocity": [0, 0, 0], "on_ground": True}
    goal = task.evaluator_parameters["position"]
    for offset in (-1, 0, 1):
        row["position"] = [center[0] + offset, *center[1:]]
        assert state_checks(row, row, position=goal)["success"], row["position"]
    row["position"] = [center[0] - goal["horizontal_tolerance"] - 1, *center[1:]]
    assert not state_checks(row, row, position=goal)["success"]


def test_truncated_recipe_book_can_only_prove_explicit_entries():
    row = {"known_recipes": {"total": 2, "omitted": 1, "items": [{"recipe": "a"}]}}
    assert known_recipes(row, required=["a"]) == {"a"}
    with pytest.raises(ValueError, match="Truncated"):
        known_recipes(row, required=["b"])
    row["private_recipe_evidence"] = {"b": {"items": [{"recipe": "b", "character_known": False}]}}
    assert known_recipes(row, required=["b"]) == {"a"}


def test_motion_and_wielding_require_native_effects_and_matching_identity():
    initial = {
        "session_id": "same", "self_identity": {"uid": 7}, "wielding": False,
        "survival": {"health": {"current": 100}},
        "private_motion_evidence": {"schema": "native-client-motion/1", "session_id": "same",
                                   "uid": 7, "samples": 10, "through_tick": 20,
                                   "jump_landings": 0, "roll_entries": 0},
    }
    final = deepcopy(initial)
    assert not state_checks(initial, final, wielding=True)["success"]
    assert not state_checks(initial, final, motion={"jump_landings": 1})["success"]
    final["wielding"] = True
    final["private_motion_evidence"].update(samples=30, through_tick=40, jump_landings=1, roll_entries=1)
    assert state_checks(initial, final, wielding=True, motion={"jump_landings": 1, "roll_entries": 1})["success"]
    for field, value in (("uid", 8), ("session_id", "other"), ("samples", 9), ("jump_landings", True)):
        changed = deepcopy(final)
        changed["private_motion_evidence"][field] = value
        with pytest.raises(ValueError):
            state_checks(initial, changed, motion={"jump_landings": 1})
    for params in ({"wielding": 1}, {"motion": {"jump": 1}}, {"motion": {"roll_entries": 0}}):
        with pytest.raises(ValueError):
            validate_state(**params)


def test_glide_landing_requires_new_flight_distance_and_correct_landing():
    from game.veloren.structured_tools.interface import EXPEDITION_TOOLS, validate_tool

    assert "GlideTool" not in EXPEDITION_TOOLS
    assert validate_tool("GlideTool", {"enabled": True}) == ("glide", {"enabled": True})
    with pytest.raises(ValueError):
        validate_tool("GlideTool", {"enabled": 1})
    initial = {
        "session_id": "same", "self_identity": {"uid": 7},
        "survival": {"health": {"current": 100}},
        "private_motion_evidence": {
            "schema": "native-client-motion/1", "session_id": "same", "uid": 7,
            "samples": 10, "through_tick": 20, "jump_landings": 0, "roll_entries": 0,
            "glide_schema": "native-client-glide/1", "glide_landings": [],
        },
    }
    goal = {"target": [0, 20, 0], "horizontal_tolerance": 2, "vertical_tolerance": .5, "min_distance": 6}
    validate_state(glide_landing=goal)
    final = deepcopy(initial)
    final["private_motion_evidence"].update(samples=100, through_tick=110)
    assert not state_checks(initial, final, glide_landing=goal)["success"]
    landed = {"position": [2, 20, .5], "glide_distance": 6}
    final["private_motion_evidence"]["glide_landings"] = [landed]
    assert state_checks(initial, final, glide_landing=goal)["success"]
    for changed in (
        {**landed, "position": [2.01, 20, .5]},
        {**landed, "position": [2, 20, .51]},
        {**landed, "glide_distance": 5.99},
    ):
        final["private_motion_evidence"]["glide_landings"] = [changed]
        assert not state_checks(initial, final, glide_landing=goal)["success"]
    initial["private_motion_evidence"]["glide_landings"] = [landed]
    final["private_motion_evidence"]["glide_landings"] = [landed]
    assert not state_checks(initial, final, glide_landing=goal)["success"]
    final["private_motion_evidence"]["glide_landings"] = []
    with pytest.raises(ValueError, match="history changed"):
        state_checks(initial, final, glide_landing=goal)


def test_glide_route_requires_distinct_new_landings_in_order():
    from game.veloren.evaluators.glide_route import glide_route_checks

    initial = {
        "session_id": "same", "self_identity": {"uid": 7},
        "survival": {"health": {"current": 100}},
        "private_motion_evidence": {
            "schema": "native-client-motion/1", "session_id": "same", "uid": 7,
            "samples": 10, "through_tick": 20, "jump_landings": 0, "roll_entries": 0,
            "glide_schema": "native-client-glide/1", "glide_landings": [],
        },
    }
    final = deepcopy(initial)
    final.update(position=[0, 0, 0], velocity=[0, 0, 0], on_ground=True)
    final["private_motion_evidence"].update(samples=100, through_tick=110)
    goals = [{"target": [x, 0, 0], "horizontal_tolerance": 2, "vertical_tolerance": 1,
              "min_distance": 6} for x in (10, 20)]
    position = {"target": [0, 0, 0], "horizontal_tolerance": 2,
                "vertical_tolerance": 1, "max_speed": .1}
    events = [{"position": goal["target"], "glide_distance": 7} for goal in goals]
    for entries, passed in ((events, True), (events[::-1], False),
                            ([events[0]], False), ([events[0], {**events[1], "glide_distance": 5}], False)):
        final["private_motion_evidence"]["glide_landings"] = entries
        assert glide_route_checks(initial, final, landings=goals, position=position)["success"] is passed
    missed = {"position": [100, 100, 0], "glide_distance": 7}
    for entries, completed in (([missed, events[0], missed], 1),
                               ([missed, events[0], missed, events[0], events[1]], 2)):
        final["private_motion_evidence"]["glide_landings"] = entries
        result = glide_route_checks(initial, final, landings=goals, position=position)
        progress = next(row for row in result["checks"] if row["kind"] == "ordered_glide_landings")
        assert progress["completed"] == completed
        assert result["success"] is (completed == 2)


def test_marker_arrival_requires_new_native_directions_not_a_personal_marker():
    goal = {"label_key": "hud-map-workshop", "horizontal_tolerance": 2, "max_speed": .1}
    validate_state(marker_arrival=goal)
    initial = {"tick": 10, "dialogue_markers": [], "survival": {"health": {"current": 100}}}
    final = {**deepcopy(initial), "tick": 20, "position": [2, 20, 381],
             "velocity": [0, 0, 0], "on_ground": True,
             "personal_map_marker": {"x": 0, "y": 20}}
    assert not state_checks(initial, final, marker_arrival=goal)["success"]
    marker = {"schema_version": "1.0", "source": "validated_server_dialogue",
              "kind": "Marker", "received_client_tick": 15,
              "marker": {"label": {"Localized": {"key": "hud-map-workshop", "args": {}, "seed": 1}},
                         "wpos": {"x": 0, "y": 20}}}
    final["dialogue_markers"] = [marker]
    assert state_checks(initial, final, marker_arrival=goal)["success"]
    for field, value in (("position", [2.01, 20, 381]), ("on_ground", False), ("velocity", [.11, 0, 0])):
        changed = {**final, field: value}
        assert not state_checks(initial, changed, marker_arrival=goal)["success"]
    old = deepcopy(initial)
    old["dialogue_markers"] = [marker]
    assert not state_checks(old, final, marker_arrival=goal)["success"]
    wrong = deepcopy(final)
    wrong["dialogue_markers"][0]["source"] = "personal_map_marker"
    with pytest.raises(ValueError, match="evidence"):
        state_checks(initial, wrong, marker_arrival=goal)


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
            "schema": "veloren-endpoint", "phase": phase, "session_id": "same",
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
