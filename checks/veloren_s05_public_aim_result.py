"""Reconcile the single S05 public-image check only after native cleanup."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.encounter import encounter_checks
from game.veloren.evaluators.endpoints import load_pair

DEV = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development")
ARTIFACT = DEV / "experiments/VE-S05-parallel-automatic-ranged-20261029-vm"
LEASE = DEV / "leases/31a861e3ef6640b2867474fc70149ce5.json"


def load(path):
    return json.loads(path.read_text())


def pin(path):
    with path.open("rb") as stream:
        return {"path": str(path), "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def component_native_contacts(initial, final):
    player = initial["control_actor"]["uid"]
    opening = initial["private_encounter_evidence"]["through_sequence"]
    oracle = ARTIFACT / "game/private-native-oracle.ndjson"
    contacts = []
    preceding_binding = None
    with oracle.open() as stream:
        for line_number, line in enumerate(stream, 1):
            event = json.loads(line)
            if event.get("sequence", 0) <= opening:
                continue
            data = event.get("data", {})
            if event["event"] == "combat_entity_bindings":
                own = next((row for row in data["bindings"] if row["uid"] == player), None)
                if own:
                    preceding_binding = {
                        "line": line_number, "sequence": event["sequence"],
                        "host_unix_ns": event["host_unix_ns"], "player": own,
                    }
            if event["event"] == "projectile_solid_contact" and data.get("owner_uid") == player:
                contacts.append({
                    "line": line_number, "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                    "event": event, "preceding_native_equipment_health_binding": preceding_binding,
                })
    deaths = [event for event in final["private_death_evidence"]["events"]
              if event["sequence"] > opening and event["data"].get("uid") == player]
    return {
        "oracle": pin(oracle), "player_uid": player, "opening_sequence": opening,
        "owned_projectile_contacts": contacts, "native_player_deaths": deaths,
        "emission_and_actual_solid_contact_proven": bool(contacts),
        "target_damage_proven_by_contact": False,
        "boundary": "These are actual native surface contacts, not an inference from missing damage. Contact does not itself identify the tool; the preceding equipped starter bow, recorded primary-release input and source semantics support bow provenance. No exact firing-position/continuous-route sample is claimed.",
    }


def main():
    global ARTIFACT, LEASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hinted-component", action="store_true")
    args = parser.parse_args()
    expected_source = "f3a08be5d506b97ea5a8c2a3c47150679edd0c43"
    controller_path = "tests/fixtures/veloren/automatic_ranged_motor_reference.py"
    output_name = "s05-public-aim-terminal-20261029.json"
    if args.hinted_component:
        ARTIFACT = DEV / "experiments/VE-S05-hinted-bow-component-20261029-vm"
        LEASE = DEV / "leases/0a850c6468e5410a991d09e6da535723.json"
        expected_source = "6c5ca408de746a981e8e6bea6287ad53d370c6a7"
        controller_path = "tests/fixtures/veloren/hinted_bow_component.py"
        output_name = "s05-hinted-bow-terminal-20261029.json"
    lease = load(LEASE)
    assert lease["status"] == "finished" and not lease["uses_model"]
    assert not Path("/proc", str(lease["command_pid"])).exists()
    source = load(ARTIFACT / "source-manifest.json")
    assert source["head"] == expected_source
    assert (ARTIFACT / "reference-controller.py").read_bytes() == subprocess.check_output(
        ["git", "show", f"{source['head']}:{controller_path}"], cwd=ROOT)
    for name, expected in source["sha256"].items():
        assert pin(ROOT / name)["sha256"] == expected, name
    if args.hinted_component:
        for name in ("automatic_ranged_motor_reference.py", "ranged_motor_reference.py"):
            path = "tests/fixtures/veloren/" + name
            assert (ROOT / path).read_bytes() == subprocess.check_output(
                ["git", "show", f"{expected_source}:{path}"], cwd=ROOT)
    result = {
        "schema": "livequest-s05-public-aim-terminal/1",
        "source_commit": source["head"],
        "task": pin(ARTIFACT / "task.yaml"),
        "source_manifest": pin(ARTIFACT / "source-manifest.json"),
        "controller": pin(ARTIFACT / "reference-controller.py"),
        "lease": pin(LEASE), "lease_returncode": lease["returncode"],
        "model_calls": 0, "source_files_verified": len(source["sha256"]),
        "private_state_used_to_steer": False,
        "main_admission_claimed": False, "unchanged_native_retry_permitted": False,
    }
    if not (ARTIFACT / "after/observation.json").exists():
        result.update(
            classification="initialization_or_measurement_unavailable",
            task_outcome="unknown",
            limit="Missing terminal native evidence is not a task failure or proof of impossibility.",
        )
    else:
        task = load_task(ROOT / "config/veloren/tasks/visual_motor/ranged_firing_positions.yaml")
        assert (ARTIFACT / "task.yaml").read_bytes() == (
            ROOT / "config/veloren/tasks/visual_motor/ranged_firing_positions.yaml").read_bytes()
        initial, final = load_pair(ARTIFACT / "before", ARTIFACT / "after")
        binding = create_binding(
            fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
            parameters=task.evaluator_parameters, tools=task.tools,
            output_dir=ROOT / "output/test/s05-replay-unused-native",
            headless=True, recording=False, recording_fps=10,
        )
        reference = load(ARTIFACT / "reference.json")
        evaluation = binding.evaluate(ARTIFACT / "before", ARTIFACT / "after")
        assert evaluation == reference["evaluation"]
        assert not encounter_checks(initial, initial, **task.evaluator_parameters)["success"]
        automatic = load(ARTIFACT / "automatic-result.json") if (ARTIFACT / "automatic-result.json").exists() else None
        if args.hinted_component:
            automatic = load(ARTIFACT / "component-result.json")
        environment = load(ARTIFACT / "game/environment.json")
        runtime = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/veloren-native-route-20261027/runtime.json")
        assert environment["runtime"] == load(runtime)
        shots = sum(
            command["name"] == "mouse_down" and command["arguments"].get("button") == "left"
            for action in reference["actions"]
            for command in action["input"]["commands"]
        )
        result.update(
            classification="guided_public_image_native_check_not_model_performance",
            task_outcome="success" if evaluation["success"] else "failure",
            initial_success=False, terminal_success=evaluation["success"],
            exact_current_scorer_evaluation_equal=True,
            elapsed_seconds=reference["elapsed"], public_batches=len(reference["actions"]),
            public_bow_shots=shots, checks=evaluation["checks"],
            shot_count_scope="Recorded left-mouse-down commands, not an asserted native projectile emission count.",
            automatic_controller=automatic,
            runtime=pin(runtime), environment=pin(ARTIFACT / "game/environment.json"),
            snapshots=[pin(ARTIFACT / name / "observation.json") for name in ("before", "after")],
            reference=pin(ARTIFACT / "reference.json"),
            limit="A controller limitation or short engineering cap does not establish task impossibility or difficulty. A whole success would still require independent construct/difficulty and source admission review.",
        )
        if args.hinted_component:
            damage = {row["role"]: row["damage"] for row in evaluation["checks"]
                      if row["kind"] == "encounter"}
            hits = [row for row in evaluation["checks"] if row["kind"] == "required_attack"]
            result.update(
                classification="authored_hint_public_motor_component_not_original_discovery_or_difficulty",
                native_bow_component_success=any(
                    row["qualifying_hits"] > 0 and damage.get(row["role"], 0) > 0 for row in hits),
                component_damage=damage,
                component_attack_checks=hits,
                public_operator_controls=pin(ARTIFACT / "component-controls.jsonl")
                if (ARTIFACT / "component-controls.jsonl").exists() else None,
                component_result=pin(ARTIFACT / "component-result.json"),
                original_condition_base="0417cf521d6e153005eace5f15eafd1943c8e429",
                scope_limit="Component damage is not a full-task success, original visual discovery or difficulty evidence. Two-target resource/time and return composition remain separate.",
                native_projectile_contact_evidence=component_native_contacts(initial, final),
            )
    for name in ("cleanup.json", "native-cleanup.json"):
        path = ARTIFACT / "game" / name
        if path.exists():
            result[name] = pin(path)
    if result.get("exact_current_scorer_evaluation_equal"):
        cleanup = load(ARTIFACT / "game/cleanup.json")
        native_cleanup = load(ARTIFACT / "game/native-cleanup.json")
        pids = {
            "lease": lease["lease_pid"], "command": lease["command_pid"],
            "server": native_cleanup["server_pid"], "renderer": environment["renderer_pid"],
        }
        absent = {name: not Path("/proc", str(pid)).exists() for name, pid in pids.items()}
        assert cleanup["worker_returncode"] == 0
        assert native_cleanup["server_stopped"] and all(absent.values())
        result["cleanup_verified"] = {
            "worker_returncode": cleanup["worker_returncode"],
            "server_stopped": native_cleanup["server_stopped"],
            "pids": pids, "processes_absent_at_reconciliation": absent,
        }
    path = ROOT / "checks" / output_name
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result.get(key) for key in (
        "classification", "task_outcome", "elapsed_seconds", "public_batches", "public_bow_shots",
        "automatic_controller", "native_bow_component_success", "component_damage")}, indent=2))


if __name__ == "__main__":
    main()
