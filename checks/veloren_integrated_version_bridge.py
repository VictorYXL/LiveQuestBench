"""Read-only, six-task archived-native reconciliation; never launches a game."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.endpoints import load_pair, state_checks
from game.veloren.fixture import verify_player, verify_aged_supplies
from game.veloren.runtime.server_extension import select_server
from game.veloren.structured_tools import interface as public

DEV = ROOT / "output/temp/task_development"
IDS = ("VE-I05", "VE-P02", "VE-P04", "VE-P05", "VE-R02", "VE-S02")


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def pin(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
            "sha256": digest(path)}


def ast_members(data):
    tree = ast.parse(data)
    return {n.name: ast.dump(n, include_attributes=False) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def delta(commit, path):
    new = git("show", f"HEAD:{path}")
    assert digest(ROOT / path) == hashlib.sha256(new).hexdigest(), path
    try:
        old = git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return {"old_sha256": None, "current_sha256": hashlib.sha256(new).hexdigest(),
                "change": "new module"}
    a, b = ast_members(old), ast_members(new)
    return {"old_sha256": hashlib.sha256(old).hexdigest(),
            "current_sha256": hashlib.sha256(new).hexdigest(),
            "byte_identical": old == new,
            "changed_top_level_symbols": sorted(k for k in a.keys() | b.keys()
                                                if a.get(k) != b.get(k))}


def one(root, pattern):
    paths = list(root.glob(pattern))
    assert len(paths) == 1, (root, pattern, paths)
    return paths[0]


def runtime_check(path):
    cfg = load(path)
    checked = []
    for name, expected in cfg["sha256"].items():
        assert digest(name) == expected, name
        checked.append(pin(name))
    assert digest(cfg["upstream_runtime"]) == cfg["upstream_sha256"]
    server = subprocess.check_output([
        cfg["python"], "-c",
        "import json,sys; from pathlib import Path; from scripts.rpg_benchmark import runtime; "
        "c=json.loads(Path(sys.argv[1]).read_text()); "
        "r=runtime.load_runtime(Path(c['upstream_runtime']),c['upstream_sha256'],backend='renderer'); "
        "print(r['renderer']['paths']['server'])", str(path)], text=True).strip()
    selected = select_server(cfg, Path(server))
    return {**pin(path), "constituents_verified": checked,
            "upstream": pin(cfg["upstream_runtime"]), "selected_server": pin(selected),
            "renderer": pin(cfg["renderer"]), "upstream_loader_and_server_selection": "pass",
            "route_capability": cfg.get("route_evidence"), "glide_capability": cfg.get("glide_evidence"),
            "native_protection": cfg["native_protection"],
            "fresh_native_execution": False}, cfg


def main():
    head = git("rev-parse", "HEAD").decode().strip()
    inventory = load(DEV / "checks/task-delivery-status.json")
    quality = load(DEV / "checks/veloren-independent-quality.json")
    report = {
        "schema": "livequest-integrated-veloren-version-bridge/1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "head": head,
        "scope": list(IDS), "excluded": ["VE-S03", "VE-S04", "VE-L01", "unqualified new tasks"],
        "method": "Actual archived endpoints evaluated by exact current-main binding; no reconstructed fields, no changed historical verdicts, no fresh native/model execution.",
        "inventory_snapshot": pin(DEV / "checks/task-delivery-status.json"),
        "independent_review": pin(DEV / "checks/veloren-independent-quality.json"),
        "frozen_manifest": pin(ROOT / "docs/reference_tasks_manifest.json"),
        "scoring_revision": "9a55a7172abc2be25c21b44d5fe173bff451439b",
        "route_observer_revision": "5619e1663f4775dca258786480fb12dffa2b4f92",
        "scoring_changed_cases": "state_checks now also rejects health.downed is True. No default floor change: omitted=1; explicit 0 still strictly positive and nondead; explicit reserves unchanged. No absent downed field is used as evidence of false in this bridge.",
        "runtime_policy": "Explicitly select the per-task checksum-pinned historical runtime with LIVEQUEST_VELOREN_RUNTIME. Neither default runtime nor route/2 renderer is newly gameplay-qualified.",
        "route_boundary": "All six fixtures leave route_evidence disabled. worker.start route/2 requirement and private route capture are conditional. S02 uses native-client-glide/1 and state.glide_landing, not itinerary/route_transfer or route/2 contact physics.",
        "runtimes": {}, "tasks": [],
        "compatibility_review": [
            "Compared frozen task commits and actual fixture records, not current mutable source worktrees. Paired task bytes are unchanged; actual native world bytes, endpoint identities and clocks verified.",
            "The state scorer delta is strictly-positive/nondead/downed guarding; P04/P05 retain explicit75 reserve. Existing older P02 reference scorer had minimum1, final integrated contract explicitly0; successes at100 remain successes but historical evaluation objects remain unchanged.",
            "Single-player setup still initializes supplies once before readiness. Extracted initialize_supplies/bind_supplies preserve operations; defer paths require team_role. Native authoring order groups the same voxel set, before gameplay. Current remote-supply age check uses max clocks conservatively; all retained openings pass it.",
            "Current energy/peer/companion/encounter paths are not enabled. Existing I05 collect/terrain and R02 pickup evidence are enabled and preserved. Harvest and pickup scorers are byte-identical to their qualified sources; all actual evidence replays pass.",
            "ST action names/argument schemas and ordinary public endpoint projections compared against frozen task source; VM still exposes only public keyboard/mouse controls, never private endpoints. Session RPC, VM interface and death scorer hashes compared explicitly.",
            "Merchant final-quote readiness is bounded setup-only, not a goal change. P02/P05 ordinary native selection remains supported; optional initial-selection fallback not imported. Exceptional final decline-reopen is not native-qualified by these ordinary witnesses.",
            "Route1 runtime sha map pins unchanged patch0006, not new patch0008. All constituents and upstream renderer loader/server-selection paths verified. No route2 source-pin bypass, no runtime rewrite.",
            "Journal validated-prefix optimization is only enabled by peer Group setup; all six are single-player with prefix=None. Pickup retention remains unchanged for R02. start_setup_bridge reconnect=False performs one ordinary setup start; retry only attached/deferred paths. Xvfb -noreset preserves clients between capture connections, not gameplay inputs.",
        ],
        "validation": {
            "focused_offline_tests": "127 passed, 2 deselected",
            "log": pin(ROOT / "checks/veloren-version-bridge-tests.log"),
            "command": ".venv/bin/python -m pytest -q -m 'not game and not live' tests/test_game/veloren/test_evaluators.py tests/test_game/veloren/test_qualified_tasks.py tests/test_game/veloren/test_harvest.py tests/test_game/veloren/test_pickups.py tests/test_game/veloren/test_server_extension.py tests/test_game/veloren/test_merchant_readiness.py tests/test_game/veloren/test_journal.py tests/test_game/veloren/test_authoring_order.py tests/test_game/veloren/test_fixture_records.py tests/test_game/veloren/test_game.py --basetemp=output/test/veloren-version-bridge-final",
            "new_game_or_model_episodes": 0,
            "replay_script": pin(Path(__file__)),
            "replay_command": ".venv/bin/python -c \"import runpy;runpy.run_path('checks/veloren_integrated_version_bridge.py',run_name='__main__')\"",
        },
        "supporting_integrations": [pin(ROOT / name) for name in (
            "docs/evidence/qualified-veloren-task-integration.json",
            "docs/evidence/spatial-task-integration.json",
            "docs/evidence/merchant_loadout_admission.json",
            "docs/evidence/veloren-alive-contract-v2-integration.json",
            "docs/evidence/veloren-route2-observer-contact-fix.json",
        )],
    }
    for key, path in {
        "route1": ROOT / "output/temp/veloren-native-route-20261027/runtime.json",
        "pickups": DEV / "veloren-interaction/native-pickups/runtime.json",
    }.items():
        receipt, cfg = runtime_check(path)
        report["runtimes"][key] = receipt
    for code in IDS:
        inv = next(t for t in inventory["tasks"] if t["stable_id"] == code)
        review = next(t for t in quality["tasks"] if t["task_key"] == code)
        assessment_path = DEV / "assessments" / f"{code}.json"
        assessment = load(assessment_path)
        commit = inv["exact_source"]["frozen_candidate_or_review_commit"]
        frozen_public = types.ModuleType("frozen_public_" + code.replace("-", "_"))
        exec(compile(git("show", f"{commit}:game/veloren/structured_tools/interface.py"),
                     f"{commit}:interface.py", "exec"), frozen_public.__dict__)
        row = {
            "stable_id": code, "task_id": inv["task_id"],
            "canonical_assessment": pin(assessment_path),
            "source_commit": commit, "prior_category": inv["category"],
            "integrated_commit": assessment.get("integrated_commit", assessment.get("integrated_commits")),
            "prior_reason": inv["reason"], "current_release_condition": {},
            "qualityreview": {k: review[k] for k in (
                "status", "construct_findings", "difficulty", "engineering_blockers", "limits")},
            "source_deltas": {}, "tracks": [], "gates": [],
        }
        sources = [
            "game/veloren/evaluators/endpoints.py", "game/veloren/evaluators/deaths.py",
            "game/veloren/binding.py", "game/veloren/fixture.py", "game/veloren/game.py",
            "game/veloren/runtime/worker.py", "game/veloren/runtime/session.py",
            "game/veloren/runtime/records.py", "game/veloren/runtime/server_extension.py",
            "game/veloren/runtime/journal.py", "game/veloren/runtime/startup.py",
            "game/veloren/runtime/server.py", "game/veloren/native_bindings.py",
            "game/veloren/structured_tools/interface.py", "game/veloren/visual_motor/interface.py",
            "game/veloren/settlement.py",
            "game/backends/x11/display.py", "game/backends/x11/interface.py",
            "game/bindings.py", "benchmark/runner.py",
        ]
        if code == "VE-I05":
            sources += ["game/veloren/evaluators/harvest.py", "game/veloren/harvest.py"]
        if code == "VE-R02":
            sources += ["game/veloren/evaluators/pickups.py"]
        for source in sources:
            row["source_deltas"][source] = delta(commit, source)
        for track, directory in (("st", "structured_tools"), ("vm", "visual_motor")):
            task_path = ROOT / "config/veloren/tasks" / directory / f"{inv['task_id']}.yaml"
            task = load_task(task_path)
            old = git("show", f"{commit}:{task_path.relative_to(ROOT)}")
            assert task_path.read_bytes() == old
            assert not task.fixture.get("route_evidence", False)
            runtime_key = "pickups" if code == "VE-R02" else "route1"
            cfg = load(ROOT / report["runtimes"][runtime_key]["path"])
            if task.fixture.get("glide_evidence"):
                assert cfg["glide_evidence"] == "native-client-glide/1"
            if task.fixture.get("pickup_evidence"):
                assert cfg["pickup_evidence"] == "native-server-pickups/1"
            binding = create_binding(
                fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
                parameters=task.evaluator_parameters, tools=task.tools,
                output_dir=ROOT / "checks/unused-native-output" / code / track,
                headless=True, recording=False, recording_fps=10,
            )
            binding.game.phase = "ready"
            _, controls = binding.controls()
            allowed = sorted(t.name for t in controls)
            assert track == "st" or not set(allowed) & set(public.SPECS)
            if track == "st":
                for name in task.tools:
                    assert public.SPECS[name][1:] == frozen_public.SPECS[name][1:]
            row["current_release_condition"][track] = {
                "task": pin(task_path), "task_byte_identical_to_review_commit": True,
                "fixture_world": pin(task.fixture["world_path"]),
                "evaluator": task.evaluator, "parameters": task.evaluator_parameters,
                "route_requested": False, "runtime": runtime_key, "public_controls": allowed,
                "admission": "pass_without_game_start",
            }
            for kind in ("native_feasibility", "formal_measurement"):
                evidence = inv["tracks"][track][kind]
                base = Path(evidence.get("path", evidence.get("result_path")))
                base = base if base.is_absolute() else ROOT / base
                if base.is_file():
                    base = base.parent
                    if base.name == "results":
                        base = base.parent
                before_path = one(base, "**/before/observation.json").parent
                after_path = one(base, "**/after/observation.json").parent
                before, after = load_pair(before_path, after_path)
                for snap in (before, after):
                    assert type(snap["survival"]["health"]["downed"]) is bool
                    assert type(snap["survival"]["health"]["dead"]) is bool
                binding.verify_initial(before_path)
                evaluated = binding.evaluate(before_path, after_path)
                state_parameters = {k: v for k, v in task.evaluator_parameters.items()
                                    if k not in ("source_cells", "supplies")}
                if "supplies" in task.evaluator_parameters:
                    state_parameters["inventory"] = [
                        {"item": s["item"], "min_count": s["amount"]}
                        for s in task.evaluator_parameters["supplies"]]
                assert not state_checks(before, before, **state_parameters)["success"]
                expected = evidence.get("success", evidence.get("task_outcome", evidence.get("outcome")))
                expected = expected if type(expected) is bool else expected == "success"
                assert evaluated["success"] is expected, (code, track, kind, evaluated)
                fixture_path = one(base, "**/fixture.json")
                fixture = load(fixture_path)
                actual, wanted = dict(fixture["fixture"]), dict(task.fixture)
                assert digest(actual.pop("world_path")) == digest(wanted.pop("world_path"))
                assert actual == wanted, (code, track, kind, "fixture mismatch")
                verify_player(task.fixture, before)
                verify_aged_supplies(fixture, before)
                environment_path = fixture_path.parent / "environment.json"
                environment = load(environment_path)
                assert environment["runtime"] == cfg
                assert environment["track"] == task.task_type
                for snap in (before, after):
                    kwargs = {"rpg": any(k in task.fixture for k in ("native_site", "merchant", "contract"))}
                    assert public.project(snap, **kwargs) == frozen_public.project(snap, **kwargs)
                boundary_path = fixture_path.parent / "boundaries.json"
                clock = load(boundary_path)
                metas = [load(p / "_livequest_snapshot.json") for p in (before_path, after_path)]
                times = [clock["ready_at_ns"], metas[0]["capture_started_at_ns"],
                         metas[0]["captured_at_ns"], clock["begin_requested_at_ns"],
                         clock["begin_acknowledged_at_ns"], clock["end_requested_at_ns"],
                         clock["end_acknowledged_at_ns"], metas[1]["capture_started_at_ns"],
                         metas[1]["captured_at_ns"]]
                assert times == sorted(times)
                seconds = (clock["end_requested_at_ns"] - clock["begin_requested_at_ns"]) / 1e9
                assert seconds <= task.time_limit_seconds
                item = {
                    "track": track, "kind": kind, "archive": str(base.relative_to(ROOT)),
                    "current_success": evaluated["success"], "retained_outcome": expected,
                    "initial_state_success": False,
                    "evaluation": evaluated, "endpoint_integrity_identity_timestamps": "pass",
                    "fixture_world_opening_and_supply_age": "pass",
                    "actual_archived_runtime_equals_selected_supported_runtime": True,
                    "public_projection_equal_to_frozen_task_source": True,
                    "native_protocol_version": environment["actor"]["protocol_version"],
                    "health": [snap["survival"]["health"] for snap in (before, after)],
                    "session_id": before["session_id"], "self_identity": before["self_identity"],
                    "client_ticks": [before["tick"], after["tick"]], "active_seconds": seconds,
                    "pins": [pin(p / name) for p in (before_path, after_path)
                             for name in ("observation.json", "_livequest_snapshot.json")]
                            + [pin(fixture_path), pin(boundary_path), pin(environment_path)],
                }
                if kind == "formal_measurement":
                    result_path = one(base, "**/results/result.json")
                    result = load(result_path)
                    assert result["status"] == "completed" and result["measurement"] == "valid"
                    item["raw_formal_verdict"] = {k: result.get(k) for k in (
                        "status", "measurement", "task_outcome", "success", "outcome")}
                    item["pins"] += [pin(result_path), pin(result_path.parent / "evaluation.json")]
                    item["full_evaluation_equal_to_archived"] = evaluated == load(result_path.parent / "evaluation.json")
                elif (base / "reference.json").exists():
                    reference = load(base / "reference.json")
                    assert reference["status"] == "completed" and not reference["formal_baseline"]
                    for action in reference["actions"]:
                        if track == "st":
                            assert action["input"]["name"] in allowed
                            public.validate_tool(**action["input"])
                        else:
                            assert set(action["input"]) == {"commands"}
                    item["public_reference_actions_validated"] = len(reference["actions"])
                    item["pins"].append(pin(base / "reference.json"))
                    item["full_evaluation_equal_to_archived"] = evaluated == reference["evaluation"]
                else:
                    item["retained_reference_receipt"] = pin(base / "result.json")
                    historical = load(base / "result.json")
                    assert historical["status"] == "completed"
                    item["full_evaluation_equal_to_archived"] = evaluated == historical["evaluation"]
                if not item["full_evaluation_equal_to_archived"]:
                    assert code == "VE-P02" and kind == "native_feasibility"
                    historical_evaluation = load(base / "reference.json")["evaluation"]
                    assert historical_evaluation["checks"][0]["minimum"] == 1
                    # Compare without changing the saved record or either native endpoint.
                    comparison = json.loads(json.dumps(historical_evaluation))
                    comparison["checks"][0]["minimum"] = 0
                    assert comparison == evaluated
                    item["historical_difference"] = "Only reported health minimum1->0; previously reviewed explicit alive-floor migration. Historical whole success at100 is unchanged."
                manifest = base / "source-manifest.json"
                if manifest.exists():
                    item["adapter_source_manifest"] = pin(manifest)
                    item["adapter_source_head"] = load(manifest).get("head")
                    archived_hashes = load(manifest)["sha256"]
                    for name, expected_digest in archived_hashes.items():
                        assert digest(base / "python-source" / name) == expected_digest
                    item["archived_source_file_count"] = len(archived_hashes)
                    item["archived_scoring_and_helpers"] = {
                        name: expected for name, expected in archived_hashes.items()
                        if name in sources
                    }
                    item["archived_source_bytes_verified"] = True
                else:
                    item["adapter_source_archive_limit"] = "No per-run Python archive exists; preserve original canonical source-commit attribution, actual runtime/fixture/endpoints and earlier independent review. No retrospective archive or exact execution-source attestation manufactured."
                row["tracks"].append(item)
        row["status"] = "eligible_fully_validated_integrated_on_explicit_pinned_runtime"
        row["category"] = "fully_validated_integrated"
        row["scoringcompatibility"] = "All four retained outcomes preserved; actual downed/dead boolean fields captured, no defaults supplied. No fresh native gameplay claimed."
        row["nativeprovenance"] = "Per-row actual environment matches selected runtime exactly; binaries/manifests/upstream loader and server extension admission verified read-only."
        row["readonlyadmission"] = "Both exact integrated task bindings and public control schemas admitted without initialization."
        row["release_limits"] = [
            "Only explicit per-track pinned runtime; substituting current default/route2 build requires separate admission and relevant native checks.",
            "Difficulty is independent provisional engineering judgment, not model failure-derived or statistically calibrated.",
            "No blanket guarantee of exceptional setup paths, all agents/models, or new physics.",
        ]
        if code == "VE-P05":
            row["qualityreview"]["resolved_source_admission_gate"] = pin(DEV / "checks/VE-P05-main-admission.json")
            row["qualityreview"]["interpretation"] = "Original reviewed row says provisional because source admission was pending; existing0d041378 admission closed that gate. This bridge closes only subsequent downed guard. Basic planning2/2; trade optional, P04 overlap retained."
        if code == "VE-I05":
            row["nativeprovenance_correction"] = "Actual four environment.json records select unextended route1 runtime, not pickups runtime generalized in prior integration/inventory. Current harvest requires native terrain query/collection, not pickup_evidence; retain actual route1 condition."
        report["tasks"].append(row)
    report["delivery_recommendation"] = {
        "category1": list(IDS), "category4": [], "category6": [],
        "scope": "Only six explicit pinned-runtime conditions. Inventory owner must apply any whole60 update; this report changes no canonical assessment or snapshot.",
        "remaining_unclosed_conditions": "Substituted/default/route2 runtimes and exceptional merchant decline-reopen are not newly qualified. Any runtime pin mismatch blocks admission and needs a targeted compatible-runtime check, not a model campaign.",
    }
    preservation = load(ROOT / "docs/evidence/veloren-alive-contract-v2-integration.json")
    report["preservation"] = {
        "frozen_manifest_unchanged": digest(ROOT / "docs/reference_tasks_manifest.json") == preservation["frozen_manifest"]["sha256"],
        "unrelated_dirty_files": {},
        "canonical_assessments_and_historical_raw_results_rewritten": False,
        "inventory_snapshot_rewritten": False, "functional_source_changed": False,
    }
    assert report["preservation"]["frozen_manifest_unchanged"]
    for path, entry in preservation["preserved_dirty_paths"].items():
        assert digest(ROOT / path) == entry["actual_worktree_sha256"], path
        report["preservation"]["unrelated_dirty_files"][path] = {
            "sha256": digest(ROOT / path), "unchanged": True,
            "contract_baffle_text_admitted": False if "native_contract" in path else None,
        }
    assert git("rev-parse", "HEAD").decode().strip() == head
    output = ROOT / "checks/veloren-integrated-version-bridge.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(output), "head": head,
                      "tasks": {r["stable_id"]: [t["current_success"] for t in r["tracks"]]
                                for r in report["tasks"]}}))


if __name__ == "__main__":
    main()
