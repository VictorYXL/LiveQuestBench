"""Read-only v3 publication bridge: immutable replay and explicit runtime admission."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from uuid import UUID

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from benchmark.config import load_task
from benchmark.factory import make_game
from game.minecraft.game import MinecraftGame
from game.minecraft.runtime import client, install
from game.minecraft.runtime.session import MinecraftSession

FROZEN = "58727868dcac99cf7378f42b1ebab1a19e145461"
MEASURED = "a1bf410fe4aa0ffe99a2d984e1288a528b628b8da25a5ab5ed5493bbd325805d"
CURRENT = "39b0c2e0e5549fa3921071d844ad9e2b8f3c1ff9ae4499531ce61683aeb98f6b"
SCIENTIFIC = (
    "game/minecraft/evaluators/circuit.py",
    "game/minecraft/evaluators/circuit_feedback.py",
    "game/minecraft/fixtures/circuit.py",
    "game/minecraft/fixtures/circuit_feedback_observer.py",
    "game/minecraft/fixtures/circuit_feedback_blocks.json",
    "config/minecraft/fixtures/workshop_circuit_feedback_v3.source.json",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob("*")) if p.is_file()}


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def frozen_sha(path):
    return hashlib.sha256(subprocess.check_output(["git", "show", f"{FROZEN}:{path}"])).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    development = args.development.resolve()
    runtime = development / "minecraft-runtime/MC-R05-main-vitals-placement-cart-v1"
    historical = development / "minecraft-runtime/MC-I03-placement-v1"
    os.environ["LIVEQUEST_MINECRAFT_HOME"] = str(runtime)
    source_files = {}
    for path in SCIENTIFIC:
        assert sha(ROOT / path) == frozen_sha(path), path
        source_files[path] = sha(ROOT / path)
    manifest_path = ROOT / SCIENTIFIC[-1]
    manifest = json.loads(manifest_path.read_text())
    fixture = ROOT / "config/minecraft/fixtures/workshop_circuit_feedback_v3"
    assert tree(fixture) == manifest["files"]
    assert len(manifest["files"]) == 43
    for name in manifest["files"]:
        path = str((fixture / name).relative_to(ROOT))
        assert sha(ROOT / path) == frozen_sha(path)
        source_files[path] = sha(ROOT / path)
    for folder in ("structured_tools", "visual_motor"):
        old = f"config/minecraft/prototypes/{folder}/workshop_circuit_feedback_v3.yaml"
        new = old.replace("/prototypes/", "/tasks/")
        assert sha(ROOT / old) == sha(ROOT / new) == frozen_sha(old)
        source_files[old] = source_files[new] = sha(ROOT / new)
    provenance = json.loads((runtime / "provenance.json").read_text())
    protected = {str(home): tree(home / "client-1.20.4") for home in (historical, runtime)}
    assert client.source_digest() == provenance["source_sha256"] == CURRENT
    client.check_client()
    for path, digest in provenance["source_files"].items():
        assert sha(client.source_root() / "src" / path) == digest
    for path, digest in provenance["classes"].items():
        assert sha(client.client_root() / "build/classes/java/main" / path) == digest
    for path, digest in provenance["dependencies"].items():
        assert sha(Path(path)) == digest
    assert json.loads((historical / "client-1.20.4/ready.json").read_text())["source_sha256"] == MEASURED
    os.environ["LIVEQUEST_MINECRAFT_HOME"] = str(historical)
    try:
        client.check_client()
    except RuntimeError as error:
        historical_rejection = str(error)
    else:
        raise AssertionError("Historical a1 must not admit current native sources")
    os.environ["LIVEQUEST_MINECRAFT_HOME"] = str(runtime)
    admissions, replays = [], []
    with ExitStack() as stack:
        for cls in (MinecraftGame, MinecraftSession):
            stack.enter_context(patch.object(cls, "start", side_effect=AssertionError("No native launch permitted")))
        for path in sorted((ROOT / "config/minecraft/tasks").glob("*/*.yaml")):
            task = load_task(path)
            output = development / "checks/I03-never-started" / path.parent.name / path.stem
            assert not output.exists()
            binding = make_game(task, output, headless=True, recording=False, recording_fps=10)
            if task.id == "workshop_circuit_feedback_v3":
                assert binding.game.server_factory is None
            installation = install.check_installation(
                task.fixture["instance"], track=task.task_type, verify_server=False)
            assert not output.exists()
            admissions.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path),
                               "status": "binding_and_offline_client_installation_pass",
                               "client_source": installation["client_build_sha256"]})
        native_pair_path = development / "checks/MC-I03-v3-corrected-runtime-pair-review.json"
        native_pair = json.loads(native_pair_path.read_text())
        for track, folder in (("st", "structured_tools"), ("vm", "visual_motor")):
            task_path = ROOT / f"config/minecraft/tasks/{folder}/workshop_circuit_feedback_v3.yaml"
            task = load_task(task_path)
            strict_path = development / f"checks/MC-I03-v3-final-{track}-strict-review.json"
            strict = json.loads(strict_path.read_text())
            assert strict["measurement"] == "valid" and strict["admitted_as_final_measurement"]
            assert strict["source_commit"] == "acd6100ed3aba29d218e192b2a4f23e20068f3d6"
            assert strict["runtime_source_sha256"] == MEASURED
            assert strict["task_sha256"] == sha(task_path)
            for kind, row in (("first_final", strict),
                              ("native_feasibility", native_pair["paired_native_feasibility"][track])):
                result_path = development.parent.parent.parent / row["result"]
                result = json.loads(result_path.read_text())
                assert sha(result_path) == row["result_sha256"]
                episode = result_path.parents[1] if kind == "first_final" else result_path.parent
                environment_path = episode / "game/environment.json"
                environment = json.loads(environment_path.read_text())
                assert environment["client_build_sha256"] == MEASURED
                before, after = episode / "before", episode / "after"
                immutable = {"before": tree(before), "after": tree(after)}
                output = development / "checks/I03-never-started-replay" / track / kind
                assert not output.exists()
                binding = make_game(task, output, headless=True, recording=False, recording_fps=10)
                assert binding.game.server_factory is None
                binding.game.player_uuid = UUID(environment["player"]["player_uuid"])
                binding.verify_initial(before)
                actual = binding.evaluate(before, after)
                metrics = binding.metrics(before, after)
                expected = (json.loads((episode / "results/evaluation.json").read_text())
                            if kind == "first_final" else result["evaluation"])
                assert actual == expected
                assert metrics == result["metrics"]
                assert binding.evaluate(before, before)["success"] is False
                assert immutable == {"before": tree(before), "after": tree(after)}
                assert not output.exists()
                if kind == "first_final":
                    assert result["measurement"] == "valid" and not result["errors"]
                    assert result["task_id"] == task.id
                    assert result["configuration_sha256"] == strict["configuration_sha256"]
                    assert sha(episode / "results/evaluation.json") == strict["evaluation_sha256"]
                    assert result["task_outcome"] == strict["task_outcome"]
                replays.append({
                    "track": track, "kind": kind, "result": str(result_path),
                    "result_sha256": sha(result_path), "environment_sha256": sha(environment_path),
                    "historical_runtime": MEASURED, "whole_evaluation_equal": True,
                    "death_metrics_equal": True, "initial_goal_false": True,
                    "success": actual["success"], "immutable_snapshot_files": immutable,
                    **({"strict_review": str(strict_path), "strict_review_sha256": sha(strict_path),
                        "measurement": strict["measurement"], "task_outcome": strict["task_outcome"]}
                       if kind == "first_final" else {}),
                })
    assert protected == {str(home): tree(home / "client-1.20.4") for home in (historical, runtime)}
    for path, digest in source_files.items():
        assert sha(ROOT / path) == digest
    result = {
        "schema": "livequest-i03-v3-version-bridge/1",
        "source_head": git("rev-parse", "HEAD").strip(), "frozen_handoff": FROZEN,
        "source_files": source_files, "fixture_file_count": 43,
        "published_id": "workshop_circuit_feedback_v3", "published_task_bytes_equal_frozen_prototypes": True,
        "historical_measured_runtime": MEASURED, "current_admission_runtime": CURRENT,
        "runtime_home": str(runtime), "runtime_provenance_sha256": sha(runtime / "provenance.json"),
        "runtime_sources_classes_dependencies_verified": True,
        "historical_and_current_runtime_unchanged": True, "historical_selection_rejected": historical_rejection,
        "admissions": admissions, "replays": replays, "i03_server_factory": "vanilla_default",
        "native_source_delta": git("diff", FROZEN, "--", "game/minecraft/client"),
        "state_scorer_delta": git("diff", FROZEN, "--", "game/minecraft/evaluators/state.py"),
        "validation_python": sys.executable, "verification_command": [sys.executable, *sys.argv],
        "verification_script_sha256": sha(Path(__file__)),
        "new_native_model_azure_or_formal_jobs": 0,
        "limits": [
            "Current native digest includes vitals and chest-cart support; it is not the measured a1 runtime.",
            "I03 uses vanilla server; optional L05 Fabric factory remains confined to function_replication.",
            "All-definition checks cover binding and offline client installation, not startup or exhaustive family sampling.",
            "Complete immutable scorer replays bridge archived results; no fresh-main gameplay is claimed.",
            "Original workshop_circuit_diagnosis formals are excluded.",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{len(admissions)} definitions admitted; four complete evaluation/death replays equal; no native jobs")


if __name__ == "__main__":
    main()
