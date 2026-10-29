"""Verify the exact I01/P01/R01 main bridge without launching a native episode."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.contract import evaluate_contract
from game.veloren.evaluators.encounter import encounter_checks
from game.veloren.runtime.server_extension import select_server
from game.veloren.runtime.session import runtime_configuration


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def git_bytes(path, committed):
    return subprocess.check_output(["git", "-C", str(ROOT), "show",
                                    ("HEAD:" if committed else ":") + path])


def legacy_pair(run):
    rows, metadata = [], []
    for phase, expected_phase in (("before", "ready"), ("after", "ended")):
        path = run / phase
        meta = read(path / "_livequest_snapshot.json")
        row = read(path / "observation.json")
        if (meta["schema"] != "veloren-endpoint-v1" or meta["phase"] != expected_phase
                or meta["sha256"] != digest(path / "observation.json")
                or row["session_id"] != meta["session_id"]):
            raise ValueError("Invalid frozen legacy endpoint")
        rows.append(row)
        metadata.append(meta)
    if (rows[0]["session_id"] != rows[1]["session_id"]
            or rows[0]["self_identity"] != rows[1]["self_identity"]
            or metadata[0]["captured_at_ns"] > metadata[1]["capture_started_at_ns"]):
        raise ValueError("Invalid frozen legacy endpoint identity or chronology")
    return rows


def verify(output, committed):
    manifest_path = ROOT / "docs/evidence/VE-I01-P01-R01-main-integration-bridge-20261030.json"
    manifest = read(manifest_path)
    for path, expected in manifest["integration_files_sha256"].items():
        if path.startswith("config/"):
            actual = hashlib.sha256(git_bytes(path, committed)).hexdigest()
        else:
            actual = digest(ROOT / path)
            if committed:
                assert hashlib.sha256(git_bytes(path, True)).hexdigest() == actual, path
        assert actual == expected, path
    for path, expected in manifest["inherited_source_sha256"].items():
        assert digest(ROOT / path) == expected, path
    if committed:
        assert hashlib.sha256(git_bytes(str(manifest_path.relative_to(ROOT)), True)).hexdigest() == digest(manifest_path)
    runtime_path = Path(manifest["runtime"]["path"])
    assert digest(runtime_path) == manifest["runtime"]["sha256"]
    runtime = read(runtime_path)
    for path, expected in runtime["sha256"].items():
        assert digest(path) == expected, path
    assert digest(runtime["upstream_runtime"]) == runtime["upstream_sha256"]
    upstream = read(runtime["upstream_runtime"])
    server = select_server(runtime, Path(runtime["upstream_runtime"]).parent / upstream["renderer"]["server"])
    assert digest(server) == manifest["runtime"]["server_sha256"]
    assert digest(runtime["renderer"]) == manifest["runtime"]["renderer_sha256"]
    assert runtime.get("route_evidence") is None
    strict_code = (
        "import json;from pathlib import Path;from scripts.rpg_benchmark import runtime;"
        f"runtime.load_runtime(Path({runtime['upstream_runtime']!r}),"
        f"{runtime['upstream_sha256']!r},backend='renderer');"
        "print(json.dumps({'strict_upstream_load':'passed'}))"
    )
    strict = subprocess.run([runtime["python"], "-c", strict_code], check=True,
                            capture_output=True, text=True)
    assert json.loads(strict.stdout)["strict_upstream_load"] == "passed"
    registry = read(ROOT / "docs/reference_tasks_manifest.json")
    snapshots = output.parent / "committed-task-snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    registrations, replays, dirty_conditions = [], [], []
    for task_id, task in manifest["tasks"].items():
        audit = read(task["review"]["path"])["dated_addenda"][task["review"]["index"]]
        encoded = json.dumps(audit, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert hashlib.sha256(encoded.encode()).hexdigest() == task["review"]["stable_sha256"]
        specs = {}
        for track, definition in task["configurations"].items():
            path = definition["path"]
            raw = git_bytes(path, committed)
            assert hashlib.sha256(raw).hexdigest() == definition["sha256"]
            data = yaml.safe_load(raw)
            original = yaml.safe_load(subprocess.check_output([
                "git", "-C", str(ROOT), "show", manifest["reviewed_source_commit"] + ":" + path,
            ]))
            without_profile = deepcopy(data)
            del without_profile["fixture"]["runtime_profile"]
            assert without_profile == original, path
            matches = [row for row in registry["tasks"] if row["path"] == path]
            assert len(matches) == 1
            assert matches[0]["sha256"] == definition["sha256"]
            assert matches[0]["definition"] == data
            snapshot = snapshots / f"{task_id}-{track}.yaml"
            snapshot.write_bytes(raw)
            spec = load_task(snapshot)
            spec.fixture["world_path"] = str((ROOT / path).parent.joinpath(data["fixture"]["world_path"]).resolve())
            assert spec.time_limit_seconds == 2700
            assert not spec.fixture.get("route_evidence") and not spec.fixture.get("pickup_evidence")
            setting = task["runtime_environment"]
            previous = os.environ.get(setting)
            try:
                os.environ[setting] = str(runtime_path)
                selected, _ = runtime_configuration(spec.fixture)
                assert selected == runtime_path.resolve()
                create_binding(
                    fixture=spec.fixture, task_type=spec.task_type, evaluator=spec.evaluator,
                    parameters=spec.evaluator_parameters, tools=spec.tools,
                    output_dir=output.parent / "not-launched", headless=True,
                    recording=False, recording_fps=10,
                )
            finally:
                if previous is None:
                    os.environ.pop(setting, None)
                else:
                    os.environ[setting] = previous
            specs[track] = spec
            registrations.append({"task": task_id, "track": track, "sha256": definition["sha256"],
                                  "runtime_profile": spec.fixture["runtime_profile"], "native_started": False})
            if (ROOT / path).read_bytes() != raw:
                assert path in manifest["preserved_dirty_contract_paths"]
                dirty_conditions.append({"path": path, "qualified": "committed configuration only",
                                         "working_tree_condition_qualified": False})
        assert specs["st"].fixture == specs["vm"].fixture
        assert specs["st"].evaluator_parameters == specs["vm"].evaluator_parameters
        replay = task["frozen_replay"]
        run = Path(replay["run"])
        for relative, expected in replay["files_sha256"].items():
            assert digest(run / relative) == expected
        if task_id == "VE-I01":
            evaluated = evaluate_contract(run / "before", run / "after", **specs["st"].evaluator_parameters)
        else:
            evaluated = encounter_checks(*legacy_pair(run), **specs["st"].evaluator_parameters)
        assert evaluated == replay["expected_evaluation"], task_id
        assert evaluated["success"] is False
        replays.append({
            "task": task_id, "same_frozen_evaluation": True, "success": False,
            "envelope": "current exact endpoint" if task_id == "VE-I01" else
                        "Frozen veloren-endpoint-v1 separately authenticated, then unchanged encounter core; current live loader remains strict.",
        })
    return {
        "schema": "livequest-originals-main-admission-receipt/1",
        "head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "source_files_match_head": committed,
        "manifest_sha256": digest(manifest_path),
        "registrations": registrations, "frozen_replays": replays,
        "runtime": manifest["runtime"], "strict_upstream_load": "passed",
        "working_tree_exclusions": dirty_conditions,
        "tests": manifest["tests"],
        "scope": "Exact three original conditions; shared guard/L01 excluded.",
        "native_episodes_launched_by_check": 0, "models": 0,
        "new_whole_victories_claimed": False,
        "runtime_limit": "Qualified frozen native events only; no route/2 qualification or generic validation relaxation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-committed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = verify(output, args.require_committed)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"output": str(output), "sha256": digest(output),
                      "registrations": len(receipt["registrations"]), "frozen_replays": len(receipt["frozen_replays"])}))


if __name__ == "__main__":
    main()
