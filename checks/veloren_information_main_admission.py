"""Verify the exact information-task bridge offline; never launch native play."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.market import evaluate_market
from game.veloren.evaluators.message import evaluate_message
from game.veloren.runtime.server_extension import select_server
from game.veloren.runtime.session import runtime_configuration


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify(*, require_committed):
    manifest_path = ROOT / "docs/evidence/VE-I03-I04-main-integration-bridge-20261029.json"
    manifest = read(manifest_path)
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    for review in manifest["independent_reviews"]:
        entry = read(review["path"])["dated_addenda"][review["addendum"]]
        encoded = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == review["sha256"]
    for name, expected in manifest["inherited_main_dependencies_unchanged"].items():
        assert digest(ROOT / name) == expected, name
    for name, expected in manifest["integration_files_sha256"].items():
        assert digest(ROOT / name) == expected, name
        if require_committed:
            committed = subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{name}"])
            assert hashlib.sha256(committed).hexdigest() == expected, name
    if require_committed:
        committed = subprocess.check_output([
            "git", "-C", str(ROOT), "show", "HEAD:" + str(manifest_path.relative_to(ROOT)),
        ])
        assert hashlib.sha256(committed).hexdigest() == digest(manifest_path)
    registrations = []
    runtimes = {}
    for stable_id, task in manifest["tasks"].items():
        runtime_path = Path(task["runtime"]["path"])
        assert digest(runtime_path) == task["runtime"]["sha256"]
        config = read(runtime_path)
        for path, expected in config["sha256"].items():
            assert digest(path) == expected, path
        upstream_path = Path(config["upstream_runtime"])
        assert digest(upstream_path) == config["upstream_sha256"]
        upstream = read(upstream_path)
        server = select_server(config, upstream_path.parent / upstream["renderer"]["server"])
        assert digest(server) == task["runtime"]["server_sha256"]
        assert digest(config["renderer"]) == task["runtime"]["renderer_sha256"]
        runtimes[stable_id] = {
            "path": str(runtime_path), "sha256": digest(runtime_path),
            "protocol": config.get("initial_message_protocol"),
            "route_evidence": config.get("route_evidence"),
            "wrapper_files_verified": len(config["sha256"]),
            "environment_key": task["runtime"]["environment_key"],
        }
        for track, definition in task["configurations"].items():
            path = ROOT / definition["path"]
            assert digest(path) == definition["sha256"], str(path)
            spec = load_task(path)
            assert spec.time_limit_seconds == 2700
            assert not spec.fixture.get("route_evidence")
            setting = task["runtime"]["environment_key"]
            previous = os.environ.get(setting)
            try:
                os.environ[setting] = str(runtime_path)
                selected, _ = runtime_configuration(spec.fixture)
                assert selected == runtime_path.resolve()
                create_binding(
                    fixture=spec.fixture, task_type=spec.task_type, evaluator=spec.evaluator,
                    parameters=spec.evaluator_parameters, tools=spec.tools,
                    output_dir=ROOT / "output/not-launched-information-binding",
                    headless=True, recording=False, recording_fps=10,
                )
            finally:
                if previous is None:
                    os.environ.pop(setting, None)
                else:
                    os.environ[setting] = previous
            registrations.append({
                "stable_id": stable_id, "task_id": spec.id, "track": track,
                "evaluator": spec.evaluator, "configuration_sha256": digest(path),
                "runtime_sha256": digest(runtime_path), "native_started": False,
            })
    replays = []
    for replay in manifest["frozen_replays"]:
        task = manifest["tasks"][replay["stable_id"]]
        spec = load_task(ROOT / task["configurations"]["st"]["path"])
        run = Path(replay["run"])
        for relative, expected in replay["sha256"].items():
            assert digest(run / relative) == expected
        evaluate = evaluate_message if replay["stable_id"] == "VE-I03" else evaluate_market
        result = evaluate(run / "before", run / "after", **spec.evaluator_parameters)
        assert result["success"] is replay["expected_success"], replay["label"]
        assert result == replay["expected_evaluation"], replay["label"]
        replays.append({"label": replay["label"], "success": result["success"],
                        "same_frozen_evaluation": True})
    return {
        "schema": "livequest-information-main-admission-receipt/1",
        "head": head, "source_files_match_head": require_committed,
        "scope": "I03 exact v3 and I04 reviewed placement repair; I02 remains VM pending.",
        "manifest_sha256": digest(manifest_path),
        "source_files_verified": len(manifest["integration_files_sha256"]),
        "registrations": registrations, "runtimes": runtimes, "frozen_replays": replays,
        "tests": manifest["tests"],
        "independent_reviews": manifest["independent_reviews"],
        "new_native_or_model_jobs": 0,
        "whole_current_runtime_native_success_claimed": False,
        "runtime_scope": "Exact pinned v3 and original market runtime; no route/2 native equivalence claimed.",
        "difficulty": "Bounded design judgment supported; statistical and latency calibration remain provisional.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-committed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT)
    receipt = verify(require_committed=args.require_committed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(output), "sha256": digest(output),
                      "head": receipt["head"], "registrations": len(receipt["registrations"]),
                      "frozen_replays": len(receipt["frozen_replays"])}))


if __name__ == "__main__":
    main()
