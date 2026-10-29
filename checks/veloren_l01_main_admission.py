"""Verify exact L01 registration, runtime capabilities and frozen false outcomes."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import load_experiment, load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.route_transfer import evaluate_route
from game.veloren.runtime.session import runtime_configuration


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify(evidence_root, committed):
    bridge_path = ROOT / "docs/evidence/VE-L01-main-integration-bridge-20261030.json"
    bridge = read(bridge_path)
    source_files = {**bridge["integration_files_sha256"], **bridge["inherited_source_sha256"]}
    for path, expected in source_files.items():
        assert digest(ROOT / path) == expected, path
        if committed:
            blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{path}"])
            assert hashlib.sha256(blob).hexdigest() == expected, path
    if committed:
        assert subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{bridge_path.relative_to(ROOT)}"]) == bridge_path.read_bytes()
    registry = read(ROOT / "docs/reference_tasks_manifest.json")
    old_registry = json.loads(subprocess.check_output([
        "git", "-C", str(ROOT), "show", bridge["base_main"] + ":docs/reference_tasks_manifest.json",
    ]))
    changed = {item["path"] for item in bridge["tracks"].values()}
    assert {key: value for key, value in registry.items() if key != "tasks"} == {
        key: value for key, value in old_registry.items() if key != "tasks"
    }
    assert [row for row in registry["tasks"] if row["path"] not in changed] == [
        row for row in old_registry["tasks"] if row["path"] not in changed
    ]
    assert len(registry["tasks"]) == len(old_registry["tasks"])
    candidate_path = evidence_root / bridge["qualified_VM"]["path"]
    assert digest(candidate_path) == bridge["qualified_VM"]["sha256"]
    candidate = yaml.safe_load(candidate_path.read_text())
    registrations, replays, runtimes = [], [], {}
    for track, definition in bridge["tracks"].items():
        path = ROOT / definition["path"]
        data = yaml.safe_load(path.read_text())
        assert digest(path) == definition["sha256"]
        rows = [row for row in registry["tasks"] if row["path"] == definition["path"]]
        assert len(rows) == 1 and rows[0]["definition"] == data
        assert rows[0]["sha256"] == digest(path)
        if track == "vm":
            normalized = deepcopy(data)
            normalized["fixture"]["world_path"] = candidate["fixture"]["world_path"]
            assert normalized == candidate
            assert digest(Path(candidate["fixture"]["world_path"])) == digest(path.parent / data["fixture"]["world_path"])
        else:
            original = subprocess.check_output([
                "git", "-C", str(ROOT), "show",
                bridge["original_source"] + ":" + definition["path"],
            ])
            assert path.read_bytes() == original
        spec = load_task(path)
        experiment = load_experiment(ROOT / definition["experiment"])
        assert sum(task.source.sha256 == definition["sha256"] for task in experiment.tasks) == 1
        runtime_info = bridge["runtimes"][track]
        runtime_path = evidence_root / runtime_info["path"]
        assert digest(runtime_path) == runtime_info["sha256"]
        env = {
            "LIVEQUEST_VELOREN_RUNTIME": str(evidence_root / bridge["runtimes"]["st"]["path"]),
            "LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME": str(evidence_root / bridge["runtimes"]["vm"]["path"]),
        }
        with patch.dict(os.environ, env):
            selected, runtime = runtime_configuration(spec.fixture)
            assert selected == runtime_path.resolve()
            assert runtime["route_evidence"] == "native-client-route/2"
            for name, value in definition["observation_profiles"].items():
                assert spec.fixture.get(name) == value
                if value is not None:
                    assert runtime[name] == value
            for dependency, expected in runtime["sha256"].items():
                assert digest(dependency) == expected, dependency
            assert digest(runtime["renderer"]) == runtime_info["renderer_sha256"]
            local = read(runtime["local_source_manifest"])
            for source, expected in local["files_sha256"].items():
                assert digest(Path(runtime["source"]) / source) == expected, source
            strict = subprocess.run([
                runtime["python"], "-c",
                "from pathlib import Path;from scripts.rpg_benchmark import runtime;"
                f"runtime.load_runtime(Path({runtime['upstream_runtime']!r}),"
                f"{runtime['upstream_sha256']!r},backend='renderer')",
            ], check=True, capture_output=True, text=True)
            assert strict.returncode == 0
            unused = evidence_root / "output/review/parallel-ve-originals-20261029/L01-not-launched"
            assert not unused.exists()
            create_binding(
                fixture=spec.fixture, task_type=spec.task_type, evaluator=spec.evaluator,
                parameters=spec.evaluator_parameters, tools=spec.tools,
                output_dir=unused, headless=True, recording=False, recording_fps=10,
            )
            assert not unused.exists()
        run = evidence_root / definition["frozen_run"]
        for relative, expected in definition["frozen_sha256"].items():
            assert digest(run / relative) == expected
        replay = evaluate_route(run / "before", run / "after", **spec.evaluator_parameters)
        result_field = "evaluation" if track == "st" else "task_evaluation"
        assert replay == read(run / "result.json")[result_field]
        assert replay["success"] is False
        registrations.append({"track": track, "path": definition["path"], "id": data["id"], "sha256": digest(path)})
        replays.append({"track": track, "run": str(run), "result": replay})
        runtimes[track] = {
            "sha256": digest(runtime_path), "renderer_sha256": digest(runtime["renderer"]),
            "route_evidence": runtime["route_evidence"], "runtime_pins": len(runtime["sha256"]),
            "source_pins": len(local["files_sha256"]), "strict_upstream_load": "passed",
        }
    return {
        "status": "verified_exact_registration_and_frozen_false_replays",
        "head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "source_files_match_head": committed,
        "bridge_sha256": digest(bridge_path),
        "registered_rows_changed": 2,
        "other_registry_rows_unchanged": True,
        "registrations": registrations, "runtimes": runtimes, "frozen_replays": replays,
        "native_or_model_calls": 0,
        "scope": "New VM local-solid-v1 only; original ST remains separate. Observation local-view/1 is not physics route/1. Neither false outcome is relabelled.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--committed", action="store_true")
    args = parser.parse_args()
    result = verify(args.evidence_root.resolve(), args.committed)
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "frozen_replays"}, indent=2))
