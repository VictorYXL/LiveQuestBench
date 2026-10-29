"""Reconcile archived original-task terminals without launching games or models.

Run from the evidence repository with the isolated source interpreter/import path:
python <worktree>/checks/minecraft_original_terminal_reconciliation.py
    --evidence-root <repository> --output <new-handoff.json>

The output is a recommendation, never a ledger update or a rewritten episode.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))

import nbtlib

from benchmark.config import load_task
from checks import minecraft_original_reference_closure as closure
from game.backends.x11.actions import ActionError
from game.backends.x11.interface import validate_actions


def pin(path):
    return {"path": str(path), "sha256": closure.sha(path)}


def condition(task):
    value = json.loads(json.dumps(task))
    value["source"].pop("path")
    value["fixture"].pop("world_path")
    return value


def classify_formal(result, lease, has_terminal_snapshot):
    """Keep recorded measurements, and do not manufacture a failed model result."""
    if result["status"] == "completed" and result["measurement"] == "valid":
        if not has_terminal_snapshot:
            raise ValueError("A valid completed measurement needs its terminal snapshot")
        return "recorded_valid_" + result["task_outcome"]
    if lease.get("finished_at") is not None and lease.get("returncode") != 0:
        return "interrupted_unavailable_not_a_model_failure"
    return "unresolved_measurement"


def public_trace(episode, result, boundaries):
    count = result["public_batches"]
    commands = sorted((episode / "commands").glob("*.json"))
    assert [p.name for p in commands] == [f"{i:03d}.json" for i in range(count + 1)]
    assert closure.load(commands[-1]) == {"finish": True}
    assert result["controller_finished"] is True
    assert 0 < result["elapsed_seconds"] < result["time_limit_seconds"]
    lower, upper = boundaries["begin_acknowledged_at_ns"], boundaries["end_requested_at_ns"]
    previous, elapsed = lower, 0
    pins, names, rejected = [], set(), []
    for index, path in enumerate(commands[:-1]):
        request = closure.load(path)
        assert not set(request) - {"role", "commands", "observe"}
        assert request.get("role", "Player") == "Player"
        batch = request.get("commands", [])
        response_path = episode / f"response-{index:03d}.json"
        response = closure.load(response_path)
        try:
            if batch:
                validate_actions(batch)
        except (ValueError, TypeError, ActionError) as error:
            assert response["success"] is False
            assert response["executed_commands"] == 0
            assert response["error"] == str(error)
            assert not response.get("results")
            rejected.append({"index": index, "error": str(error), "executed_commands": 0})
            batch = []
        else:
            assert response["success"] is True
            assert len(response["results"]) == len(batch)
        assert elapsed <= response["elapsed_seconds"] <= result["elapsed_seconds"]
        elapsed = response["elapsed_seconds"]
        for action, receipt in zip(batch, response.get("results", [])):
            assert action["name"] == receipt["operation"]
            assert previous <= receipt["started_at_ns"] <= receipt["finished_at_ns"] <= upper
            previous = receipt["finished_at_ns"]
            names.add(action["name"])
        frame = response["images"]["Player"]
        assert previous <= frame["captured_at_ns"] <= upper
        previous = frame["captured_at_ns"]
        image = episode / Path(frame["path"]).name
        pins.extend([pin(path), pin(response_path), pin(image)])
    pins.append(pin(commands[-1]))
    return {"validated_batches": count, "admitted_batches": count - len(rejected),
            "rejected_before_execution": rejected,
            "public_command_names": sorted(names), "files": pins}


def lease_record(root, task):
    candidates = []
    for path in (root / "output/temp/task_development/leases").glob("*.json"):
        row = closure.load(path)
        if row["task"] == task:
            candidates.append((path, row))
    assert len(candidates) == 1, task
    path, row = candidates[0]
    processes = {str(row[k]): Path(f"/proc/{row[k]}").exists()
                 for k in ("lease_pid", "command_pid")}
    assert not any(processes.values()), "Do not reconcile an episode with potentially live PIDs"
    return {"receipt": pin(path), "record": row, "recorded_pids_present": processes}


def current_cargo(root, selected):
    episode = root / "output/task-validation/original-minecraft-closure/cargo-vm-01"
    task = load_task(SOURCE / "config/minecraft/tasks/visual_motor/abandoned_mine_cargo.yaml")
    source, result = closure.load(episode / "source.json"), closure.load(episode / "result.json")
    assert condition(source["task"]) == condition(task.resolved())
    assert result["task_sha256"] == task.source.sha256
    assert result["time_limit_seconds"] == task.time_limit_seconds
    assert closure.sha(episode / "controller-harness.py") == source["harness_sha256"]
    fixture = closure.load(episode / "game/fixture.json")
    world = Path(task.fixture["world_path"])
    current_files = {str(p.relative_to(world)): closure.sha(p)
                     for p in world.rglob("*") if p.is_file()}
    assert fixture["sha256"] == current_files
    environment = closure.load(episode / "game/environment.json")
    assert environment["client_build_sha256"] == selected["source_sha256"]
    assert environment["track"] == task.task_type
    assert environment["server_sha256"] == selected["installation"][1]["server_sha256"]
    snapshots = [closure.snapshot(episode / phase) for phase in ("before", "after")]
    assert [s["phase"] for s in snapshots] == ["ready", "ended"]
    assert snapshots[0]["player_uuid"] == snapshots[1]["player_uuid"]
    assert snapshots[0]["boundaries"]["ready_at_ns"] == snapshots[1]["boundaries"]["ready_at_ns"]
    binding = closure.binding(task)
    binding.game.player_uuid = UUID(snapshots[0]["player_uuid"])
    binding.game.player_state.verify(nbtlib.load(
        episode / "before/playerdata" / f"{binding.game.player_uuid}.dat"), binding.game.player_uuid)
    binding.verify_initial(episode / "before")
    evaluation = binding.evaluate(episode / "before", episode / "after")
    metrics = binding.metrics(episode / "before", episode / "after")
    assert evaluation == result["evaluation"] and evaluation["success"] is True
    assert metrics == result["metrics"]
    trace = public_trace(episode, result, snapshots[1]["boundaries"])
    lease = lease_record(root, "original-abandoned-mine-cargo-vm-first")
    assert lease["record"]["returncode"] == 0
    return {
        "task_id": "minecraft/abandoned_mine_cargo",
        "recommendation": "task_acceptance_supported_pending_parent_reconciliation",
        "resolved_gate": "Exact released VM composition: all three originals and living grounded return in one episode.",
        "terminal": pin(episode / "result.json"), "evaluation": evaluation, "metrics": metrics,
        "elapsed_seconds": result["elapsed_seconds"], "budget_seconds": task.time_limit_seconds,
        "source": pin(episode / "source.json"), "fixture": pin(episode / "game/fixture.json"),
        "release_fixture_files_exact": len(current_files),
        "environment": pin(episode / "game/environment.json"),
        "harness": pin(episode / "controller-harness.py"),
        "authored_trace_reuse": pin(episode / "public-trace-reuse.json"),
        "snapshots": snapshots, "public_trace": trace, "lease": lease,
        "policy": {
            "known_blocking_bug": None,
            "feasibility": "Exact-condition whole VM success supplements retained ST evidence; no incompatible endpoint stitching.",
            "construct": "Identity-bound originals, elevation/access and settled return remain unchanged. Authored route use proves motor feasibility, not autonomous exploration.",
            "difficulty": "Retained independent ST3/VM4 (VM range3-4, high uncertainty); no easier variant, no rating inferred from this authored success.",
        },
        "remaining_gates": [], "deferred": ["Nonblocking difficulty calibration and final review."],
    }


def interrupted_route(root, short, track):
    run = root / f"output/task-validation/original-minecraft-closure/route-formal-{short}"
    episode = run / f"baseline/route_schema_transfer.{track}/episode_1"
    path = episode / "results/result.json"
    result = closure.load(path)
    task = load_task(SOURCE / f"config/minecraft/tasks/{'structured_tools' if short == 'st' else 'visual_motor'}/route_schema_transfer.yaml")
    config = closure.load(run / "config.json")
    assert condition(config["tasks"][0]) == condition(task.resolved())
    assert task.evaluator_parameters == {"variant": 5, "origin": [0, 0, 201]}
    lease = lease_record(root, f"original-route-schema-transfer-mapping5-first-{short}")
    terminal = (episode / "after/_livequest_snapshot.json").exists()
    return {
        "track": track, "result": pin(path), "configuration": pin(run / "config.json"),
        "raw_status": result["status"], "raw_measurement": result["measurement"],
        "raw_task_outcome": result["task_outcome"], "terminal_snapshot_present": terminal,
        "reconciled_state": classify_formal(result, lease["record"], terminal),
        "lease": lease, "historical_result_unchanged": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    closure.DEV = root / "output/temp/task_development"
    closure.HOME = closure.DEV / "minecraft-runtime/MC-R05-main-vitals-placement-cart-v1"
    freeze_path = root / "output/task-validation/original-minecraft-closure/source-freeze.json"
    freeze = closure.load(freeze_path)
    for path, digest in freeze["task_sources"].items():
        assert closure.sha(SOURCE / path) == digest
    selected = closure.runtime()
    assert selected["source_sha256"] == freeze["runtime"]["source_sha256"]
    quality_path = closure.DEV / "checks/minecraft-independent-quality.json"
    quality = closure.load(quality_path)
    review = next(r for r in quality["original_reference_coverage"] if r["task_id"] == "route_schema_transfer")
    review = deepcopy(review)
    for row in review["native_references"]:
        row["path"] = str(root / row["path"])
    tasks = {track: load_task(SOURCE / f"config/minecraft/tasks/{directory}/route_schema_transfer.yaml")
             for track, directory in (("structured_tool", "structured_tools"), ("visual_motor", "visual_motor"))}
    route = {
        "task_id": "minecraft/route_schema_transfer", "released_mapping": 5,
        "recommendation": "task_acceptance_supported_pending_parent_reconciliation",
        "native_bridge": closure.route_bridge(review, tasks),
        "formal_attempts": [interrupted_route(root, short, track)
                            for short, track in (("st", "structured_tool"), ("vm", "visual_motor"))],
        "resolved_gate": "Missing released-mapping5 model measurements are experiment-only, not task-admission blockers.",
        "policy": {
            "known_blocking_bug": None,
            "feasibility": "Retained whole mapping5 ST/VM trajectories replay with actual zero deaths under the current scorer.",
            "construct": "Same-episode cue reuse has retained/erased evidence; supplied-route VM is motor feasibility, not acquisition benefit.",
            "difficulty": "Retained ST3 (range2-3), VM4 (range3-4, high uncertainty). VM340.491m/344m margin remains disclosed.",
        },
        "remaining_gates": [],
        "experiment_gaps": ["Released-mapping5 ST/VM measurement unavailable after external termination; no retry."],
        "historical_mapping2": "Preserved as mapping2 outcomes; not substituted for mapping5.",
        "deferred": ["Nonblocking calibration and final review."],
    }
    expedition = root / "output/task-validation/original-minecraft-closure/expedition-vm-01"
    expedition_lease = lease_record(root, "original-expedition-first-public-vm")
    assert not (expedition / "result.json").exists()
    assert not (expedition / "after/_livequest_snapshot.json").exists()
    report = {
        "schema": "livequest-original-minecraft-resume/1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"worktree": str(SOURCE), "base_commit": freeze["source_commit"],
                   "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
                   "source_freeze": pin(freeze_path), "task_hashes_verified": freeze["task_sources"]},
        "checker": pin(Path(__file__)), "runtime": selected,
        "focused_tests": {
            "log": pin(closure.DEV / "checks/resume-minecraft-20261029-tests.log"),
            "output": (closure.DEV / "checks/resume-minecraft-20261029-tests.log").read_text(),
            "selectors": [
                "tests/test_game/minecraft/test_original_terminal_reconciliation.py",
                "tests/test_game/minecraft/test_route_transfer.py",
                "tests/test_game/minecraft/test_game.py",
                "tests/test_game/minecraft/test_install.py",
            ],
            "marker": "not game and not live", "new_native_episodes": 0,
        },
        "interpreter": {"path": sys.executable, "versions": {
            name: importlib.metadata.version(name) for name in ("nbtlib", "pytest", "PyYAML", "Pillow", "numpy")}},
        "review_inputs": [pin(quality_path), pin(closure.DEV / "checks/minecraft-original-reference-closure.json"),
                          pin(closure.DEV / "checks/minecraft-acceptance-policy-audit-20261029.json"),
                          pin(closure.DEV / "checks/task-delivery-status.json"),
                          pin(root / "output/survey/task_difficulty_and_capability_acceptance_20261027.md")],
        "tasks": [current_cargo(root, selected), route],
        "next_original_gap_review": {
            "task_id": "minecraft/expedition_record_reconstruction",
            "lease": expedition_lease,
            "state": "interrupted_without_terminal_receipt_not_task_failure",
            "completed_public_batches": len(list(expedition.glob("response-*.json"))),
            "source": pin(expedition / "source.json"),
            "remaining_gate": "VM composition still lacks all-original retrieval, public clue access and living return evidence in one bounded condition. Nine acknowledged batches and before-only snapshot do not close it.",
            "action": "No unchanged rerun: stop after primary evidence closure. A follow-up must isolate a specific clue/access/composition uncertainty.",
        },
        "changes": ["Added isolated, read-only terminal reconciliation and focused guard tests; no task/scorer/runtime edits."],
        "new_native_episodes": 0, "new_model_calls": 0, "lease_acquisitions": 0,
        "main_integration_performed": False, "ledger_edits": False,
        "recommendation_is_not_confirmed_integration": True,
        "preservation": "Existing outcomes, frozen source, main dirty worktree, runtime and Python environment were not overwritten.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "tasks": [t["task_id"] for t in report["tasks"]],
                      "new_episodes": 0, "integration": False}))


if __name__ == "__main__":
    main()
