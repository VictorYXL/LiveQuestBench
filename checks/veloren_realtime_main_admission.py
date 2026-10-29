"""Authenticate frozen realtime evidence against main without starting a game."""

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import yaml

from benchmark.config import load_task
from benchmark.factory import make_game
from game.veloren.evaluators.encounter import evaluate_encounter
from game.veloren.evaluators.encounter_supplies import evaluate_encounter_supplies
from game.veloren.fixture import native_authoring_order, solid_voxels
from game.veloren.runtime.server_extension import select_server
from game.veloren.structured_tools.interface import COMBAT_TOOLS, EXPEDITION_TOOLS, SPECS


ROOT = Path(__file__).resolve().parents[1]
FROZEN = "57fe49c143909d257ef6acdd3ef02afba95ac8d3"
PACKET = "output/temp/task_development/checks/resume-realtime-composition-offline-v4-20261029.json"
PACKET_SHA = "d894c629d4e76a9a5bd637f2a9d9adc75a878f6d839cf25d9a2970637548f0a0"
RUNTIMES = {
    "route2": (
        "output/temp/task_development/veloren-route-v2-contact-fix/candidate-runtime.json",
        "f90ca9a97e20a106e6d749368319cdd45243a2f902605e7797c6f8e3613c3793",
    ),
    "route2_pickups": (
        "output/engineering/veloren-realtime-runs/route2-pickups-runtime.json",
        "47e3460c6cac0bd51fd1dce5fa8c000d76be71d8a63771fe457ccc3a236468d8",
    ),
}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def frozen(path):
    return subprocess.check_output(["git", "show", f"{FROZEN}:{path}"], cwd=ROOT).decode()


def tree(source):
    return ast.parse(source)


def normalized(source, omitted=()):
    value = tree(source)
    value.body = [node for node in value.body if getattr(node, "name", None) not in omitted]
    return ast.dump(value, include_attributes=False)


class BindingBridge(ast.NodeTransformer):
    def visit_If(self, node):
        node = self.generic_visit(node)
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "evaluator" and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value in ("active_build", "harvest")):
            return node.orelse
        return node

    def visit_Tuple(self, node):
        node.elts = [child for child in node.elts
                     if not (isinstance(child, ast.Constant) and child.value == "active_build")]
        return self.generic_visit(node)


class AuthoringBridge(ast.NodeTransformer):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "native_authoring_order":
            assert ast.dump(node.args[0]) == ast.dump(ast.Name(id="additional", ctx=ast.Load()))
            return ast.parse("[list(point) for point in sorted(additional)]", mode="eval").body
        return self.generic_visit(node)


def adapter_bridge(directory):
    archive = json.loads((directory / "source-manifest.json").read_text())
    allowed = {
        "fixture.py": "Same authored voxel set; retained main's clustered, bottom-up setup order.",
        "binding.py": "Retained active_build/harvest branches and active_build role guard; these tasks select neither.",
        "settlement.py": "Retained merchant final-quote preparation; these tasks declare no merchant.",
        "evaluators/route_transfer.py": "Retained stronger route min-health validation; these tasks do not use that scorer.",
        "evaluators/encounter.py": "Retained team min-health forwarding; all non-team scorer code is AST-identical.",
    }
    changed, equal, hashes = {}, [], {}
    for relative, expected in archive.items():
        path = ROOT / "game/veloren" / relative
        assert digest(directory / "python-source" / relative) == expected
        assert hashlib.sha256(frozen(str(path.relative_to(ROOT))).encode()).hexdigest() == expected
        hashes[str(path.relative_to(ROOT))] = digest(path)
        if digest(path) == expected:
            equal.append(relative)
        else:
            assert relative in allowed, relative
            changed[relative] = {
                "archived_sha256": expected, "main_sha256": digest(path), "explanation": allowed[relative],
                "diff": subprocess.check_output(
                    ["git", "diff", FROZEN, "--", str(path.relative_to(ROOT))], cwd=ROOT, text=True),
            }
    assert set(changed) == set(allowed)
    for relative, omitted in (
        ("evaluators/encounter.py", ("team_encounter_checks",)),
        ("settlement.py", ("initialize_merchant", "final_quote_trade")),
    ):
        path = f"game/veloren/{relative}"
        assert normalized((ROOT / path).read_text(), omitted) == normalized(frozen(path), omitted)
    path = "game/veloren/binding.py"
    assert ast.dump(BindingBridge().visit(tree((ROOT / path).read_text()))) == ast.dump(tree(frozen(path)))
    path = "game/veloren/fixture.py"
    actual = AuthoringBridge().visit(tree((ROOT / path).read_text()))
    actual.body = [node for node in actual.body if getattr(node, "name", None) != "native_authoring_order"]
    assert ast.dump(actual) == ast.dump(tree(frozen(path)))
    return {"unchanged_archived_files": equal, "affected_deltas": changed, "main_source_hashes": hashes}


