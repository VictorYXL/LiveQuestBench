"""Offline admission and endpoint scoring for the frozen I05/R02 task pairs."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.binding import create_binding


ROOT = Path(__file__).resolve().parents[3]
TASKS = ("landmark_resource_survey", "staggered_expiring_supplies")


@pytest.fixture(params=[
    (task, track) for task in TASKS for track in ("structured_tools", "visual_motor")
], ids=lambda pair: "-".join(pair))
def qualified_task(request):
    task, track = request.param
    return load_task(ROOT / "config/veloren/tasks" / track / f"{task}.yaml")


def bind(task, output_dir, *, parameters=None):
    return create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters if parameters is None else parameters,
        tools=task.tools, output_dir=output_dir, headless=True, recording=False, recording_fps=10,
    )


def snapshots(task):
    parameters = task.evaluator_parameters
    initial = {
        "session_id": "qualified-task-test", "self_identity": {"uid": 7}, "tick": 10,
        "survival": {"health": {"current": 100}},
        "position": task.fixture["player_state"]["position"],
        "velocity": [0, 0, 0], "on_ground": True, "inventory": {"items": []},
    }
    if task.evaluator == "harvest":
        from tests.test_game.veloren.test_harvest import snapshots as harvest_snapshots

        harvest_initial, _ = harvest_snapshots()
        evidence = harvest_initial["private_harvest_evidence"]
        registry = evidence["registry"]
        registry["session_id"] = registry["preparation"]["session_id"] = initial["session_id"]
        for site, point in zip(registry["preparation"]["sites"], parameters["source_cells"], strict=True):
            site["position"] = point
            site["cell"]["position"] = point
        evidence["cells"] = [
            {"position": site["position"], "cell": deepcopy(site["cell"])}
            for site in registry["preparation"]["sites"]
        ]
        initial["private_harvest_evidence"] = evidence
        holdings = [{"item": row["item"], "amount": row["min_count"]} for row in parameters["inventory"]]
    else:
        sources = [
            {"uid": 20 + index, "entity": f"original-{index}", **row,
             "created_sequence": index + 1, "spawned_at": 0, "lifetime_seconds": 300}
            for index, row in enumerate(parameters["supplies"])
        ]
        initial["private_pickup_evidence"] = {
            "schema": "livequest-source-pickups/1", "through_sequence": 10, "events": [],
            "registry": {"run_id": "test-run", "nonce": "native-process", "opening_sequence": 10,
                         "actor": {"uid": 7, "server_entity": "player"}, "sources": sources},
        }
        holdings = parameters["supplies"]
    final = deepcopy(initial)
    final.update(position=parameters["position"]["target"], tick=40)
    final["survival"]["health"]["current"] = .390625
    final["inventory"]["items"] = [
        {"item": {"id": {"Simple": row["item"]}, "amount": row["amount"]}} for row in holdings
    ]
    if task.evaluator == "harvest":
        evidence = final["private_harvest_evidence"]
        evidence["phase"] = "terminal"
        for cell in evidence["cells"]:
            cell["cell"]["sprite"] = "Empty"
            cell["query_binding"] = {
                "session_id": final["session_id"], "self_identity": final["self_identity"],
                "tick": 41, "actor_position": final["position"],
            }
    else:
        evidence = final["private_pickup_evidence"]
        evidence["events"] = [
            {"schema": "rpg-native-oracle", "version": "1.1", "private": True,
             "sequence": 11 + index, "event": "item_pickup_applied",
             "data": {"item": {"Simple": source["item"]}, "server_time": 30,
                      "source_uid": source["uid"], "source_entity": source["entity"],
                      "amount": source["amount"], "source_amount_before": source["amount"],
                      "source_amount_after": 0, "collector_uid": 7, "collector_entity": "player"}}
            for index, source in enumerate(evidence["registry"]["sources"])
        ]
        evidence["through_sequence"] = evidence["events"][-1]["sequence"]
    return initial, final


def endpoints(root, initial, final):
    paths = []
    for name, phase, row, start in (("before", "ready", initial, 1), ("after", "ended", final, 3)):
        path = root / name
        path.mkdir(exist_ok=True)
        data = json.dumps(row).encode()
        (path / "observation.json").write_bytes(data)
        (path / "_livequest_snapshot.json").write_text(json.dumps({
            "schema": "veloren-endpoint", "phase": phase, "session_id": row["session_id"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "capture_started_at_ns": start, "captured_at_ns": start + 1,
        }))
        paths.append(path)
    return paths


def test_qualified_pair_admits_public_controls_and_scores(qualified_task, tmp_path):
    binding = bind(qualified_task, tmp_path / "game")
    binding.game.phase = "ready"
    _, tools = binding.controls()
    names = {tool.name for tool in tools}
    if qualified_task.task_type == "structured_tool":
        assert names == set(qualified_task.tools)
    else:
        assert not names & {"CollectTool", "InspectTerrainTool", "PickupTool"}
    initial, final = snapshots(qualified_task)
    assert not binding.evaluate(*endpoints(tmp_path, initial, initial))["success"]
    assert binding.evaluate(*endpoints(tmp_path, initial, final))["success"]


@pytest.mark.parametrize("failure", ["source", "inventory", "dead", "position", "airborne", "moving"])
def test_qualified_scorer_requires_source_and_all_public_endpoint_goals(qualified_task, tmp_path, failure):
    binding = bind(qualified_task, tmp_path / "game")
    initial, final = snapshots(qualified_task)
    if failure == "source":
        if qualified_task.evaluator == "harvest":
            final["private_harvest_evidence"]["cells"][0]["cell"]["sprite"] = "Mushroom"
        else:
            final["private_pickup_evidence"]["events"] = []
    elif failure == "inventory":
        final["inventory"]["items"][0]["item"]["amount"] -= 1
    elif failure == "dead":
        final["survival"]["health"]["current"] = 0
    elif failure == "position":
        final["position"] = qualified_task.fixture["player_state"]["position"]
        final["position"] = [final["position"][0] + 100, *final["position"][1:]]
    elif failure == "airborne":
        final["on_ground"] = False
    else:
        final["velocity"] = [1, 0, 0]
    assert not binding.evaluate(*endpoints(tmp_path, initial, final))["success"]


def test_qualified_admission_rejects_scored_sources_not_in_fixture(qualified_task, tmp_path):
    parameters = deepcopy(qualified_task.evaluator_parameters)
    if qualified_task.evaluator == "harvest":
        parameters["source_cells"][0][0] += 1
        message = "declared native mushroom cells"
    else:
        parameters["supplies"][0]["amount"] += 1
        message = "matching native fixture sources"
    with pytest.raises(ValueError, match=message):
        bind(qualified_task, tmp_path / "game", parameters=parameters)
