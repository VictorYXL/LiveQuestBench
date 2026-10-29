"""Verify the reviewed L05 source/config/runtime bridge without launching a game."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from benchmark.config import load_experiment, load_task
from benchmark.factory import make_game, validate_experiment
from game.veloren.evaluators.endpoints import evaluate_state
from game.veloren.prototypes.covered_support_forks_solid import build_solid_candidate
from game.veloren.runtime.session import runtime_configuration


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "docs/evidence/VE-L05-main-integration-bridge-20261030.json"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify():
    manifest = json.loads(BRIDGE.read_text())
    for path, expected in manifest["integration_files_sha256"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Integrated source differs from the reviewed bridge: {path}")
    for path, expected in manifest["existing_dependency_sha256"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Existing scored/control dependency changed: {path}")
    runtime_path = Path(manifest["runtime"]["path"])
    if digest(runtime_path) != manifest["runtime"]["sha256"]:
        raise ValueError("The supported runtime descriptor changed")
    task = load_task(ROOT / manifest["registration"]["task"])
    original = deepcopy(task.fixture)
    with patch.dict(os.environ, {"LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME": str(runtime_path)}):
        selected, runtime = runtime_configuration(task.fixture)
        assert selected == runtime_path.resolve()
        assert runtime["camera_observation"] == "native-local-camera/1"
        assert runtime["scene_observation"] == "native-solid-scene/1"
        for path, expected in runtime["sha256"].items():
            if digest(path) != expected:
                raise ValueError(f"Runtime executable, patch or sidecar changed: {path}")
        assert digest(runtime["renderer"]) == manifest["runtime"]["renderer_sha256"]
        assert digest(runtime["local_source_manifest"]) == manifest["runtime"]["local_source_manifest_sha256"]
        assert digest(runtime["upstream_runtime"]) == runtime["upstream_sha256"]
        source = json.loads(Path(runtime["local_source_manifest"]).read_text())
        source_pins = source["files_sha256"]
        for path, expected in source_pins.items():
            if digest(Path(runtime["source"]) / path) != expected:
                raise ValueError(f"Qualified native source changed: {path}")
        for seed in (0, 0, 1):
            with patch("game.veloren.support_forks.secrets.randbits", return_value=seed):
                binding = make_game(
                    task, ROOT / "unused-l05-preflight", headless=True,
                    recording=False, recording_fps=5,
                )
            expected, _ = build_solid_candidate(Path(task.fixture["world_path"]), seed)
            assert binding.game.fixture == expected["fixture"]
            assert binding.game.fixture.get("route_observation") is None
            assert not binding.game.fixture.get("route_evidence", False)
            assert binding.game.phase == "new"
        validate_experiment(load_experiment(ROOT / manifest["registration"]["experiment"]))
    assert task.fixture == original
    assert not (ROOT / "unused-l05-preflight").exists()
    native = Path(manifest["native_component"]["root"])
    replay = evaluate_state(native / "before", native / "after", **task.evaluator_parameters)
    original_result = json.loads((native / "result.json").read_text())["task_evaluation"]
    assert replay == original_result and replay["success"] is False
    return {
        "status": "verified_without_native_or_model_execution",
        "bridge_sha256": digest(BRIDGE),
        "source_files_verified": len(manifest["integration_files_sha256"]),
        "existing_dependencies_verified": len(manifest["existing_dependency_sha256"]),
        "registered_template_sha256": task.source.sha256,
        "registration": manifest["registration"],
        "runtime_sha256": digest(runtime_path),
        "runtime_declared_files_verified": len(runtime["sha256"]),
        "native_source_files_verified": len(source_pins),
        "actual_runtime_renderer_sha256": digest(runtime["renderer"]),
        "both_mappings_and_repeated_choice_verified": True,
        "configuration_mutated": False,
        "public_profile": "camera1+scene1;route=null;ordinary minimap remains legal",
        "current_main_score_replay": replay,
        "no_whole_native_success_inferred": True,
        "new_native_or_model_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
