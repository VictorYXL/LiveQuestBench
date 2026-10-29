"""C03-only archived-evidence admission. Never starts a game or model."""
import ast
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

CANDIDATE = Path(__file__).resolve().parents[1]
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else CANDIDATE
sys.path.insert(0, str(CANDIDATE))

from benchmark.config import Source, load_task
from benchmark.factory import make_game
from game.backends.x11.interface import validate_actions
from game.veloren.evaluators.endpoints import load_pair, state_checks
from game.veloren.runtime.server_extension import select_server
from game.veloren.structured_tools import interface as public

DEV = ROOT / "output/temp/task_development"
EVIDENCE = DEV / "veloren-interaction"
SOURCE = "5a3d6c36c479fc9589bfc0897ebab4c54eb7ab08"
TASK = "shared_workshop_exchange"


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path):
    path = Path(path)
    relative = (path.relative_to(CANDIDATE) if path.is_relative_to(CANDIDATE)
                else path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return {"path": str(relative),
            "sha256": digest(path)}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def one(root, pattern):
    found = list(root.glob(pattern))
    assert len(found) == 1, (root, pattern, found)
    return found[0]


def source_delta(commit, path, provenance=None):
    new = (CANDIDATE / path).read_bytes()
    try:
        old = git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        assert provenance is None or path not in provenance["source_sha256"]
        return {"change": "new module since original execution",
                "executed_or_frozen_sha256": None,
                "candidate_sha256": hashlib.sha256(new).hexdigest()}
    old_hash = hashlib.sha256(old).hexdigest()
    if provenance is not None:
        assert provenance["source_sha256"][path] == old_hash, (commit, path)
    def definitions(data):
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.parse(data).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    a, b = definitions(old), definitions(new)
    return {"executed_or_frozen_sha256": old_hash,
            "candidate_sha256": hashlib.sha256(new).hexdigest(),
            "byte_identical": old == new,
            "changed_top_level_symbols": sorted(k for k in a.keys() | b.keys()
                                                if a.get(k) != b.get(k))}


def runtime_receipt(path, required_route):
    cfg = load(path)
    for name, expected in cfg["sha256"].items():
        assert digest(name) == expected, name
    assert digest(cfg["upstream_runtime"]) == cfg["upstream_sha256"]
    assert cfg["route_evidence"] == required_route
    assert cfg["native_protection"] == "disabled by explicit renderer launch environment"
    server = subprocess.check_output([
        cfg["python"], "-c",
        "import json,sys; from pathlib import Path; from scripts.rpg_benchmark import runtime; "
        "c=json.loads(Path(sys.argv[1]).read_text()); "
        "r=runtime.load_runtime(Path(c['upstream_runtime']),c['upstream_sha256'],backend='renderer'); "
        "print(r['renderer']['paths']['server'])", str(path)], text=True).strip()
    selected = select_server(cfg, Path(server))
    return cfg, {**pin(path), "constituents": [pin(p) for p in cfg["sha256"]],
                 "upstream": pin(cfg["upstream_runtime"]), "selected_server": pin(selected),
                 "renderer": pin(cfg["renderer"]), "route_capability": required_route,
                 "read_only_loader_and_server_selection": "pass",
                 "supported_for_current_task_launch": required_route == "native-client-route/2",
                 "fresh_gameplay": False}


def task_binding(track):
    directory = "structured_tools" if track == "st" else "visual_motor"
    path = CANDIDATE / f"config/veloren/tasks/{directory}/{TASK}.yaml"
    assert path.read_bytes() == git("show", f"{SOURCE}:{path.relative_to(CANDIDATE)}")
    task = load_task(path)
    binding = make_game(task, CANDIDATE / f"checks/not-started-c03/{track}",
                        headless=True, recording=False, recording_fps=10,
                        recording_path=None)
    assert not binding.game.output_dir.exists()
    controls = {}
    for role, member in binding.game.members.items():
        member.game.phase = "ready"
        controls[role] = sorted(t.name for t in binding.game.controls(role)[1])
        if track == "vm":
            assert not set(controls[role]) & set(public.SPECS)
    return task, binding, {"task": pin(path), "source_byte_identical": True,
                           "public_controls": controls, "game_started": False}


def native_inputs(base):
    beta = [json.loads(line) for line in (base / "Beta/public.jsonl").read_text().splitlines()]
    alpha_paths = sorted((base / "Alpha/public").glob("*-action.json"))
    alpha = [load(path) for path in alpha_paths]
    batches = []
    for row in beta:
        assert (base / "Beta" / f"{row['index'] - 1:04d}.png").is_file()
        batches.append(row["commands"])
    for row in alpha:
        assert row["observation_index"] == row["request"]["observation_index"]
        assert (base / "Alpha/public" / f"{row['observation_index']:04d}.png").is_file()
        request = row["request"]["request"]
        if "commands" in request:
            batches.append(request["commands"])
        else:
            assert request == {"finish": True}
            assert row["response"]["executed_commands"] == 0
    for commands in batches:
        validate_actions(commands)
        assert len(commands) <= 60
    return {"alpha_image_fenced_receipts": len(alpha), "beta_own_image_batches": len(beta),
            "all_commands_current_native_motor_schema": True,
            "reference_limits": "at most60 commands and10000ms summed waits per batch",
            "pins": [pin(base / "Beta/public.jsonl")] + [pin(p) for p in alpha_paths]}


def replay(base, track, expected, task, binding, cfg, *, reference=False, historical=False):
    before = one(base, "**/before/Alpha/observation.json").parent.parent
    after = one(base, "**/after/Alpha/observation.json").parent.parent
    binding.verify_initial(before)
    evaluated = binding.evaluate(before, after)
    result_path = base / "result.json" if reference else one(base, "**/results/result.json")
    result = load(result_path)
    archived = result["evaluation"] if reference else load(one(base, "**/results/evaluation.json"))
    assert evaluated == archived
    assert evaluated["success"] is expected
    assert result["status"] == "completed" and result["measurement"] == "valid"
    assert result["task_outcome"] == ("success" if expected else "failure")
    if reference:
        assert binding.metrics(before, after) == result["metrics"]
        metrics_boundary = "Exact current binding metrics equal the route/2 native result."
    else:
        try:
            binding.metrics(before, after)
        except ValueError as error:
            assert str(error) == "Native route identity or schema mismatch"
        else:
            raise AssertionError("Current route/2 metric consumer accepted historical route/1")
        provenance = load(base / "provenance.json")
        revision = provenance["revision"]
        itinerary = types.ModuleType("historical_itinerary")
        itinerary.__package__ = "game.veloren.evaluators"
        itinerary_source = git("show", f"{revision}:game/veloren/evaluators/itinerary.py")
        assert hashlib.sha256(itinerary_source).hexdigest() == provenance["source_sha256"]["game/veloren/evaluators/itinerary.py"]
        exec(compile(itinerary_source, "historical-itinerary", "exec"), itinerary.__dict__)
        efficiency = types.ModuleType("historical_efficiency")
        efficiency.__package__ = "game.veloren.evaluators"
        efficiency_source = git("show", f"{'6d7f8d4' if historical else revision}:game/veloren/evaluators/team_efficiency.py")
        assert hashlib.sha256(efficiency_source).hexdigest() == provenance["source_sha256"]["game/veloren/evaluators/team_efficiency.py"]
        exec(compile(efficiency_source, "historical-efficiency", "exec"), efficiency.__dict__)
        efficiency.route_samples = itinerary.route_samples
        assert efficiency.team_efficiency(before, after, list(binding.game.members)) == result["metrics"]["native_efficiency"]
        for role, member in binding.game.members.items():
            assert member.metrics(before / role, after / role) == result["metrics"]["participants"][role]
        metrics_boundary = ("Current route/2 consumer correctly rejects route/1. Original exact-source "
                            "route consumer reproduces all archived efficiency metrics; current death "
                            "metrics reproduce exactly. No route relabeling or relaxed consumer.")
    row = {"track": track, "kind": ("historical_open_court_guided_reference" if historical
                                  else "assistantguidedreference" if reference else "formal"),
           "qualifies_current_condition": not historical,
           "whole_native_outcome": expected, "measurement": "valid",
           "complete_evaluation_equal": True, "metrics_boundary": metrics_boundary,
           "result": pin(result_path), "evaluation": evaluated,
           "actors": {}, "runtime": pin(base / "runtime.json") if reference else None}
    for role, member in binding.game.members.items():
        initial, final = load_pair(before / role, after / role)
        for snapshot in (initial, final):
            for key in ("dead", "downed"):
                assert type(snapshot["survival"]["health"][key]) is bool, (base, role, key)
        assert not state_checks(initial, initial, **task.evaluator_parameters["roles"][role])["success"]
        fixture_path = one(base, f"**/game/{role}/fixture.json")
        actual = dict(load(fixture_path)["fixture"])
        wanted = dict(member.game.fixture)
        assert digest(actual.pop("world_path")) == digest(wanted.pop("world_path"))
        assert actual == wanted, (base, role, actual.keys() ^ wanted.keys())
        assert load(fixture_path)["administrator_retirement"]["confirmed_absent"] is True
        environment = fixture_path.parent / "environment.json"
        assert load(environment)["runtime"] == cfg
        clock_path = fixture_path.parent / "boundaries.json"
        clock = load(clock_path)
        metas = [load(p / role / "_livequest_snapshot.json") for p in (before, after)]
        times = [clock["ready_at_ns"], metas[0]["capture_started_at_ns"], metas[0]["captured_at_ns"],
                 clock["begin_requested_at_ns"], clock["begin_acknowledged_at_ns"],
                 clock["end_requested_at_ns"], clock["end_acknowledged_at_ns"],
                 metas[1]["capture_started_at_ns"], metas[1]["captured_at_ns"]]
        assert times == sorted(times), (base, role)
        assert final["private_route_evidence"]["route_schema"] == cfg["route_evidence"]
        row["actors"][role] = {
            "health_before": initial["survival"]["health"],
            "health_after": final["survival"]["health"],
            "original_identity": final["self_identity"],
            "native_route_schema": final["private_route_evidence"]["route_schema"],
            "initial_role_goal_false": True, "native_fixture_world_and_runtime_equal": True,
            "snapshot_integrity_identity_phase_order": "pass",
            "pins": [pin(p / role / name) for p in (before, after)
                     for name in ("observation.json", "_livequest_snapshot.json")]
                    + [pin(fixture_path), pin(environment), pin(clock_path)],
        }
    if reference:
        assert result["source_commit"] == SOURCE and result["uses_model"] is False
        assert result["formal"] is False
        assert result["task_sha256"] == task.source.sha256
        assert digest(base / "driver.py") == result["driver_sha256"]
        assert (base / "driver.py").read_bytes() == git(
            "show", f"{SOURCE}:tests/fixtures/veloren/independent_motor_reference.py")
        saved = load(base / "task.json")
        assert saved["source"]["content"] == task.source.content
        row["active_seconds"] = result["active_wall_seconds"]
        row["policy_boundary"] = result["policy_boundary"]
        row["driver"] = pin(base / "driver.py")
    else:
        saved = load(base / "config.json")
        assert saved["tasks"][0]["source"]["content"] == task.source.content
        assert saved["tasks"][0]["source"]["sha256"] == task.source.sha256
        assert hashlib.sha256(task.source.content.encode()).hexdigest() == task.source.sha256
        assert saved["repetitions"] == 1
        agent = saved["agents"][0]
        assert agent["id"] == ("guided_reference" if historical else "baseline")
        assert agent["name"] == "tool_calling"
        assert {k: agent["model"][k] for k in (
            "provider", "name", "reasoning_effort", "max_output_tokens", "max_attempts")} == {
                "provider": "github_copilot", "name": "gpt-6-astra", "reasoning_effort": "low",
                "max_output_tokens": 4096, "max_attempts": 3}
        row.update(formal_profile=agent, active_seconds=result["timing"]["active_wall_seconds"],
                   configuration=pin(base / "config.json"),
                   provenance=pin(base / "provenance.json"),
                   archived_revision=load(base / "provenance.json")["revision"])
    return row


def main():
    quality_path = DEV / "checks/veloren-independent-quality.json"
    quality = load(quality_path)
    review = next(row for row in quality["closed_native_followups"] if row["task_key"] == "VE-C03")
    assert review["status"] == "reviewed_pass" and review["source_commit"] == SOURCE
    review_hash = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
    assert review_hash == "d43c8d9ea1bea163315f2865d1231bd6a94a43fe04e2640d3d6bd3ecfbd57532"
    native = EVIDENCE / "VE-C03-settled-input-v2-vm"
    assert digest(native / "result.json") == "cba0fb8ae0aca130f58db44b6bfbbac90535a5e216c77285289e89c23e8d402c"
    for path, expected in review["hashes"].items():
        assert digest(native / path) == expected
    runtime2, runtime2_receipt = runtime_receipt(native / "runtime.json", "native-client-route/2")
    assert digest(native / "runtime.json") == "f90ca9a97e20a106e6d749368319cdd45243a2f902605e7797c6f8e3613c3793"
    assert digest(CANDIDATE / "game/veloren/patches/0008-native-physics-route-evidence.patch") == runtime2["physics_route_patch_sha256"]
    runtime1, runtime1_receipt = runtime_receipt(
        ROOT / "output/temp/veloren-native-route-20261027/runtime.json", "native-client-route/1")
    lease_path = DEV / "leases/2395ad92b70f401399f7b24cd2b367d7.json"
    lease = load(lease_path)
    assert lease["status"] == "finished" and lease["returncode"] == 0 and lease["uses_model"] is False
    report = {
        "schema": "livequest-c03-main-admission/1", "task_key": "VE-C03", "task_id": TASK,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CANDIDATE, text=True).strip(),
        "execution_source": SOURCE, "frozen_task_source": "0eb2f1f",
        "native_receipt_commit": "3c713c4941236aafd4daa4a31c4b5f2f5df151f3",
        "new_game_or_model_episodes": 0, "task_count": 1, "track_count": 2,
        "admission_decision": "Admit exactly one paired task when this passing receipt and its exact standalone files are committed together.",
        "independent_review_source": pin(quality_path), "independent_review": review,
        "independent_review_canonical_sha256": review_hash,
        "frozen_owner_handoff": pin(DEV / "checks/VE-C03-admission-handoff.json"),
        "difficulty": review["difficulty"], "lease": pin(lease_path),
        "native_public_inputs": native_inputs(native),
        "runtimes": {"current_native_vm": runtime2_receipt, "historical_formals": runtime1_receipt},
        "runtime_policy": "Use the checksum-pinned route/2 candidate-runtime.json; archived route/1 measurements are replayable historical outcomes, not fresh current-runtime ST/model episodes.",
        "admitted": {}, "replays": [], "source_deltas": {},
        "boundaries": [
            "One task, two tracks; no repeated formal, reference or model episode.",
            "Final-walled ST formal success is also the native ST whole-task witness, not a second episode. Earlier open-court guided ST remains historical only.",
            "Archived formal ST success and VM valid failure remain unchanged, with original source/runtime and difficulty uncertainty. Offline replays do not claim new gameplay.",
            "Both native health dead/downed flags are present and checked; no metadata bridge, fabricated flags or weaker alive guard.",
            "Basic reciprocal material cooperation: either player may craft. No balanced contribution, negotiation difficulty, autonomous-model success or speedup claim.",
            "ST2/VM3 are provisional point hypotheses, ranges2-3/2-4, high uncertainty; no calibrated rating.",
            "Main retains all stronger alive/cause guards, current route/2 observer, and active_build support. No old shared source file is overwritten.",
            "Exact shared reference helper contains C02 branches but C02 task definitions and active owner worktree are not imported or changed.",
        ],
        "compatibility_review": [
            "The reported exact VM execution commit5a3d6c3 game adapter/binding dependency set matches current main except the additive active_build evaluator registration. Team state scoring, route consumer, inputs and fixture code are unchanged. The result archives task and driver, not a complete executed Python-source manifest.",
            "Main's folded observer patch equals the hash in the actual immutable runtime manifest. The runtime's older base observer plus diagnostic/contact patches produce that pinned source; never rebuild or rewrite the witness.",
            "Historical ST/VM endpoint scorer differs only by the stronger downed predicate; actual recorded dead/downed booleans are available in every opening and terminal actor snapshot.",
            "Historical route/1 metrics intentionally fail current route/2 admission. Exact original route_samples and hash-verified team_efficiency reproduce their saved values; no metadata upgrade is fabricated.",
            "Historical team changes add peer_group and deferred supply/encounter barriers; this task has none of those fixture keys. Existing shared owner, role-local controls and team endpoint composition remain unchanged.",
            "Fixture authoring order batches the same ordinary voxel set before play. The exact final-court runtime2 native witness covers current setup. Optional enemy, companion, pickup, merchant and harvest paths are not enabled.",
            "Historical public tools are unchanged for this task's allowlist and role-local public projections match. Added terrain/wall-jump tools and optional energy are not exposed by this contract.",
            "Journal validated-prefix optimization is only enabled for peer Group encounters, absent here. Native death snapshots preserve their exact metrics; Xvfb -noreset retains native clients between captures, not game inputs.",
            "Old guided ST ran a dirty source revision: its efficiency module is recovered from6d7f8d4 only after equality to the actual archived source_sha256. That open-court run is never used as final-court qualification.",
        ],
    }
    sources = [
        "benchmark/config.py", "benchmark/factory.py", "benchmark/runner.py",
        "game/team.py", "game/bindings.py", "game/backends/x11/display.py",
        "game/backends/x11/interface.py", "game/veloren/binding.py",
        "game/veloren/fixture.py", "game/veloren/game.py", "game/veloren/native_bindings.py",
        "game/veloren/settlement.py", "game/veloren/structured_tools/interface.py",
        "game/veloren/visual_motor/interface.py", "game/veloren/runtime/session.py",
        "game/veloren/runtime/worker.py", "game/veloren/runtime/records.py",
        "game/veloren/runtime/journal.py", "game/veloren/runtime/startup.py",
        "game/veloren/runtime/server.py", "game/veloren/evaluators/endpoints.py",
        "game/veloren/evaluators/deaths.py", "game/veloren/evaluators/team_efficiency.py",
        "game/veloren/evaluators/itinerary.py",
        "game/veloren/runtime/server_extension.py",
    ]
    for track in ("st", "vm"):
        task, binding, admitted = task_binding(track)
        report["admitted"][track] = admitted
        base = EVIDENCE / f"VE-C03-final-walled-{track}"
        report["replays"].append(replay(base, track, track == "st", task, binding, runtime1))
        provenance = load(base / "provenance.json")
        report["source_deltas"][track + "_formal"] = {
            path: source_delta(provenance["revision"], path, provenance) for path in sources}
        frozen = types.ModuleType("frozen_public_" + track)
        exec(compile(git("show", f"{provenance['revision']}:game/veloren/structured_tools/interface.py"),
                     "frozen-public-interface", "exec"), frozen.__dict__)
        for role in binding.game.members:
            for phase in ("before", "after"):
                snapshot = load(one(base, f"**/{phase}/{role}/observation.json"))
                assert public.project(snapshot, peer=True) == frozen.project(snapshot, peer=True)
        if track == "st":
            for name in task.tools:
                if name in public.SPECS:
                    assert public.SPECS[name] == frozen.SPECS[name]
            old_base = EVIDENCE / "VE-C03-guided-st"
            old = load(old_base / "config.json")["tasks"][0]
            assert old["fixture"]["blocks"] != task.fixture["blocks"]
            old_task = replace(task, fixture=old["fixture"], task=old["task"],
                               evaluator=old["evaluator"], evaluator_parameters=old["evaluator_parameters"],
                               tools=tuple(old["tools"]), time_limit_seconds=old["time_limit_seconds"],
                               source=Source(**old["source"]))
            old_binding = make_game(old_task, CANDIDATE / "checks/not-started-c03/historical-st",
                                    headless=True, recording=False, recording_fps=10,
                                    recording_path=None)
            report["replays"].append(replay(old_base, track, True, old_task, old_binding,
                                            runtime1, historical=True))
        else:
            report["replays"].append(replay(native, track, True, task, binding, runtime2, reference=True))
    report["source_deltas"]["current_native_vm"] = {
        path: source_delta(SOURCE, path) for path in sources
    }
    report["gates"] = {name: "pass" for name in (
        "engineering", "mechanism_review", "provisional_paired_difficulty",
        "retained_measurements", "unchanged_task", "current_source_readonly_admission")}
    report["validation"] = {
        "focused_tests": "55 passed, 1 deselected",
        "test_log": pin(CANDIDATE / "checks/veloren-c03-tests.log"),
        "deselection": "Unrelated Minecraft-only inventory composition test requires absent optional nbtlib; not a C03 path.",
        "script": pin(Path(__file__)),
        "replay_method": "Execute via project Python runpy after initializing its environment.",
        "replay_command": ".venv/bin/python -c \"import runpy; runpy.run_path('checks/veloren_c03_admission.py', run_name='__main__')\"",
        "test_command": ".venv/bin/python -m pytest -q -m 'not game and not live' tests/test_agent/test_public_operator.py tests/test_game/veloren/test_independent_motor_reference.py tests/test_game/veloren/test_team_efficiency.py tests/test_game/veloren/test_evaluators.py tests/test_benchmark/test_team.py -k 'not test_team_goal_composition_uses_each_native_players_inventory' --basetemp=output/test/c03-public-input-admission",
    }
    output = CANDIDATE / "checks/VE-C03-main-admission.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"receipt": str(output), "replays": len(report["replays"]),
                      "gates": report["gates"]}, indent=2))


if __name__ == "__main__":
    main()
