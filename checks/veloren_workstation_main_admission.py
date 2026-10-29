"""Verify the exact original-guide integration offline, without native play."""

import argparse
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
from game.veloren.evaluators.workstation import evaluate_workstation
from game.veloren.runtime.session import runtime_configuration
from game.veloren.runtime.workstation import ENVIRONMENT, expected_route_schema


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(evidence_root, *, require_committed):
    manifest_path = ROOT / "docs/evidence/VE-I02-main-integration-bridge-20261030.json"
    manifest = read(manifest_path)
    review = manifest["quality_review"]
    entry = read(evidence_root / review["path"])["dated_addenda"][review["addendum"]]
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == review["sha256"]
    assert entry["disposition"] == "supported"
    for path, expected in manifest["evidence_sha256"].items():
        assert digest(evidence_root / path) == expected, path
    for path, expected in {
        **manifest["integration_files_sha256"], **manifest["inherited_main_dependencies_unchanged"],
    }.items():
        assert digest(ROOT / path) == expected, path
        if require_committed:
            data = subprocess.check_output(["git", "-C", str(ROOT), "show", f"HEAD:{path}"])
            assert hashlib.sha256(data).hexdigest() == expected, path
    if require_committed:
        data = subprocess.check_output([
            "git", "-C", str(ROOT), "show", "HEAD:" + str(manifest_path.relative_to(ROOT)),
        ])
        assert hashlib.sha256(data).hexdigest() == digest(manifest_path)

    original = evidence_root / manifest["original_adapter"]
    source = (ROOT / "game/veloren/evaluators/workstation.py").read_text()
    restored = source.replace(
        "from game.veloren.evaluators.workstation_route import",
        "from game.veloren.evaluators.itinerary import",
    )
    assert restored == (original / "game/veloren/evaluators/workstation.py").read_text()
    assert (ROOT / "game/veloren/evaluators/workstation_route.py").read_bytes() == (
        original / "game/veloren/evaluators/itinerary.py"
    ).read_bytes()

    runtime_path = evidence_root / manifest["runtime"]["path"]
    assert digest(runtime_path) == manifest["runtime"]["sha256"]
    config = read(runtime_path)
    for path, expected in config["sha256"].items():
        assert digest(path) == expected, path
    registrations = []
    previous = os.environ.get(ENVIRONMENT)
    os.environ[ENVIRONMENT] = str(runtime_path)
    try:
        for track, declaration in manifest["configurations"].items():
            path = ROOT / declaration["path"]
            authored = yaml.safe_load(path.read_text())
            archived = yaml.safe_load((evidence_root / declaration["archived_task"]).read_text())
            authored["fixture"].pop("runtime_profile")
            for value in (authored, archived):
                value["fixture"].pop("world_path")
            assert authored == archived
            task = load_task(path)
            selected, cfg = runtime_configuration(task.fixture)
            assert selected == runtime_path.resolve()
            assert expected_route_schema(task.fixture, cfg) == "native-client-route/1"
            binding = create_binding(
                fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
                parameters=task.evaluator_parameters, tools=task.tools,
                output_dir=ROOT / "output/not-started-i02-registration",
                headless=True, recording=False, recording_fps=10,
            )
            binding.verify_initial(evidence_root / declaration["archived_before"])
            registrations.append({"track": track, "task_id": task.id,
                                  "route_schema": "native-client-route/1"})
    finally:
        if previous is None:
            os.environ.pop(ENVIRONMENT, None)
        else:
            os.environ[ENVIRONMENT] = previous

    fixture = load_task(ROOT / manifest["configurations"]["st"]["path"]).fixture
    native_code = """
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.rpg_benchmark import runtime
cfg = json.loads(Path(sys.argv[2]).read_text())
loaded = runtime.load_runtime(Path(cfg['upstream_runtime']), cfg['upstream_sha256'], backend='renderer')
from game.veloren.runtime.server_extension import select_server
server = select_server(cfg, Path(loaded['renderer']['paths']['server']))
from game.veloren.runtime.worker import Session
fixture = json.loads(sys.argv[3])
async def reject():
    changed = dict(cfg, route_evidence='native-client-route/2')
    session = Session(changed, Path(sys.argv[1]) / 'output/not-started-i02-worker', 'visual_motor', fixture)
    try:
        await session.start()
    except ValueError as error:
        assert 'exact independently qualified runtime' in str(error), str(error)
    else:
        raise AssertionError('Changed native configuration was not rejected before startup')
asyncio.run(reject())
print(json.dumps({'strict_runtime_loader': True, 'worker_rejected_changed_runtime_before_start': True,
                  'server': str(server), 'native_processes_launched': 0}))
"""
    preflight = json.loads(subprocess.check_output([
        config["python"], "-c", native_code, str(ROOT), str(runtime_path),
        json.dumps(fixture),
    ], text=True))
    replays = []
    for record in manifest["frozen_replays"]:
        directory = evidence_root / record["run"]
        task = load_task(directory / "task.yaml")
        expected = read(directory / "reference.json")["evaluation"]
        actual = evaluate_workstation(directory / "before", directory / "after",
                                      **task.evaluator_parameters)
        assert actual == expected, record["run"]
        assert actual["success"] == record["success"]
        replays.append({"run": record["run"], "success": actual["success"],
                        "full_evaluation_dictionary_unchanged": True})
    return {
        "schema": "livequest-workstation-main-admission/1",
        "head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "source_files_match_head": require_committed,
        "manifest_sha256": digest(manifest_path),
        "source_files_verified": len(manifest["integration_files_sha256"]),
        "quality_review": review, "registrations": registrations,
        "runtime": {**manifest["runtime"], "wrapper_files_verified": len(config["sha256"]),
                    "preflight": preflight},
        "frozen_replays": replays,
        "tests": manifest["tests"],
        "new_native_or_model_jobs": 0,
        "qualification_boundary": manifest["qualification_boundary"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    parser.add_argument("--require-committed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = verify(arguments.evidence_root.resolve(), require_committed=arguments.require_committed)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
