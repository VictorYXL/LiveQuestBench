"""Verify only the reviewed sheltered C05 ST/VM source and explicit f90 runtime."""

import argparse
import ast
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "output/temp/task_development"
SOURCE = "8a16931615bdda2fcaefee0280caa7a649c213fc"
PARENT = "34ec6d851b710460b24ceaece89ada76b1a95e6e"
TASK = "caravan_protection_team_sheltered"
RUNTIME = "f90ca9a97e20a106e6d749368319cdd45243a2f902605e7797c6f8e3613c3793"
HOOKS = {
    "game/team.py": "2c7972538e6d1153e9cab85a939a8ee2f318b1bf6ca1efae4ab581f9feb84eae",
    "game/veloren/evaluators/encounter.py": "4e7dfb4132ddfb5a0331f30f77971b8e9126d33033dae9ad4fe3fe690be4a923",
    "game/veloren/fixture.py": "3856b5dc01149a5350022dbef1bf8500495d3d836f21258db60125c2b00e9d0a",
}
TASK_HASHES = {
    "structured_tools": "035878e4f5457a9100f44780a5b97c033dea4561c031046221e4dac3a8b5b909",
    "visual_motor": "c32fb2af7d59b94008dd4e543a55b0138832e5648d0d6d98f4f21304ad72455f",
}


def git(*args):
    return subprocess.check_output(["git", "--no-pager", *args], cwd=ROOT)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": digest(path)}


def read(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def symbol(source, name):
    return ast.dump(next(node for node in ast.walk(ast.parse(source))
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name == name), include_attributes=False)


def branch(source, operation):
    return ast.dump(next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.If)
                         and ast.unparse(node.test) == f"operation == {operation!r}"),
                    include_attributes=False)


