"""Replay source-bound spatial evidence without starting native or model processes."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.encounter import encounter_checks
from game.veloren.evaluators.endpoints import load_pair
from game.veloren.evaluators.itinerary import itinerary_checks


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path):
    return {"path": str(path), "sha256": digest(path)}


def binding(task):
    return create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools,
        output_dir=ROOT / "output/test/spatial-replay-unused-native",
        headless=True, recording=False, recording_fps=10,
    )


def replay(task, artifact):
    initial, final = load_pair(artifact / "before", artifact / "after")
    fixture_path = artifact / "game/fixture.json"
    fixture = load(fixture_path)
    declared = {k: v for k, v in task.fixture.items() if k != "world_path"}
    actual = {k: v for k, v in fixture["fixture"].items() if k != "world_path"}
    assert declared == actual, artifact
    assert fixture["world"]["map_sha256"] == digest(task.fixture["world_path"])
    scorer = binding(task)
    result = scorer.evaluate(artifact / "before", artifact / "after")
    checks = {"itinerary": itinerary_checks, "encounter": encounter_checks}
    opening = checks[task.evaluator](initial, initial, **task.evaluator_parameters)
    assert not opening["success"]
    reference = load(artifact / "reference.json")
    assert result == reference["evaluation"], artifact
    result_row = {
        "artifact": str(artifact),
        "snapshots": [pin(artifact / phase / "observation.json") for phase in ("before", "after")],
        "reference": pin(artifact / "reference.json"),
        "initial_success": False, "terminal_success": result["success"],
        "exact_archived_evaluation_equal": True,
        "actual_fixture": pin(fixture_path),
        "fixture_and_world_byte_parity": True,
        "elapsed_seconds": reference.get("elapsed"),
        "native_route_schemas": sorted({
            row["private_route_evidence"]["route_schema"]
            for row in (initial, final) if "private_route_evidence" in row
        }),
        "checks": result["checks"],
    }
    if "private_route_evidence" in initial:
        first, last = (row["private_route_evidence"] for row in (initial, final))
        samples = last["route_samples"]
        added = samples[len(first["route_samples"]):]
        measured = first["route_samples"][-1:] + added
        result_row["route_boundary"] = {
            "actor_uid": first["uid"], "session_id": first["session_id"],
            "opening_sequence": first["samples"], "final_sequence": last["samples"],
            "opening_tick": first["through_tick"], "final_tick": last["through_tick"],
            "opening_prefix_preserved": samples[:len(first["route_samples"])] == first["route_samples"],
            "new_sample_count": len(added),
            "whole_history_including_setup_maximum_step_m": max(
                (math.dist(a["position"], b["position"]) for a, b in zip(samples, samples[1:])),
                default=0,
            ),
            "post_readiness_maximum_recorded_step_m": max(
                (math.dist(a["position"], b["position"]) for a, b in zip(measured, measured[1:])),
                default=0,
            ),
            "post_readiness_visits": [
                {"sequence": check["sequence"],
                 "position": next(row["position"] for row in added if row["sequence"] == check["sequence"])}
                for check in result["checks"]
                if check["kind"] == "native_region_visit" and check["passed"]
            ],
        }
    return result_row


def pickup_timing(artifact):
    fixture = load(artifact / "game/fixture.json")
    source = fixture["supplies"][0]
    initial, final = load_pair(artifact / "before", artifact / "after")
    boundaries = load(artifact / "game/boundaries.json")
    journal = artifact / "game/native.jsonl"
    session = initial["session_id"]
    item = "common.items.crafting_ing.hide.tough_hide"
    with journal.open() as stream:
        for line_number, line in enumerate(stream, 1):
            if session not in line or "Collected" not in line or item not in line:
                continue
            row = json.loads(line)
            event = row.get("event", {})
            data = event.get("data", {})
            if (row.get("actor") == session
                    and event.get("event") == "pickup_inventory_update"
                    and data.get("server_event") == "Collected"
                    and data.get("acquisition_observed") is True
                    and data.get("collected_item", {}).get("id") == {"Simple": item}):
                break
        else:
            raise AssertionError("Missing native VM Collected event")
    created_start, created_end = source["creation_wall_interval"]
    age = row["wall_monotonic"] - created_start
    ready = boundaries["ready_at_ns"] / 1e9
    assert 0 < ready - created_start < 10
    assert boundaries["begin_acknowledged_at_ns"] / 1e9 < row["wall_monotonic"]
    assert row["wall_monotonic"] < boundaries["end_requested_at_ns"] / 1e9
    assert age < source["expires_after_game_seconds"]
    def count(observation):
        return sum(entry["item"]["amount"] for entry in observation["inventory"]["items"]
                   if entry["item"]["id"] == {"Simple": item})
    assert count(initial) == 0 and count(final) == 1
    return {
        "journal": pin(journal), "line_number": line_number,
        "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
        "event": row,
        "fixture": pin(artifact / "game/fixture.json"),
        "boundaries": pin(artifact / "game/boundaries.json"),
        "creation_wall_interval": [created_start, created_end],
        "ready_age_host_seconds_upper_bound": ready - created_start,
        "pickup_age_host_seconds_upper_bound": age,
        "host_margin_to_300_seconds": 300 - age,
        "native_lifetime_game_seconds": source["expires_after_game_seconds"],
        "initial_hide_count": 0, "terminal_hide_count": 1,
        "interpretation": "Actual same-player native Collected event proves acquisition before expiry; original full VM episode retains the hide through return. Host age/margin estimates are not exact server Object spawned_at clocks. Collected has no source UID; no unique-bundle provenance claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dev = args.archive_root.resolve() / "output/temp/task_development"
    fixed = dev / "veloren-route-v2-contact-fix"
    freeze = load(fixed / "first-final-route2/freeze.json")
    runtime = fixed / "candidate-runtime.json"
    assert digest(runtime) == freeze["runtime_sha256"]
    runtime_config = load(runtime)
    for path, expected in runtime_config["sha256"].items():
        assert digest(path) == expected, path
    assert digest(runtime_config["renderer"]) == freeze["renderer_sha256"]
    assert runtime_config["route_evidence"] == "native-client-route/2"

    report = {
        "schema": "livequest-parallel-spatial-replay/1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "no_native_or_model_start": True,
        "replay_script": pin(Path(__file__)),
        "runtime": pin(runtime),
        "renderer": pin(runtime_config["renderer"]),
        "runtime_constituents_verified": len(runtime_config["sha256"]),
        "source": {}, "tasks": {},
    }
    relevant = {
        path: expected for path, expected in freeze["source_sha256"].items()
        if path.startswith("game/veloren/") or path in (
            "game/route_transfer.py", "game/backends/x11/interface.py",
            "game/backends/x11/display.py")
    }
    changed = []
    for path, expected in relevant.items():
        actual = digest(ROOT / path)
        report["source"][path] = actual
        if actual != expected:
            changed.append(path)
    assert changed == ["game/veloren/binding.py"], changed
    frozen_binding = subprocess.check_output([
        "git", "show", f"{freeze['source_commit']}:game/veloren/binding.py",
    ], cwd=ROOT, text=True)
    addition = (
        '    elif evaluator == "active_build":\n'
        '        from game.veloren.evaluators.active_build import evaluate_active_build, validate_active_build\n'
        '        evaluators[evaluator] = evaluate_active_build\n'
        '        validators[evaluator] = validate_active_build\n'
    )
    current = (ROOT / "game/veloren/binding.py").read_text()
    assert current.replace(addition, "").replace(
        '("encounter", "expedition", "damage", "active_build")',
        '("encounter", "expedition", "damage")',
    ) == frozen_binding
    report["source_delta"] = {
        "frozen_source": freeze["source_commit"], "changed": changed,
        "review": "Exact normalization removes only the unselected active_build branch and role guard. All other frozen Veloren and public motor source bytes match.",
    }

    proof = load(fixed / "vm-dogleg-stdlib-verification.json")
    cliff = {"tracks": [], "task_quality_ready": True, "main_admitted": False}
    for row in proof["checks"]:
        track = row["track"]
        profile = "structured_tools" if track == "st" else "visual_motor"
        path = ROOT / f"config/veloren/tasks/{profile}/cliff_ledge_ascent.yaml"
        assert digest(path) == freeze["tracks"][track]["task_sha256"]
        result = replay(load_task(path), Path(row["artifact"]))
        assert result["terminal_success"]
        assert result["native_route_schemas"] == ["native-client-route/2"]
        cliff["tracks"].append({"track": track, "task": pin(path), **result})
    cliff["formal_measurements"] = {}
    for track in ("st", "vm"):
        artifact = dev / f"experiments/VE-S03-first-final-route2-{track}"
        result_path = list(artifact.glob("run/baseline/*/episode_1/results/result.json"))
        status = load(artifact / "status.json")
        result = load(result_path[0]) if len(result_path) == 1 else {}
        lease_path = dev / "leases" / (
            "291fb88777b3488f9397f0e3167244e1.json" if track == "st"
            else "8f58a3b84a6f49e3833865dc0c98b273.json")
        lease = load(lease_path)
        assert lease["status"] == "finished"
        cliff["formal_measurements"][track] = {
            "status_receipt": pin(artifact / "status.json"),
            "status_label": status["status"],
            "result_receipt": pin(result_path[0]) if len(result_path) == 1 else None,
            "result_status": result.get("status"),
            "measurement": result.get("measurement"),
            "task_outcome": result.get("task_outcome"),
            "terminal_lease": pin(lease_path),
            "lease_returncode": lease["returncode"],
            "recovered_state": "valid_failure" if track == "st" else "interrupted_unavailable_measurement",
            "acceptance_blocker": False,
        }
    report["tasks"]["VE-S03"] = cliff

    switchback = {"historical_route1_not_relabelled": [], "current_route2": None}
    for track, label in (("st", "contained-public-reference"), ("vm", "contained-image-reference")):
        profile = "structured_tools" if track == "st" else "visual_motor"
        path = ROOT / f"config/veloren/tasks/{profile}/subterranean_switchback.yaml"
        task = load_task(path)
        artifact = dev / f"experiments/VE-S04-{label}-{track}"
        initial, final = load_pair(artifact / "before", artifact / "after")
        assert initial["private_route_evidence"]["route_schema"] == "native-client-route/1"
        try:
            binding(task).evaluate(artifact / "before", artifact / "after")
        except ValueError as error:
            assert "schema mismatch" in str(error)
        else:
            raise AssertionError("Historical route/1 was accepted as route/2")
        archived_task = load_task(dev / f"worktrees/VE-S04/config/veloren/tasks/{profile}/subterranean_switchback.yaml")
        frozen_bytes = subprocess.check_output([
            "git", "show", f"c1a27bbcc82525e717605248583877f34ac8ba68:config/veloren/tasks/{profile}/subterranean_switchback.yaml",
        ], cwd=ROOT)
        assert path.read_bytes() == frozen_bytes
        assert archived_task.task == task.task
        assert archived_task.tools == task.tools
        assert archived_task.evaluator_parameters == task.evaluator_parameters
        assert archived_task.time_limit_seconds == task.time_limit_seconds
        old_fixture = {k: v for k, v in archived_task.fixture.items() if k != "world_path"}
        new_fixture = {k: v for k, v in task.fixture.items() if k != "world_path"}
        assert old_fixture == new_fixture
        assert digest(archived_task.fixture["world_path"]) == digest(task.fixture["world_path"])
        switchback["historical_route1_not_relabelled"].append({
            "track": track, "task": pin(path), "reference": pin(artifact / "reference.json"),
            "native_schema": "native-client-route/1", "current_scorer_rejects": True,
            "unchanged_physical_fixture_world_and_goal": True,
            "native_terminal_position": final["position"],
        })
    artifact = dev / "experiments/VE-S04-parallel-route2-20261029-st"
    if (artifact / "after").exists() and (artifact / "reference.json").exists():
        task = load_task(ROOT / "config/veloren/tasks/structured_tools/subterranean_switchback.yaml")
        switchback["current_route2"] = replay(task, artifact)
        current = switchback["current_route2"]
        assert current["terminal_success"]
        assert current["native_route_schemas"] == ["native-client-route/2"]
        assert current["route_boundary"]["post_readiness_maximum_recorded_step_m"] <= 4
        environment = load(artifact / "game/environment.json")
        assert environment["runtime"] == runtime_config
        manifest = load(artifact / "source-manifest.json")
        for name, expected in manifest["sha256"].items():
            assert digest(ROOT / name) == expected
        cleanup = load(artifact / "game/cleanup.json")
        native_cleanup = load(artifact / "game/native-cleanup.json")
        lease_path = dev / "leases/292ffd37be3247f4b33e405767bca165.json"
        lease = load(lease_path)
        assert cleanup["worker_returncode"] == 0 and native_cleanup["server_stopped"]
        assert lease["status"] == "finished" and lease["returncode"] == 0
        assert not Path("/proc", str(environment["renderer_pid"])).exists()
        setup = load(artifact / "game/fixture.json")
        boundaries = load(artifact / "game/boundaries.json")
        current["native_admission"] = {
            "environment": pin(artifact / "game/environment.json"),
            "runtime_exactly_equals_pinned_config": True,
            "source_manifest": pin(artifact / "source-manifest.json"),
            "source_commit": manifest["head"],
            "adapter_files_verified": len(manifest["sha256"]),
            "ready_supply_age_host_seconds_upper_bound": (
                boundaries["ready_at_ns"] / 1e9 - setup["supplies"][0]["creation_wall_interval"][0]
            ),
            "worker_cleanup": pin(artifact / "game/cleanup.json"),
            "native_cleanup": pin(artifact / "game/native-cleanup.json"),
            "lease": pin(lease_path),
            "worker_returncode": 0, "server_stopped": True, "renderer_process_gone": True,
        }
    historical_vm = dev / "experiments/VE-S04-contained-image-reference-vm"
    switchback["historical_vm_resource_timing"] = pickup_timing(historical_vm)
    switchback["unchanged_vm_controls"] = []
    for name in ("game/veloren/visual_motor/interface.py", "game/veloren/runtime/session.py"):
        assert (historical_vm / "python-source" / name).read_bytes() == (ROOT / name).read_bytes()
        switchback["unchanged_vm_controls"].append(pin(ROOT / name))
    switchback["observer_noninterference"] = {
        "patch": pin(ROOT / "game/veloren/patches/0008-native-physics-route-evidence.patch"),
        "build_receipt": pin(fixed / "build-receipt.json"),
        "folded_patch_equivalence": pin(fixed / "folded-patch-equivalence.json"),
        "existing_physics_tests": pin(fixed / "physics-tests.log"),
        "existing_renderer_tests": pin(fixed / "renderer-tests.log"),
        "review": "The opt-in NativeRouteTrace records collision-resolved increments and final positions; it does not change velocities, positions, collision resolution or input semantics. Existing five native physics tests include observed/unobserved transform equality for slow-frame and volume-contact cases, resolved-wall points and sticky overflow/rejection. Two renderer tests preserve opt-in and displacement/sequence guards. Actual local voxel contacts still reject; broad-phase overlap alone does not. ST and VM share this observer, while VM facade and session transport are byte-identical to the historical complete VM.",
        "limit": "Historical VM remains route/1; current task-specific route/2 evidence is the fresh ST check, not a reconstructed or relabelled VM trajectory. S03's current-runtime VM witness supports the shared image/motor interface, not S04's geometry by itself.",
    }
    report["tasks"]["VE-S04"] = switchback

    ranged = {"retained_current_scorer_replays": []}
    for track, label in (("st", "settled-progress-reference"), ("vm", "observed-ranged-reference"),
                         ("vm", "guarded-ranged-reference")):
        profile = "structured_tools" if track == "st" else "visual_motor"
        path = dev / f"worktrees/VE-S05/config/veloren/tasks/{profile}/ranged_firing_positions.yaml"
        frozen_bytes = subprocess.check_output([
            "git", "show", f"d8610eaba74d88534a4ac2e55998c776523149a6:config/veloren/tasks/{profile}/ranged_firing_positions.yaml",
        ], cwd=ROOT)
        assert path.read_bytes() == frozen_bytes
        artifact = dev / f"experiments/VE-S05-{label}-{track}"
        row = replay(load_task(path), artifact)
        ranged["retained_current_scorer_replays"].append({"track": track, **row})
    automatic = dev / "experiments/VE-S05-automatic-ranged-reference-vm"
    lease = dev / "leases/4997fc178b754afd923a73c88f7e6b40.json"
    terminal = load(lease)
    assert terminal["status"] == "finished" and terminal["returncode"] == -15
    assert not any((automatic / name).exists() for name in ("before", "after", "reference.json", "control.json"))
    assert load(automatic / "source-manifest.json")["head"] == "c7f0fc84966d80ed0c35b84e4b6a4969d51ed8fc"
    ranged["automatic_recovery"] = {
        "lease": pin(lease), "source_manifest": pin(automatic / "source-manifest.json"),
        "classification": "interrupted_initialization_not_task_outcome",
        "terminal_returncode": -15, "new_gameplay_evidence": False,
    }
    ranged["remaining_gate"] = (
        "Native-grounded public-VM bow sightline/aim access and constructive joint two-target/return "
        "timing remain unsupported. Neither a particular controller win nor a model outcome is required."
    )
    report["tasks"]["VE-S05"] = ranged
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: {
        "route2_successes": len(value.get("tracks", [])),
        "current_route2": bool(value.get("current_route2")),
        "retained_replays": len(value.get("retained_current_scorer_replays", [])),
    } for key, value in report["tasks"].items()}))


if __name__ == "__main__":
    main()
