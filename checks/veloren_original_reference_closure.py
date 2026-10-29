"""Offline original-six closure; immutable archives, no game or model execution."""
import ast
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "checks"))
from veloren_integrated_version_bridge import delta, digest, git, load, pin, runtime_check
from benchmark.config import load_task
from game.backends.x11.interface import validate_actions
from game.team import create_team_binding
from game.veloren.binding import create_binding
from game.veloren.evaluators import endpoints, encounter, contract, deaths, route_transfer
from game.veloren.fixture import verify_player
from game.veloren.structured_tools import interface as public

DEV = ROOT / "output/temp/task_development"
ARCHIVE_SOURCE = "31cf02cdea33b350310c59d98e8e4ecf4dc92661"
SOURCE_PATH = "game/veloren/evaluators/endpoints.py"
RELEASE = ROOT / "output/review/veloren-original-reference-release"
CHECKERS = (endpoints, encounter, contract, deaths, route_transfer)
CURRENT_LOAD_PAIR = endpoints.load_pair
SOURCES = (
    "game/veloren/evaluators/endpoints.py", "game/veloren/evaluators/deaths.py",
    "game/veloren/evaluators/encounter.py", "game/veloren/evaluators/contract.py",
    "game/veloren/evaluators/route_transfer.py", "game/veloren/binding.py",
    "game/veloren/game.py", "game/veloren/fixture.py", "game/veloren/structured_tools/interface.py",
    "game/veloren/visual_motor/interface.py", "game/veloren/runtime/session.py",
    "game/veloren/runtime/worker.py", "game/veloren/runtime/records.py",
    "game/veloren/runtime/server_extension.py", "game/veloren/runtime/startup.py",
    "game/backends/x11/interface.py", "game/team.py",
)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def archived_loader():
    """Keep the original schema discriminator; do not rewrite any archive bytes."""
    tree = ast.parse(git("show", f"{ARCHIVE_SOURCE}:{SOURCE_PATH}"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "load_pair")
    current = ast.parse(inspect.getsource(CURRENT_LOAD_PAIR)).body[0]
    comparison = ast.parse(ast.unparse(node).replace('"veloren-endpoint-v1"', '"veloren-endpoint"')
                           .replace("'veloren-endpoint-v1'", "'veloren-endpoint'")).body[0]
    assert ast.dump(comparison, include_attributes=False) == ast.dump(current, include_attributes=False)
    namespace = dict(vars(endpoints))
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<archived-load-pair>", "exec"), namespace)
    return namespace["load_pair"]


def load_archived_pair(before, after):
    schema = load(Path(before) / "_livequest_snapshot.json")["schema"]
    loader = archived_loader() if schema == "veloren-endpoint-v1" else CURRENT_LOAD_PAIR
    pair = loader(before, after)
    for row in pair:
        for field in ("downed", "dead"):
            if type(row["survival"]["health"].get(field)) is not bool:
                raise ValueError(f"Archive lacks explicit native health.{field}")
    return pair


def fixture_prefix(path):
    with path.open("rb") as stream:
        prefix = stream.read(131072)
    text = prefix.decode("utf-8")
    match = re.match(r'\s*\{\s*"fixture"\s*:\s*', text)
    assert match, path
    fixture, _ = json.JSONDecoder().raw_decode(text, match.end())
    return fixture, {"path": str(path.relative_to(ROOT)), "file_size": path.stat().st_size,
                     "prefix_bytes": len(prefix), "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
                     "decoded_fixture_sha256": canonical(fixture),
                     "scope": "First complete fixture object, not a digest of the large authoring journal."}


def differences(left, right):
    return sorted(key for key in left.keys() | right.keys() if left.get(key) != right.get(key))


def source_match(commit, path, expected):
    try:
        return hashlib.sha256(git("show", f"{commit}:{path}")).hexdigest() == expected
    except subprocess.CalledProcessError:
        return None


def semantic_task_delta(old, task):
    normalized = dict(old)
    normalized.pop("source", None)
    current = json.loads(json.dumps(task.resolved()))
    current.pop("source")
    # Explicitly report public wording/capability changes, never claim byte equality.
    return {key: {"archived": normalized.get(key), "release": current.get(key)}
            for key in differences(normalized, current)
            if key not in ("fixture", "tools")}


def admit(task):
    options = dict(headless=True, recording=False, recording_fps=10)
    unused = ROOT / "output/review/unused-original-native-output"
    if task.participants:
        binding = create_team_binding(task, unused, **options)
        allowed = {}
        for role, member in binding.game.members.items():
            member.game.phase = "ready"
            allowed[role] = sorted(t.name for t in binding.game.controls(role)[1])
    else:
        binding = create_binding(fixture=task.fixture, task_type=task.task_type,
                                 evaluator=task.evaluator, parameters=task.evaluator_parameters,
                                 tools=task.tools, output_dir=unused, **options)
        binding.game.phase = "ready"
        allowed = sorted(t.name for t in binding.controls()[1])
    return binding, allowed


def replay(task, result_path, runtime, old_public):
    result = load(result_path)
    formal = result_path.parent.name == "results"
    base = result_path.parent.parent if formal else result_path.parent
    roles = [p.id for p in task.participants] or [None]
    binding, controls = admit(task)
    item = {"archive": str(base.relative_to(ROOT)), "formal": formal, "pins": [pin(result_path)],
            "endpoints": [], "fixture_differences": {}, "runtime_matches_explicit_pin": True,
            "archived_result": {k: result.get(k) for k in (
                "status", "measurement", "task_outcome", "track", "kind", "active_wall_seconds")}}
    for role in roles:
        before = base / "before" / role if role else base / "before"
        after = base / "after" / role if role else base / "after"
        initial, final = load_archived_pair(before, after)
        game = base / "game" / role if role else base / "game"
        environment = load(game / "environment.json")
        runtime_matches = environment["runtime"] == runtime
        item["runtime_matches_explicit_pin"] &= runtime_matches
        fixture, fixture_pin = fixture_prefix(game / "fixture.json")
        wanted = dict(task.fixture)
        if role:
            wanted["player_state"] = next(p.player_state for p in task.participants if p.id == role)
        actual = dict(fixture)
        world_matches = digest(actual.pop("world_path")) == digest(wanted.pop("world_path"))
        item["fixture_differences"][role or "player"] = differences(actual, wanted)
        verify_player({**task.fixture, **({"player_state": wanted["player_state"]} if role else {})}, initial)
        clock = load(game / "boundaries.json")
        metas = [load(p / "_livequest_snapshot.json") for p in (before, after)]
        times = [clock["ready_at_ns"], metas[0]["capture_started_at_ns"], metas[0]["captured_at_ns"],
                 clock["begin_requested_at_ns"], clock["begin_acknowledged_at_ns"],
                 clock["end_requested_at_ns"], clock["end_acknowledged_at_ns"],
                 metas[1]["capture_started_at_ns"], metas[1]["captured_at_ns"]]
        assert times == sorted(times), (base, role)
        active = (clock["end_requested_at_ns"] - clock["begin_requested_at_ns"]) / 1e9
        projection_equal = []
        for row in (initial, final):
            kwargs = {"rpg": any(k in task.fixture for k in ("native_site", "merchant", "contract")),
                      "skills": "sword_skill_points" in task.fixture}
            old = old_public.project(row, **kwargs)
            new = public.project(row, **kwargs, peer=role is not None,
                                 energy=task.fixture.get("public_energy", False))
            old.pop("profile")
            new.pop("profile")
            projection_equal.append(old == new)
        item["endpoints"].append({
            "role": role, "session_id": initial["session_id"], "self_identity": initial["self_identity"],
            "ticks": [initial["tick"], final["tick"]],
            "health": [row["survival"]["health"] for row in (initial, final)],
            "schema": metas[0]["schema"], "integrity_identity_and_clock_order": "pass",
            "active_seconds": active, "within_release_budget": active <= task.time_limit_seconds,
            "world_sha256_matches": world_matches,
            "public_projection_equal_except_profile_label": all(projection_equal),
            "actual_runtime": {k: environment["runtime"].get(k) for k in (
                "schema", "renderer", "upstream_runtime", "upstream_sha256", "route_evidence",
                "native_protection", "sha256")},
            "current_alive_only_check": endpoints.state_checks(initial, final, min_health=0),
            "fixture": fixture_pin, "death_metrics": deaths.death_metrics(initial, final),
        })
        if task.evaluator == "state":
            item["endpoints"][-1]["opening_goal_success"] = endpoints.state_checks(
                initial, initial, **task.evaluator_parameters)["success"]
        item["pins"] += [pin(p / name) for p in (before, after)
                         for name in ("observation.json", "_livequest_snapshot.json")]
        item["pins"] += [pin(game / name) for name in ("environment.json", "boundaries.json")]
    historical = load(result_path.parent / "evaluation.json") if formal else result.get("evaluation")
    with ExitStack() as stack:
        # Only the historical schema spelling is admitted. Integrity remains identical.
        for module in CHECKERS:
            stack.enter_context(patch.object(module, "load_pair", load_archived_pair))
        try:
            evaluated = binding.evaluate(base / "before", base / "after")
            item["current_evaluation"] = evaluated
            item["historical_success"] = historical["success"]
            item["success_gate_equal_to_archive"] = evaluated["success"] == historical["success"]
            item["full_evaluation_equal_to_archive"] = evaluated == historical
        except ValueError as error:
            item["current_replay_gate"] = str(error)
    if formal:
        config_path = base.parents[2] / "config.json"
        configuration = load(config_path)
        old_task = next(t for t in configuration["tasks"] if t["id"] == task.id)
        launch_path = config_path.parent / "launch.json"
        launch = load(launch_path)
        fingerprint_task = {k: v for k, v in old_task.items() if k != "source"}
        fingerprint = canonical({
            "task": fingerprint_task,
            "agent": next(a for a in configuration["agents"] if a["id"] == result["agent_id"]),
            **{k: launch[k] for k in ("headless", "recording", "recording_fps", "record_chat")},
        })
        assert fingerprint == result["configuration_sha256"], result_path
        provenance_path = config_path.parent / "provenance.json"
        provenance = load(provenance_path)
        item["formal_conditions"] = {
            "valid": result["status"] == "completed" and result["measurement"] == "valid",
            "actual_time_limit_seconds": old_task["time_limit_seconds"],
            "configuration_fingerprint_verified": fingerprint,
            "actual_agents": configuration["agents"],
            "task_definition_delta": semantic_task_delta(old_task, task),
            "tool_allowlist_equal": list(task.tools) == old_task["tools"] if task.tools else old_task["tools"] is None,
            "source_revision": provenance["revision"],
            "task_source_sha256": old_task["source"]["sha256"],
            "adapter_source_hashes_match_declared_commit": {
                p: source_match(provenance["revision"], p, provenance["source_sha256"][p])
                for p in SOURCES if p in provenance["source_sha256"]},
            "source_match_null_semantics": "File absent from declared git revision; actual archived provenance hash retained in pinned provenance.json. No invented clean-source attestation.",
        }
        item["pins"] += [pin(config_path), pin(provenance_path), pin(launch_path),
                         pin(result_path.parent / "evaluation.json")]
    else:
        reference = base / "reference.json"
        if reference.exists():
            item["pins"].append(pin(reference))
            item["reference_conditions"] = load(reference)
        commands = base / "commands"
        if commands.exists():
            admitted = set(controls)
            receipts = []
            for path in sorted(commands.glob("*.json")):
                packet = load(path)
                if packet == {"finish": True}:
                    receipts.append([path.name, digest(path)])
                    continue
                for action in packet.get("actions", []):
                    assert action["name"] in admitted
                    public.validate_tool(**action)
                    assert public.validate_tool(**action) == old_public.validate_tool(**action)
                if task.task_type == "visual_motor":
                    assert set(packet) == {"commands"}
                    validate_actions(packet["commands"])
                receipts.append([path.name, digest(path)])
            item["public_command_archive"] = {
                "files": len(receipts), "ordered_file_hashes_sha256": canonical(receipts),
                "all_admitted": True, "st_native_translation_equal_to_archived_source": True,
            }
    return item


PLANS = {
    "VE-S01": [],
    "VE-P01": [
        "Two whole legal feasibility witnesses (one ST, one VM) on committed funded-expedition fixture: both original kills, chestpiece, >=1 potion, >=10 coins and alive arch return within2700s. Keep existing zero-death preparation/first-kill evidence; do not rerun those stages separately.",
        "Existing valid formal failures retain actual settings and unused-waypoint bridge; they do not establish whole-chain feasibility. No blanket model rerun or no-death requirement.",
    ],
    "VE-R01": [
        "One complete ST and one complete VM legal witness on the starting-waypoint fixture: new leather from any lawful source, both original target deaths and alive return. Archive real supply age at opening and actual endpoint identities.",
        "A narrow current-waypoint recovery demonstration is needed only if relying on death/recovery; old below-platform deaths cannot calibrate revised recovery. Preserve pre-death pickup/combat evidence and historical formal verdicts; no hard original-bundle deadline claim.",
        "Old ST/VM formal failures are valid at their actual2700s/no-start-waypoint condition but both used recovery. Final revised-condition formal evidence is therefore missing for each track; a successful valid formal episode can close native and formal gates together, not a mandatory second campaign.",
    ],
    "VE-I01": [
        "Use the clean committed config export, never the dirty baffle/text experiment. One ST and one VM whole witness must join exact new native Slay acceptance, post-acceptance target kill, real >=1000 coin settlement transaction and living original-giver arrival; explicitly fund giver3000 and use committed arch/waypoint.",
        "Retain the valid2700s funded/current-fixture VM formal contract-vm-controls-01; it fails kill/payment/arrival but is genuine formal evidence. Earlier ST formal is unfunded/no-waypoint/no-arch: only ST needs a funded-condition formal measurement after native feasibility. No VM formal repeat and no automatic episodes authorized.",
    ],
    "VE-C01": [
        "Retain the archived independent-two-player ST whole success: zero deaths makes added recovery waypoint unused. Need one whole independent-two-player VM completion at committed recovery condition; no equal-damage or communication-causality requirement.",
        "If recovery is used, capture starting-waypoint respawn and both living grounded arch endpoints, with source-bound union-of-peer contributions. Old VM below-platform recovery failure does not estimate revised difficulty.",
        "Only VM needs revised-recovery formal evidence; one valid whole-success formal can supply that and native feasibility together. Current peer observation adds native social fields; this is reported, not called projection equality or proof of information-sharing advantage.",
    ],
    "VE-L01": [
        "Existing route/1 ST completion is historical only. Route specialist68b2943 owns runtime/build; request no duplicate build or generic diagnostics. Once that exact runtime is admitted, need task-specific route/2 whole ST and VM endpoints/traces for variant5/origin18702,10802,701, all ordered wings, <=344m application travel, zero deaths and final alive stationary chamber.",
        "S03/f90ca9/5619e16 proves shared observer repair, not L01 task completion. Retain historical exploration/application trace. Exact current-route valid formal conditions remain missing; fixed-variant transfer is not causal learning calibration or held-out generalization.",
    ],
}


def main():
    head = git("rev-parse", "HEAD").decode().strip()
    quality_path = DEV / "checks/veloren-independent-quality.json"
    quality = load(quality_path)["original_reference_review"]
    inventory_path = DEV / "checks/task-delivery-status.json"
    inventory = load(inventory_path)
    manifest_path = ROOT / "docs/reference_tasks_manifest.json"
    manifest = load(manifest_path)
    frozen = {entry["path"]: entry for entry in manifest["tasks"]}
    old_public = types.ModuleType("original_reference_public")
    exec(compile(git("show", f"{ARCHIVE_SOURCE}:game/veloren/structured_tools/interface.py"),
                 "<original-public-source>", "exec"), old_public.__dict__)
    runtime_path = ROOT / "output/temp/veloren-native-20261022/runtime.json"
    runtime_receipt, runtime = runtime_check(runtime_path)
    report = {
        "schema": "livequest-original-reference-closure/1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "release_source_commit": head,
        "scope": [r["task_id"] for r in quality["tasks"]],
        "inputs": [pin(quality_path), pin(inventory_path), pin(manifest_path),
                   pin(ROOT / "checks/veloren-integrated-version-bridge.json")],
        "runtime": runtime_receipt,
        "method": "Independent bounded mechanism/difficulty closure plus actual archive replay. Reuse earlier review and six-added-task bridge, not its native witnesses. No native/model episodes, no archive mutation and no zero-bug guarantee.",
        "archive_schema_bridge": {
            "source_commit": ARCHIVE_SOURCE, "source_path": SOURCE_PATH,
            "operation": "Original load_pair integrity checks; AST equals current loader except schema spelling veloren-endpoint-v1 versus veloren-endpoint. Read-only shim for archive replay only; current production acceptance is not weakened.",
            "native_health": "Explicit captured downed/dead booleans required. No fabricated flags, identities, counters or timestamps.",
        },
        "source_bridge": {
            "base": ARCHIVE_SOURCE,
            "source_deltas": {path: delta(ARCHIVE_SOURCE, path) for path in SOURCES},
            "inherited_review": "checks/veloren-integrated-version-bridge.json compatibility_review",
            "additional_original_delta": [
                "Snapshot and public-profile labels lost version suffixes; native payloads and endpoint integrity checks unchanged. Compare actual projected fields excluding profile label explicitly.",
                "Workshop allowlist excludes new collect/terrain/wall-jump/peer features; ordinary ST schemas/native translations and VM interface remain compatible.",
                "Workshop is single-player, no encounters, merchant, supplies, route, glide or peer-group evidence requested. Deferred encounter/team-supply/journal paths do not apply. Native authoring reorders the same voxel set; verify exact archived fixture and initial player.",
                "Alive-only explicit0 replaces implicit1, preserving captured100HP workshop outcomes; current scorer independently rejects dead/downed. Explicit reserves elsewhere are untouched.",
            ],
        },
        "release_policy": {
            "runtime_env": f"LIVEQUEST_VELOREN_RUNTIME={runtime_path}",
            "clean_config_root": str(RELEASE.relative_to(ROOT)),
            "config_export": "Exact git blobs from release_source_commit with original relative world path; world blob exported alongside. Never load dirty contract working-tree YAML.",
            "default_or_substituted_route2_runtime_qualified": False,
            "new_game_or_model_episodes": 0,
            "frozen_manifest_history_rewritten": False,
        },
        "tasks": [],
    }
    world = "config/veloren/fixtures/veloren_0_18_0_0.bin"
    target_world = RELEASE / world
    target_world.parent.mkdir(parents=True, exist_ok=True)
    target_world.write_bytes(git("show", f"{head}:{world}"))
    for review in quality["tasks"]:
        code, name = review["task_key"], review["task_id"]
        inv = next(r for r in inventory["tasks"] if r["stable_id"] == f"veloren/{name}")
        row = {
            "stable_id": inv["stable_id"], "review_id": code, "task_id": name,
            "prior_category": inv["category"], "eligibility": "bounded_validation_needed",
            "mechanism_review": list(review["construct_findings"]),
            "difficulty": review["independent_provisional_difficulty"],
            "difficulty_semantics": "Development estimate, high uncertainty, not statistical calibration; null means insufficient track-level evidence.",
            "review_closed": True, "tracks": {}, "archives": [], "remaining_validation": PLANS[code],
            "earlier_review_followup": review["followup_classification"],
        }
        if code == "VE-I01":
            row["mechanism_review"][2] = (
                "Committed release geometry is the frozen reference plus alive-only scoring. "
                "The pre-existing local baffle/route wording is neither admitted nor overwritten.")
        if code != "VE-S01":
            row["previous_difficulty"] = row["difficulty"]
            estimates = {"VE-P01": (3, 4), "VE-R01": (3, 4), "VE-I01": (3, 4),
                         "VE-C01": (2, 3), "VE-L01": (3, 4)}
            st, vm = estimates[code]
            row["difficulty"] = {
                **row["previous_difficulty"], "st": st, "vm": vm,
                "basis": "Independent development estimate from committed mechanism, not a completion-rate claim. Missing whole native feasibility remains an engineering gate, not a reason to invent empirical calibration.",
                "track_estimates_not_native_qualification": True,
            }
        tasks = {}
        for short, directory in (("st", "structured_tools"), ("vm", "visual_motor")):
            path = f"config/veloren/tasks/{directory}/{name}.yaml"
            raw = git("show", f"{head}:{path}")
            target = RELEASE / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            task = load_task(target)
            tasks[task.task_type] = task
            definition = json.loads(json.dumps(frozen[path]["definition"]))
            import yaml
            committed = yaml.safe_load(raw)
            parameters = definition["evaluator"]["parameters"]
            (parameters["all"] if code == "VE-C01" else parameters)["min_health"] = 0
            assert not differences(definition, committed), (code, short, "unexpected manifest drift")
            _, controls = admit(task)
            row["tracks"][short] = {
                "committed_path": path, "committed_sha256": hashlib.sha256(raw).hexdigest(),
                "frozen_manifest_sha256": frozen[path]["sha256"],
                "only_manifest_definition_change": "explicit alive min_health0",
                "clean_run_config": pin(target), "world": pin(target_world),
                "read_only_binding_and_controls": "pass", "controls": controls,
                "route_requested": task.fixture.get("route_evidence", False),
                "evaluator": task.evaluator, "parameters": task.evaluator_parameters,
                "time_limit_seconds": task.time_limit_seconds,
                "working_tree_bytes_admitted": False,
            }
        for evidence in review["evidence"]:
            if not evidence["path"].endswith("/result.json"):
                continue
            result_path = ROOT / evidence["path"]
            result = load(result_path)
            track = result.get("track")
            if track not in tasks:
                track = "visual_motor" if ".visual_motor/" in str(result_path) or "-vm-" in str(result_path) else "structured_tool"
            item = replay(tasks[track], result_path, runtime, old_public)
            item["track"] = track
            item["prior_classification"] = evidence.get("classification")
            row["archives"].append(item)
        if code == "VE-S01":
            assert len(row["archives"]) == 4
            for name in tasks["structured_tool"].tools:
                assert public.SPECS[name][1:] == old_public.SPECS[name][1:]
            formal_sources = {
                item["track"]: item["formal_conditions"]["task_source_sha256"]
                for item in row["archives"] if item["formal"]
            }
            for item in row["archives"]:
                assert item["runtime_matches_explicit_pin"]
                assert item["success_gate_equal_to_archive"]
                assert all(not fields for fields in item["fixture_differences"].values())
                assert all(e["within_release_budget"] and e["world_sha256_matches"]
                           and e["public_projection_equal_except_profile_label"]
                           and not e["opening_goal_success"] for e in item["endpoints"])
                if item["formal"]:
                    assert item["formal_conditions"]["valid"]
                    assert item["formal_conditions"]["actual_time_limit_seconds"] == 2700
                    hashes = item["formal_conditions"]["adapter_source_hashes_match_declared_commit"]
                    assert all(hashes[p] for p in (
                        SOURCE_PATH, "game/veloren/evaluators/deaths.py", "game/veloren/game.py",
                        "game/veloren/fixture.py", "game/veloren/structured_tools/interface.py",
                        "game/veloren/visual_motor/interface.py", "game/veloren/runtime/session.py",
                        "game/veloren/runtime/worker.py", "game/backends/x11/interface.py"))
                    assert item["formal_conditions"]["tool_allowlist_equal"]
                else:
                    assert item["current_evaluation"]["success"]
                    assert item["public_command_archive"]["all_admitted"]
                    assert item["reference_conditions"]["task_sha256"] == formal_sources[item["track"]]
                    item["native_reference_source_matches_actual_formal_task"] = True
            row["archive_source_provenance_limit"] = (
                "Guided runs have no separate whole-adapter source manifest. Their actual runtime, "
                "fixture, task hashes, public command receipts and endpoints are pinned; same-task "
                "formal provenance pins the old adapter. This is a bounded compatibility bridge, "
                "not a retrospectively manufactured clean execution-source attestation.")
            row["eligibility"] = "eligible_fully_validated_integrated_on_explicit_pinned_runtime"
            row["category"] = "fully_validated_integrated"
            row["closed_gates"] = [
                "Exact fixture-equivalent whole legal ST and VM native successes replay under alive-v2/downed guards.",
                "Both valid formal actual2700s conditions preserved; failures remain failures. Public whitespace/finish-response cleanup is not represented as byte-equal prompts.",
                "Independent mechanism estimate ST2(range2-3), VM3(range3-4), high uncertainty. Not mandatory station visitation or model difficulty calibration.",
                "Pinned old native binary verified and admitted with current committed adapter; no route2/default-runtime claim.",
            ]
        elif code == "VE-L01":
            row["runtime_gate"] = "Only original-six route-enabled fixture; actual route/1 archives cannot satisfy route/2 scorer. No S03 evidence substitution."
        row["resolved_gate"] = "Alive-only objective alignment is fixed in9a55a71; captured explicit health flags pass separate current alive predicate where appropriate. L01 whole scorer still rejects route/1; no missing-field inference."
        report["tasks"].append(row)
    report["delivery_recommendation"] = {
        "category1": [r["stable_id"] for r in report["tasks"] if r.get("category") == "fully_validated_integrated"],
        "others": "Retain current category with concrete per-task minimal validation, not generic review/version labels.",
        "owner": "2e8ab76b", "inventory_rewritten": False,
    }
    report["validation"] = {
        "helper": pin(Path(__file__)),
        "replay": ".venv/bin/python checks/veloren_original_reference_closure.py",
        "test_log": pin(ROOT / "checks/veloren-original-reference-tests.log"),
        "focused_result": "84 passed, 1 deselected",
        "deselection": "Unrelated Minecraft team inventory test requires unavailable nbtlib; initial combined run84passed/1missing-dependency failure. No dependency installation or Minecraft qualification.",
    }
    assert git("rev-parse", "HEAD").decode().strip() == head, "HEAD changed; rerun before integration"
    output = ROOT / "checks/veloren-original-reference-closure.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(output), "promotion": report["delivery_recommendation"]["category1"]}))


if __name__ == "__main__":
    main()
