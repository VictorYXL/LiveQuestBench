"""Verify exact C04 registration, retained evidence and runtime bridge without gameplay."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.config import load_task
from benchmark.factory import make_game
from game.veloren.runtime.composition import compose
from game.veloren.runtime.server_extension import select_server
from game.veloren.structured_tools import interface


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def frozen(path):
    return subprocess.check_output(
        ["git", "show", f"18721b954766825af7c70e00118823a1266534f7:{path}"], cwd=ROOT)


def controls(source):
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TeamGame")
    return ast.dump(next(node for node in cls.body if getattr(node, "name", None) == "controls"))


def verify(evidence_root):
    document = ROOT / "docs/evidence/ridge_scout_ground_team_admission.json"
    admission = json.loads(document.read_text())
    checks = evidence_root / "output/temp/task_development/checks"
    review = json.loads((checks / "veloren-acceptance-policy-audit-20261029.json").read_text())["dated_addenda"][36]
    assert canonical(review) == admission["review"]["entry_sha256"]
    assert digest(checks / "VE-C04-limited-coordination-closure.json") == admission["review"]["packet_sha256"]
    bridge_path = checks / "VE-C04-main-bridge-probe-result.json"
    assert digest(bridge_path) == admission["source_bridge"]["receipt_sha256"]
    bridge = json.loads(bridge_path.read_text())
    pins = dict(bridge["current_main_source_pins"])
    pins["game/team.py"] = bridge["proposed_binding"]["projected_team_py_sha256"]
    for path, expected in pins.items():
        assert digest(ROOT / path) == expected, path
    tasks, bindings = {}, {}
    for track, pin in admission["task_pins"].items():
        path = ROOT / pin["path"]
        assert digest(path) == pin["sha256"]
        task = load_task(path)
        assert task.id == "ridge_scout_ground_team" and task.time_limit_seconds == 2700
        assert task.evaluator_parameters["source_supplies"] == [
            {"item": "common.items.crafting_ing.leather.simple_leather", "amount": 4}]
        assert "peer_group" not in task.fixture
        tasks[track] = task
        bindings[track] = make_game(
            task, checks / "VE-C04-never-launched", headless=True,
            recording=False, recording_fps=5)

    evidence = evidence_root / "output/temp/task_development/veloren-interaction"
    replays = {}
    for run, expected in bridge["saved_snapshot_replays"].items():
        directory = evidence / run
        assert digest(directory / "result.json") == expected["result_sha256"]
        saved = json.loads((directory / "result.json").read_text())
        track = "visual_motor" if run.endswith("-vm") else "structured_tools"
        archived = json.loads((directory / "task.json").read_text())["source"]
        assert hashlib.sha256(archived["content"].encode()).hexdigest() == tasks[track].source.sha256
        actual = bindings[track].evaluate(directory / "before", directory / "after")
        assert actual == saved["evaluation"] and actual["success"] is expected["success"], run
        try:
            bindings[track].metrics(directory / "before", directory / "after")
        except ValueError as error:
            assert str(error) == "Native route identity or schema mismatch", str(error)
        else:
            raise AssertionError("Historical route/1 metrics must not be relabeled route/2")
        replays[run] = {
            "result_sha256": expected["result_sha256"], "evaluation_equal": True,
            "success": actual["success"], "historical_route1_metrics_rejected": True,
        }

    old = types.ModuleType("c04_retained_interface")
    exec(compile(frozen("game/veloren/structured_tools/interface.py"), "retained-interface", "exec"), old.__dict__)
    names = [name for name in tasks["structured_tools"].tools if name not in ("BroadcastTool", "ChatTool")]
    assert all(interface.SPECS[name] == old.SPECS[name] for name in names)
    conversions = 0
    for role in ("Alpha", "Beta"):
        for line in (evidence / "VE-C04-independent-defended-st" / f"{role}-public.jsonl").read_text().splitlines():
            row = json.loads(line)
            if row.get("tool") in names:
                assert interface.validate_tool(row["tool"], row["arguments"]) == old.validate_tool(row["tool"], row["arguments"])
                conversions += 1
    assert conversions == 139
    assert controls((ROOT / "game/team.py").read_text()) == controls(frozen("game/team.py"))
    motor = "game/veloren/visual_motor/interface.py"
    assert (ROOT / motor).read_bytes() == frozen(motor)

    runtime_path = evidence_root / admission["supported_runtime"]["path"]
    assert digest(runtime_path) == admission["supported_runtime"]["sha256"]
    runtime = json.loads(runtime_path.read_text())
    assert runtime["route_evidence"] == "native-client-route/2"
    assert runtime["pickup_evidence"] == "native-server-pickups/1"
    assert "experimental_item_use_admission" not in runtime
    manifests = runtime["runtime_composition"]
    assert compose(Path(manifests["client_runtime"]), Path(manifests["server_runtime"])) == runtime
    upstream = Path(runtime["upstream_runtime"])
    native_server = Path(json.loads(upstream.read_text())["renderer"]["server"])
    if not native_server.is_absolute():
        native_server = upstream.parent / native_server
    selected = select_server(runtime, native_server)
    source = json.loads(Path(runtime["local_source_manifest"]).read_text())
    for path, expected in source["files_sha256"].items():
        assert digest(Path(source["source_root"]) / path) == expected, path
    return {
        "schema": "livequest-c04-main-admission/1", "task_id": "VE-C04", "passed": True,
        "head_at_check": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "main_parent": admission["source_bridge"]["main_parent"],
        "checker_sha256": digest(Path(__file__)), "document_sha256": digest(document),
        "review": {"path": str(checks / "veloren-acceptance-policy-audit-20261029.json"),
                   "entry": 36, "entry_sha256": canonical(review)},
        "task_pins": admission["task_pins"], "source_pins": pins,
        "saved_snapshot_replays": replays,
        "actual_st_action_conversions_equal": conversions,
        "team_chat_controls_equal": True, "vm_controls_equal": True,
        "registration": "Both exact task YAMLs load and actual main bindings construct without start.",
        "supported_runtime": {
            **admission["supported_runtime"], "renderer_sha256": digest(runtime["renderer"]),
            "server_sha256": digest(selected), "artifact_pins_verified": len(runtime["sha256"]),
            "compiled_client_sources_verified": len(source["files_sha256"]),
        },
        "historical_formal_outcomes": {"st": "valid success", "vm": "valid failure"},
        "native_episodes": 0, "model_calls": 0,
        "limits": admission["limits"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.evidence_root.resolve())
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "receipt": str(args.output)}))
