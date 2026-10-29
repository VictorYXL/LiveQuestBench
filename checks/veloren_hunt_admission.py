"""C01-only, read-only source/evidence admission; no game, model or scorer replay."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


REVIEW_SOURCE = "966d21875301276c906cbb33f0f7cc796c2e1398"
TASK = "coordinated_route_hunt"
EVIDENCE = "checks/veloren-hunt-evidence-20261029.json"
QUALITY = "docs/evidence/coordinated-route-hunt-quality-20261029.json"
SOURCE_SCOPE = (
    "benchmark", "game/veloren", "game/backends/x11",
    "game/team.py", "game/base_game.py", "game/bindings.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), "--no-pager", *args])


def pin(root, path):
    return {"path": str(path.relative_to(root)), "sha256": digest(path)}


def check(root, evidence_root):
    evidence_path, quality_path = root / EVIDENCE, root / QUALITY
    evidence, quality = load(evidence_path), load(quality_path)
    assert quality["disposition"] == "supported"
    assert quality["ledger_stable_id"] == f"veloren/{TASK}"
    assert digest(evidence_path) == quality["receipt"]["sha256"]
    assert evidence["source"]["commit"] == quality["receipt"]["source_commit"] == REVIEW_SOURCE
    head = git(root, "rev-parse", "HEAD").decode().strip()
    paths = git(root, "ls-tree", "-r", "--name-only", REVIEW_SOURCE, "--", *SOURCE_SCOPE)
    paths = {path for path in paths.decode().splitlines() if path.endswith((".py", ".patch"))}
    current = git(root, "ls-tree", "-r", "--name-only", head, "--", *SOURCE_SCOPE)
    assert paths == {path for path in current.decode().splitlines() if path.endswith((".py", ".patch"))}
    paths |= {
        f"config/veloren/tasks/{track}/{TASK}.yaml"
        for track in ("structured_tools", "visual_motor")
    }
    paths.add("docs/reference_tasks_manifest.json")
    source_checks = []
    for path in sorted(paths):
        reviewed = git(root, "show", f"{REVIEW_SOURCE}:{path}")
        committed = git(root, "show", f"{head}:{path}")
        actual = (root / path).read_bytes()
        assert reviewed == committed == actual, f"Material source/working-tree mismatch: {path}"
        source_checks.append({
            "path": path, "review_sha256": hashlib.sha256(reviewed).hexdigest(),
            "head_sha256": hashlib.sha256(committed).hexdigest(),
            "worktree_sha256": hashlib.sha256(actual).hexdigest(),
            "head_matches_review": True, "worktree_matches_head": True,
        })
    for track, directory in (("st", "structured_tools"), ("vm", "visual_motor")):
        assert digest(root / f"config/veloren/tasks/{directory}/{TASK}.yaml") == (
            quality["receipt"][f"task_{track}_sha256"]
        )

    refs = [
        evidence["source"]["reused_replay"], evidence["runtime"]["receipt"],
        evidence["runtime"]["native_source_manifest"],
        evidence["validation"]["light_tests"]["log"],
        *evidence["original_vm"]["pins"],
        *evidence["original_vm"]["actual_observation_images"].values(),
        *evidence["runtime"]["native_sources_newly_hash_checked"].values(),
        *(row["trace"] for row in evidence["original_vm"]["public_motor"].values()),
    ]
    for ref in refs:
        assert digest(evidence_root / ref["path"]) == ref["sha256"], ref["path"]
    reviewed_script = evidence_root / "output/review/parallel-ve-hunt-20261029/reviewed-analyze.py"
    assert digest(reviewed_script) == evidence["validation"]["evidence_script"]["sha256"]
    replay = load(evidence_root / evidence["source"]["reused_replay"]["path"])
    records = {row["track"]: row for row in replay["records"] if row["task_id"] == TASK}
    assert records["structured_tool"]["current_evaluation"]["success"]
    assert not records["visual_motor"]["current_evaluation"]["success"]
    assert all(row["runtime_matches_explicit_pin"] for row in records.values())
    assert evidence["runtime"]["receipt"]["sha256"] == quality["receipt"]["runtime_manifest_sha256"]
    assert evidence["original_vm"]["joint_active_seconds"] == 1124.227395753
    assert evidence["original_vm"]["separate_player_resources"]["Beta"]["native_deaths"] == 0
    assert evidence["original_vm"]["correction_to_previous_proposal"]["Beta_fall"]["data"]["cause"] == "Falling"
    assert evidence["constructive_vm_review"]["time_budget"]["illustrative_total_seconds"] == 1503
    assert evidence["validation"]["native_processes_started"] == 0
    assert evidence["validation"]["models_called"] == 0

    return {
        "schema": "livequest-c01-source-admission-check/1",
        "task": f"veloren/{TASK}", "passed": True,
        "review_source": REVIEW_SOURCE, "checked_main_source": head,
        "source_checks": source_checks,
        "changed_paths_since_review": git(
            root, "diff", "--name-only", REVIEW_SOURCE, head,
        ).decode().splitlines(),
        "bridge": (
            "Every selected benchmark, native Veloren adapter/scorer/patch, X11, team, task "
            "and frozen manifest byte equals the independently reviewed source in both HEAD "
            "and working tree. Other committed task/evidence changes do not enter C01's "
            "unchanged execution path. Historical runs are not relabeled current executions."
        ),
        "reviewed_evidence": pin(root, evidence_path),
        "independent_quality": pin(root, quality_path),
        "reviewed_extractor": pin(evidence_root, reviewed_script),
        "verified_existing_small_evidence_files": len(refs),
        "runtime": evidence["runtime"],
        "four_quality_gates": {
            "known_blocking_bug": quality["bug_and_source_status"]["known_blocking_bug"],
            "feasibility": quality["feasibility_argument"]["composition_conclusion"],
            "construct": quality["construct_status"],
            "difficulty": quality["difficulty_status"],
        },
        "preserved_limits": {
            "historical_failure": quality["historical_failure_corrections_preserved"],
            "historical_provenance": quality["bug_and_source_status"]["historical_provenance_limit"],
            "runtime": quality["bug_and_source_status"]["runtime_limit"],
            "time": "1503s is a constructive planning allowance, never an actual VM result or guarantee.",
            "experiment": quality["experiment_status"],
            "diagnostics": quality["diagnostic_transfer_boundary"],
        },
        "light_tests": evidence["validation"]["light_tests"],
        "light_test_source_bridge": (
            "16existing tests ran on isolated966d218; relevant production bytes equal current main. "
            "Unrelated dirty main initialization tests were not used or overwritten."
        ),
        "new_native_or_model_executions": 0,
        "new_scorer_replays": 0,
        "no_default_runtime_admission": True,
        "no_ledger_mutation": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    print(json.dumps(check(root, (args.evidence_root or root).resolve()), indent=2))


if __name__ == "__main__":
    main()