def check(runtime_path, require_committed):
    head = git("rev-parse", "HEAD").decode().strip()
    assert git("branch", "--show-current").decode().strip() == "main"
    assert head == PARENT or git("merge-base", "--is-ancestor", PARENT, head) == b""
    for path, expected in HOOKS.items():
        assert digest(ROOT / path) == expected, path
    base_path = DEV / "checks/VE-C05-current-main-bridge-20261030.json"
    classified_path = DEV / "checks/VE-C05-current-main-bridge-validation-20261030.json"
    assert digest(base_path) == "7073d92c4297b9660ad3be60b94d668e368f89656b0c05f424b34330b4474fe4"
    assert digest(classified_path) == "e9e6584bb12967ffab9b5802c719d51b3ac3714dc4eda6dd2c1edb8171a692c7"
    base, classified = read(base_path), read(classified_path)
    reasons = {row["path"]: row["scope"] for row in classified["delta_classification"]}
    archive = DEV / "checks/VE-C05-public-sharing-escort-v3-capacity-ready-route2-st-provenance/source"
    source_checks = []
    for row in base["source_inventory"]:
        path = row["path"]
        assert digest(archive / path) == row["actual_8a_sha256"], path
        current = ROOT / path
        if path in HOOKS:
            expected = HOOKS[path]
            reason = "Minimal reviewed escort/owner-only companion/zero-floor/pre-spawn cursor bridge; exact hash."
        elif path == f"config/veloren/tasks/structured_tools/{TASK}.yaml":
            expected = TASK_HASHES["structured_tools"]
            reason = "Exact reviewed task newly registered, not a changed goal."
        else:
            expected = row["current_main_sha256"]
            reason = reasons.get(path, "Exact executed-source bytes.")
        if path == "agent_framework/agents/deepseek_harness/setup.py":
            current_hash = hashlib.sha256(git("show", f"{head}:{path}")).hexdigest()
            reason += " Unrelated dirty working override is excluded; committed main factory import only."
        else:
            current_hash = digest(current) if current.exists() else None
        assert current_hash == expected, f"Unreviewed bridge delta: {path}"
        source_checks.append({"path": path, "executed_sha256": row["actual_8a_sha256"],
                              "main_sha256": expected, "bridge": reason})
    for path, expected in base["current_main_selected_source_pins"].items():
        assert digest(ROOT / path) == HOOKS.get(path, expected), path

    # Import the committed unused Agent factory module, never the unrelated dirty override.
    setup_name = "agent_framework.agents.deepseek_harness.setup"
    setup_path = "agent_framework/agents/deepseek_harness/setup.py"
    setup_module = ModuleType(setup_name)
    setup_module.__file__ = str(ROOT / setup_path)
    setup_module.__package__ = setup_name.rpartition(".")[0]
    sys.modules[setup_name] = setup_module
    exec(compile(git("show", f"{head}:{setup_path}"), setup_module.__file__, "exec"), setup_module.__dict__)
    sys.path.insert(0, str(ROOT))
    from benchmark.config import load_task
    from benchmark.factory import make_game
    from game.veloren.runtime.session import runtime_configuration
    from game.veloren.runtime.workstation import expected_route_schema
    from game.veloren.structured_tools import interface
    from game.veloren.evaluators.team_efficiency import team_efficiency

    assert digest(runtime_path) == RUNTIME, "Only the exact f90 artifact is supported"
    runtime = read(runtime_path)
    for path, expected in runtime["sha256"].items():
        assert digest(path) == expected, path
    manifest_path = Path(runtime["local_source_manifest"])
    manifest = read(manifest_path)
    for path, expected in manifest["files_sha256"].items():
        assert digest(Path(manifest["source_root"]) / path) == expected, path
    upstream_path = Path(runtime["upstream_runtime"])
    assert digest(upstream_path) == runtime["upstream_sha256"]
    upstream = read(upstream_path)
    content_path = upstream_path.parent / upstream["content"]["path"]
    assert digest(content_path) == upstream["content"]["sha256"]
    server = upstream_path.parent / upstream["renderer"]["server"]
    assert digest(server) == read(content_path)["renderer"]["server_sha256"]
    from game.veloren.runtime.server_extension import select_server
    assert select_server(runtime, server) == server
    run = DEV / "veloren-interaction/VE-C05-public-sharing-escort-v3-capacity-ready-route2-st"
    result = read(run / "result.json")
    assert (result["status"], result["measurement"], result["task_outcome"]) == ("completed", "valid", "failure")
    registrations, task_pins = {}, {}
    for track, expected in TASK_HASHES.items():
        path = ROOT / f"config/veloren/tasks/{track}/{TASK}.yaml"
        assert digest(path) == expected
        task_pins[track] = pin(path)
        task = load_task(path)
        with patch.dict(os.environ, {"LIVEQUEST_VELOREN_RUNTIME": str(runtime_path)}):
            selected, configured = runtime_configuration(task.fixture)
        assert selected == runtime_path and configured == runtime
        assert expected_route_schema(task.fixture, runtime) == "native-client-route/2"
        assert not set(task.fixture) & {
            "runtime_profile", "message_contract", "market", "pickup_evidence",
            "route_observation", "camera_observation", "scene_observation",
        }
        binding = make_game(task, DEV / "checks/c05-not-started-registration" / track,
                            headless=True, recording=False, recording_fps=5)
        assert binding.game.phase == "new"
        assert not binding.game.output_dir.exists()
        assert list(binding.game.members) == ["Alpha", "Beta"]
        assert binding.game.members["Alpha"].game.fixture["companion"] == task.fixture["companion"]
        assert "companion" not in binding.game.members["Beta"].game.fixture
        binding.verify_initial(run / "before")
        evaluation = binding.evaluate(run / "before", run / "after")
        metrics = binding.metrics(run / "before", run / "after")
        assert evaluation == result["evaluation"] and metrics == result["metrics"]
        public_tools = {}
        for role in binding.game.members:
            member_game = binding.game.members[role].game
            try:
                member_game.get_agent_interface()
            except RuntimeError as error:
                assert str(error) == "Game interface requires initialized play"
            else:
                raise AssertionError("Unstarted game exposed its interface")
            with patch.object(member_game, "get_agent_interface", return_value=member_game._interface):
                controls, tools = binding.game.controls(role)
            from game.base_game import AgentAccessClosed
            try:
                asyncio.run(controls.observe())
            except AgentAccessClosed:
                pass
            else:
                raise AssertionError("Unstarted game allowed an observation")
            names = {tool.name for tool in tools}
            assert names == (set(task.tools) if task.tools is not None else {"action"})
            public_tools[role] = sorted(names)
        registrations[track] = {
            "constructed_without_start": True, "initial_validation": "passed for both archived roles",
            "full_frozen_scorer_equal": True, "full_frozen_metrics_equal": True,
            "replayed_success": evaluation["success"], "controls": public_tools,
            "companion_owner_only": True,
            "control_enumeration_scope": "Getter alone mocked to return the constructor-created interface for offline tool enumeration; actual new-phase getter and observation remain closed. No phase change, native transport or OS input.",
        }
    assert team_efficiency(run / "before", run / "after", ["Alpha", "Beta"]) == result["metrics"]["native_efficiency"]
    legacy = ModuleType("executed_c05_interface")
    exec(compile(git("show", f"{SOURCE}:game/veloren/structured_tools/interface.py"),
                 "executed-c05-interface", "exec"), legacy.__dict__)
    st_task = load_task(ROOT / task_pins["structured_tools"]["path"])
    names = set(st_task.tools) - {"BroadcastTool", "ChatTool"}
    assert all(interface.SPECS[name] == legacy.SPECS[name] for name in names)
    conversions = Counter()
    for role in ("Alpha", "Beta"):
        for row in map(json.loads, (run / f"{role}-public.jsonl").read_text().splitlines()):
            if row.get("tool") in names:
                tool = row["tool"]
                assert interface.validate_tool(tool, row["arguments"]) == legacy.validate_tool(tool, row["arguments"])
                conversions[tool] += 1
    assert sum(conversions.values()) == 294
    worker_path = "game/veloren/runtime/worker.py"
    worker, old_worker = (ROOT / worker_path).read_text(), git("show", f"{SOURCE}:{worker_path}")
    for name in ("frame_fence", "physical"):
        assert symbol(worker, name) == symbol(old_worker, name)
    for operation in ("begin", "end"):
        assert branch(worker, operation) == branch(old_worker, operation)
    assert 'raise PermissionError("VM cannot invoke native skills")' in worker
    assert 'os.environ["LIVEQUEST_PHYSICAL_INPUT"] = "1" if self.track == "visual_motor" else "0"' in worker
    assert symbol((ROOT / "game/team.py").read_text(), "controls") == symbol(
        git("show", f"{SOURCE}:game/team.py"), "controls")
    assert (ROOT / "game/veloren/visual_motor/interface.py").read_bytes() == git(
        "show", f"{SOURCE}:game/veloren/visual_motor/interface.py")
    assert symbol((ROOT / "game/veloren/evaluators/encounter.py").read_text(), "evaluate_escort") == symbol(
        git("show", f"{SOURCE}:game/veloren/evaluators/encounter.py"), "evaluate_escort")
    audit = read(DEV / "checks/veloren-acceptance-policy-audit-20261029.json")
    review_pins = {}
    for index, expected in {
        64: "ff15e88ee4680e3039070b032ec14c749f82060ed7b00f0af6219b1306db59be",
        67: "c5cafbe777b6c71e09158f2f5ca6bb4320a88d08965ba37ff5b042300f41cbe3",
    }.items():
        assert canonical(audit["dated_addenda"][index]) == expected
        review_pins[str(index)] = expected
    production = {**HOOKS, **{row["path"]: row["sha256"] for row in task_pins.values()}}
    if require_committed:
        for path, expected in production.items():
            assert hashlib.sha256(git("show", f"{head}:{path}")).hexdigest() == expected, path
    assert git("rev-parse", "HEAD").decode().strip() == head
    return {
        "schema": "C05-exact-main-admission/1", "task_id": "VE-C05", "passed": True,
        "main_parent": PARENT, "checked_head": head, "production_required_committed": require_committed,
        "reviewed_source": SOURCE, "checker": pin(__file__), "production_pins": production,
        "task_pins": task_pins, "supported_tracks": ["structured_tool", "visual_motor"],
        "quality_review_canonical_pins": review_pins,
        "source_checks": source_checks, "prepared_delta_classification": pin(classified_path),
        "supported_runtime": {**pin(runtime_path), "dependencies_verified": len(runtime["sha256"]),
                              "compiled_sources_verified": len(manifest["files_sha256"]),
                              "source_manifest": pin(manifest_path), "upstream": pin(upstream_path),
                              "server": pin(server), "route_schema": "native-client-route/2"},
        "registrations": registrations, "actual_conversions_equal": dict(conversions),
        "permissions_lifecycle": "Executed-source AST equality for native frame/physical fence and begin/end; same Team.controls, VM interface, physical-input track gate and VM semantic-action denial. No setup/native skill permission broadened.",
        "startup": "Existing off-thread bounded combat cursor is warmed before pet spawn. Focused test proves order and fail-closed binding failure. No fresh-main native timing or loaded-process attestation claimed; original1088.500509s initialization remains historical.",
        "full_frozen_result": pin(run / "result.json"), "actual_native_success": False,
        "native_or_model_runs": 0, "controller_c717_included": False,
        "unrelated_dirty_source_scope": "Committed HEAD DeepSeek factory setup is loaded in memory only for unused imports; unrelated dirty working override is neither executed nor changed. Qualification is committed source plus these exact hooks, not arbitrary dirty main contents.",
        "limits": "Exact sheltered version and explicit f90 only. ST actual133.584656 failure and old exposed VM failures retained. Q/VM construction is not an observed victory. Cooperation2(2-3) and overall3(2-4), high calibration uncertainty. Ledger adoption requires actual commit plus independent frozen-bridge signoff.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-committed", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    report = check(args.runtime.resolve(), args.require_committed)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(pin(args.output.resolve())))


if __name__ == "__main__":
    main()
