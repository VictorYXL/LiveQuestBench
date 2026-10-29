"""Recover already-retained native VM projectile contacts and return; never run a game."""

import json
from pathlib import Path
import subprocess

import veloren_s05_public_aim_result as evidence

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.endpoints import load_pair


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = evidence.DEV / "experiments/VE-S05-observed-ranged-reference-vm"


def main():
    evidence.ARTIFACT = ARTIFACT
    before, after = load_pair(ARTIFACT / "before", ARTIFACT / "after")
    source = evidence.load(ARTIFACT / "source-manifest.json")
    assert source["head"] == "d8610eaba74d88534a4ac2e55998c776523149a6"
    controller_path = "tests/fixtures/veloren/ranged_motor_reference.py"
    assert (ARTIFACT / "reference-controller.py").read_bytes() == subprocess.check_output(
        ["git", "show", f"{source['head']}:{controller_path}"], cwd=ROOT)
    task_path = ROOT / "config/veloren/tasks/visual_motor/ranged_firing_positions.yaml"
    assert task_path.read_bytes() == (ARTIFACT / "task.yaml").read_bytes()
    runtime = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/veloren-native-route-20261027/runtime.json")
    assert evidence.load(ARTIFACT / "game/environment.json")["runtime"] == evidence.load(runtime)
    task = load_task(task_path)
    binding = create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools,
        output_dir=ROOT / "output/test/s05-prior-contact-unused-native",
        headless=True, recording=False, recording_fps=10,
    )
    reference = evidence.load(ARTIFACT / "reference.json")
    evaluation = binding.evaluate(ARTIFACT / "before", ARTIFACT / "after")
    assert evaluation == reference["evaluation"]
    contacts = evidence.component_native_contacts(before, after)
    assert len(contacts["owned_projectile_contacts"]) == 2
    assert before["control_actor"]["uid"] == after["control_actor"]["uid"] == 102
    shots = [row for row in reference["actions"] if any(
        command["name"] == "mouse_down" and command["arguments"].get("button") == "left"
        for command in row["input"]["commands"])]
    result = {
        "schema": "livequest-s05-prior-vm-contact-recovery/1",
        "source_commit": source["head"],
        "source_manifest": evidence.pin(ARTIFACT / "source-manifest.json"),
        "task": evidence.pin(ARTIFACT / "task.yaml"),
        "runtime": evidence.pin(runtime),
        "environment": evidence.pin(ARTIFACT / "game/environment.json"),
        "controller": evidence.pin(ARTIFACT / "reference-controller.py"),
        "reference": evidence.pin(ARTIFACT / "reference.json"),
        "snapshots": [evidence.pin(ARTIFACT / phase / "observation.json")
                      for phase in ("before", "after")],
        "exact_current_scorer_full_evaluation_equal": True,
        "elapsed_seconds": reference["elapsed"],
        "whole_task_success": evaluation["success"],
        "checks": evaluation["checks"],
        "public_shot_batches": shots,
        "native_projectile_contact_evidence": contacts,
        "inventory_before": before["inventory"]["items"],
        "inventory_after": after["inventory"]["items"],
        "energy_before": before["energy"],
        "energy_after": after["energy"],
        "correction": "The original pre-diagnostic search recovered zero-damage evaluations but missed these already-retained projectile contacts. Emission/lower-yard access was not a new factual gap; the new hinted episode is redundant on that component. No outcome is rewritten and no further episode is authorized.",
        "native_geometry_boundary": "Both contact points are in the original south yard. An operator's north shot-counter label is not native target/yard attribution.",
        "same_episode_composition": "This complete original VM episode contains two actual owned projectile contacts and a genuinely alive/grounded/still arch endpoint, with unchanged consumable counts and two native deaths. It remains zero target damage, not two-target combat completion or unhinted competence.",
        "remaining_question": "Safe public target-directed aiming/hits and the full two-target resource/time/return construction remain for bounded independent review; a particular whole VM victory is not required.",
    }
    out = ROOT / "checks/s05-prior-vm-contact-recovery-20261029.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "receipt": evidence.pin(out), "contacts": len(contacts["owned_projectile_contacts"]),
        "whole_success": evaluation["success"],
        "native_deaths": len(contacts["native_player_deaths"]),
        "return_check": next(row for row in evaluation["checks"] if row["kind"] == "position"),
    }, indent=2))


if __name__ == "__main__":
    main()