def check(output):
    assert digest(ROOT / PACKET) == PACKET_SHA
    packet = json.loads((ROOT / PACKET).read_text())
    report = {
        "schema": "livequest-realtime-main-bridge/1", "frozen_review_source": FROZEN,
        "frozen_packet": {"path": PACKET, "sha256": PACKET_SHA},
        "scope": "Offline current-main binding/scorer/source/runtime authentication. No current-main native episode, "
                 "model measurement or reconstruction of historical loaded Python is claimed.",
        "tasks": {}, "runtimes": {},
    }
    for stable_id, evidence in packet["historical_witnesses"].items():
        tasks = [ROOT / path for path in evidence["task_sha256"]]
        for path in tasks:
            assert digest(path) == evidence["task_sha256"][str(path.relative_to(ROOT))]
            assert path.read_text() == frozen(str(path.relative_to(ROOT)))
        definitions = [yaml.safe_load(path.read_text()) for path in tasks]
        for field in ("fixture", "evaluator", "time_limit_seconds"):
            assert definitions[0][field] == definitions[1][field]
        fixture = definitions[0]["fixture"]
        assert not any(key in fixture for key in ("merchant", "native_site", "peer_group"))
        for path in tasks:
            task = load_task(path)
            make_game(task, output.parent / "realtime-main-bindings" / stable_id / path.parent.name,
                      headless=True, recording=False, recording_fps=5)
        extra = solid_voxels(fixture) - solid_voxels({**fixture, "blocks": []})
        ordered = native_authoring_order(extra)
        assert len(ordered) == len(extra) and set(map(tuple, ordered)) == extra
        directory = ROOT / evidence["directory"]
        for phase, expected in evidence["snapshot_sha256"].items():
            assert digest(directory / phase / "observation.json") == expected
        assert digest(directory / "game/environment.json") == evidence["environment_sha256"]
        scorer = evaluate_encounter_supplies if stable_id == "VE-R05" else evaluate_encounter
        replay = scorer(directory / "before", directory / "after", **definitions[0]["evaluator"]["parameters"])
        assert replay == evidence["current_VM_scorer_replay"] and replay["success"]
        report["tasks"][stable_id] = {
            "task_sha256": evidence["task_sha256"], "current_main_scorer_replay": replay,
            "six_bindings_constructed_without_start": True, "authored_voxel_count": len(extra),
            "same_fixture_evaluator_budget": True, "frozen_native_directory": evidence["directory"],
        }
    assert SPECS["SwapWeaponsTool"][1:] == ("swap_weapons", {})
    assert "SwapWeaponsTool" not in COMBAT_TOOLS and "SwapWeaponsTool" not in EXPEDITION_TOOLS
    fresh = ROOT / packet["historical_witnesses"]["VE-R05"]["directory"]
    report["adapter_bridge"] = adapter_bridge(fresh)
    report["R05_whole_task"] = deepcopy(packet["R05_fresh_conjunction"])
    assert digest(fresh / "result.json") == report["R05_whole_task"]["result_sha256"]
    for label, (relative, expected) in RUNTIMES.items():
        path = ROOT / relative
        assert digest(path) == expected
        config = json.loads(path.read_text())
        for name, sha in config["sha256"].items():
            assert digest(name) == sha, name
        loader = (
            "import json,sys; from pathlib import Path; from scripts.rpg_benchmark import runtime; "
            "print(json.dumps(runtime.load_runtime(Path(sys.argv[1]),sys.argv[2],"
            "backend='renderer')['renderer']['paths']))"
        )
        selected = json.loads(subprocess.check_output(
            [config["python"], "-c", loader, config["upstream_runtime"], config["upstream_sha256"]],
            cwd=ROOT, text=True,
        ))
        server = select_server(config, Path(selected["server"]))
        manifest = json.loads(Path(config["local_source_manifest"]).read_text())
        for name, sha in manifest["files_sha256"].items():
            assert digest(Path(manifest["source_root"]) / name) == sha, name
        report["runtimes"][label] = {
            "path": relative, "sha256": expected, "authenticated_artifact_pins": len(config["sha256"]),
            "compiled_source_files_verified": len(manifest["files_sha256"]),
            "selected_server": str(server), "selected_server_sha256": digest(server),
            "renderer_sha256": digest(config["renderer"]),
            "composition": config.get("runtime_composition"),
        }
    report["limitations"] = {
        "VE-R03": "Retain 449s/3-death VM failure and unavailable historical loaded-source reconstruction.",
        "VE-R04": "Retain 150s and 116s VM failures; ~4s means cumulative effective beam contact, not tracking "
                  "or wall-clock completion. Public102s frame, terminal150s geometry and128s safety interval "
                  "are chronologically distinct; dynamic reacquisition and original-pet reunion are constructive.",
        "VE-R05": "Full runtime47e346 includes route2+pickup. Original55HP, original3-stock and actual bow lethal "
                  "with living return were witnessed; zero deaths, no tested respawn branch; no fresh VM win.",
        "quality": "Independent basic realtime support only; difficulty2-4 remains high-uncertainty, calibration deferred.",
    }
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.output)
    print(json.dumps({"tasks": list(result["tasks"]), "current_main_replays": 3,
                      "new_native_or_model_jobs": 0, "source_bridge": "verified"}))
