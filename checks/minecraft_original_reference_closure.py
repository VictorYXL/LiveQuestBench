"""Read-only original-reference closure. Never starts a game or model."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import UUID

import nbtlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.config import load_task
from game.backends.x11.interface import validate_actions
from game.minecraft.binding import create_binding
from game.minecraft.runtime.client import check_client, source_digest
from game.minecraft.runtime.install import check_installation
from game.minecraft.structured_tools.interface import agent_tools, validate_tool
from game.minecraft.visual_motor.interface import agent_tools as motor_tools
from game.minecraft.evaluators.world import _chunk, read_blocks
from game.route_transfer import build_layout

DEV = ROOT / "output/temp/task_development"
HOME = DEV / "minecraft-runtime/MC-R05-main-vitals-placement-cart-v1"
QUALITY = DEV / "checks/minecraft-independent-quality.json"
INVENTORY = DEV / "checks/task-delivery-status.json"
IDS = (
    "abandoned_mine_cargo", "expedition_record_reconstruction",
    "mining_workshop_restart", "prepared_village_defense",
    "route_schema_transfer", "shared_crossing_camp",
)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pin(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return {"path": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
            "sha256": sha(path)}


def recorded(row):
    actual = pin(row["path"])
    assert actual["sha256"] == row["sha256"], row["path"]
    return actual


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def snapshot(path):
    receipt = load(path / "_livequest_snapshot.json")
    assert receipt["phase"] in ("ready", "ended")
    assert receipt["capture_started_at_ns"] <= receipt["save_acknowledged_at_ns"] <= receipt["copied_at_ns"]
    boundary = receipt["boundaries"]
    if receipt["phase"] == "ended":
        keys = ("ready_at_ns", "begin_requested_at_ns", "begin_acknowledged_at_ns",
                "end_requested_at_ns", "end_acknowledged_at_ns")
        times = [boundary[k] for k in keys]
        assert times == sorted(times) and times[-1] <= receipt["capture_started_at_ns"]
    for name, digest in receipt["sha256"].items():
        assert sha(path / name) == digest, path / name
    return {**pin(path / "_livequest_snapshot.json"),
            "verified_files": len(receipt["sha256"]),
            "phase": receipt["phase"], "player_uuid": receipt["player_uuid"],
            "boundaries": boundary}


def runtime():
    os.environ["LIVEQUEST_MINECRAFT_HOME"] = str(HOME)
    launch = check_client()
    provenance = load(HOME / "provenance.json")
    assert source_digest() == provenance["source_sha256"]
    client = HOME / "client-1.20.4"
    groups = {
        "source_files": client / "src",
        "classes": client / "build/classes/java/main",
        "resources": client / "build/resources/main",
        "dependencies": Path("/"),
    }
    counts = {}
    for group, base in groups.items():
        for name, digest in provenance[group].items():
            assert sha(base / name) == digest, name
            if group == "source_files":
                assert sha(ROOT / "game/minecraft/client/src" / name) == digest
        counts[group] = len(provenance[group])
    return {
        "home": str(HOME), "source_sha256": source_digest(),
        "ready": pin(client / "ready.json"), "launch": pin(client / "launch.json"),
        "provenance": pin(HOME / "provenance.json"),
        "verified_constituents": counts, "classpath_entries": len(launch["classpath"]),
        "admission": "passed_read_only", "default_cache": "not selected; remains legitimately stale",
        "installation": [check_installation(track=t) for t in ("structured_tool", "visual_motor")],
        "fresh_native_execution": False, "runtime_overwrites": 0,
    }


def binding(task):
    if task.participants:
        from game.team import create_team_binding
        return create_team_binding(task, DEV / "original-reference-closure-unused-game",
                                   headless=True, recording=False, recording_fps=10)
    return create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools,
        output_dir=DEV / "original-reference-closure-unused-game",
        headless=True, recording=False, recording_fps=10,
    )


def other_archives(review, tasks):
    proofs = []
    candidates = [("formal", track, r) for track, r in review["formal_measurements"].items()]
    if review["task_id"] == "prepared_village_defense":
        candidates.append(("native", "structured_tool", review["native_references"][0]))
    for kind, track, row in candidates:
        path = Path(row["path"] if kind == "native" else row["result"]["path"])
        episode = path.parent if kind == "native" else path.parent.parent
        result = load(path)
        task = tasks[track]
        b = binding(task)
        members = b.game.members if task.participants else {"": b}
        endpoints = {}
        for role, member in members.items():
            endpoints[role] = [snapshot(episode / phase / role) for phase in ("before", "after")]
            assert endpoints[role][0]["player_uuid"] == endpoints[role][1]["player_uuid"]
            member.game.player_uuid = UUID(endpoints[role][0]["player_uuid"])
            member.game.player_state.verify(nbtlib.load(
                episode / "before" / role / "playerdata" / f"{member.game.player_uuid}.dat"),
                member.game.player_uuid)
        b.verify_initial(episode / "before")
        replay = b.evaluate(episode / "before", episode / "after")
        historical = result["evaluation"] if kind == "native" else load(path.parent / "evaluation.json")
        comparison = json.loads(json.dumps(historical))
        label_changes = []
        if task.id == "shared_crossing_camp":
            assert comparison["schema"] == "team-endpoints-v1"
            comparison["schema"] = "team-endpoints"
            label_changes.append("/schema: team-endpoints-v1 -> team-endpoints")
            for role in ("Alpha", "Beta"):
                structure = comparison["checks"][2]["roles"][role]["checks"][1]["result"]
                assert structure["version"] == "minecraft-1.20.4-structure-v1"
                structure["version"] = "minecraft-1.20.4-structure"
                label_changes.append(f"/checks/2/roles/{role}/checks/1/result/version: removed -v1 suffix")
        assert replay == comparison, (task.id, track)
        if kind == "formal":
            assert result["measurement"] == "valid"
            assert (result["task_outcome"] == "success") == replay["success"]
            config_path = next(p / "config.json" for p in episode.parents if (p / "config.json").exists())
            captured = load(config_path)["tasks"][0]
            assert captured["evaluator_parameters"] == task.evaluator_parameters
            assert captured["time_limit_seconds"] == task.time_limit_seconds
        else:
            assert replay["success"]
        proofs.append({"kind": kind, "track": track, "result": pin(path),
                       "snapshots": endpoints, "initial_state_verified": True,
                       "current_evaluation_equals_historical": replay == historical,
                       "exact_metadata_label_changes": label_changes,
                       "all_predicate_values_and_verdicts_equal": True,
                       "evaluation": replay,
                       "purpose": "Closes retained supported-track scorer/initial-state reconciliation only; does not convert incomplete VM into a native success."})
    return proofs


def mining_bridge(review, tasks):
    proofs = []
    configs = {}
    for track, row in review["formal_measurements"].items():
        result_path = Path(row["result"]["path"])
        episode = result_path.parent.parent
        config_path = next(p / "config.json" for p in episode.parents if (p / "config.json").is_file())
        config = load(config_path)["tasks"][0]
        current = json.loads(json.dumps(tasks[track].resolved()))
        assert hashlib.sha256(config["source"]["content"].encode()).hexdigest() == config["source"]["sha256"]
        differences = sorted(k for k in current.keys() | config.keys() if current.get(k) != config.get(k))
        assert differences == ["fixture", "source", "task"], differences
        assert {k: v for k, v in config["fixture"].items() if k != "world_path"} == {
            k: v for k, v in current["fixture"].items() if k != "world_path"}
        old_prompt = " ".join(config["task"].split())
        assert old_prompt == " ".join(current["task"].split()) + " Release held controls and finish with a text response."
        configs[track] = config
        proofs.append({"kind": "condition_comparison", "track": track,
                       "configuration": pin(config_path),
                       "historical_task_sha256": config["source"]["sha256"],
                       "deltas": differences,
                       "meaning": "Identical mechanics, initialization, tools, budget and scorer parameters. Relocated byte-identical fixture; whitespace and redundant control-release/text-finish sentence removed. Not byte-identical prompt or a new model measurement."})
    for kind, track, row in [
        ("native", r["runtime"]["track"], r) for r in review["native_references"]
    ] + [("formal", track, r) for track, r in review["formal_measurements"].items()]:
        result_path = Path(row["path"] if kind == "native" else row["result"]["path"])
        episode = result_path.parent if kind == "native" else result_path.parent.parent
        result = load(result_path)
        task = tasks[track]
        b = binding(task)
        endpoints = [snapshot(episode / phase) for phase in ("before", "after")]
        assert endpoints[0]["player_uuid"] == endpoints[1]["player_uuid"]
        b.game.player_uuid = UUID(endpoints[0]["player_uuid"])
        b.game.player_state.verify(nbtlib.load(
            episode / "before/playerdata" / f"{b.game.player_uuid}.dat"), b.game.player_uuid)
        b.verify_initial(episode / "before")
        replay = b.evaluate(episode / "before", episode / "after")
        historical = result["evaluation"] if kind == "native" else load(result_path.parent / "evaluation.json")
        assert replay == historical, (kind, track)
        fixture = load(episode / "game/fixture.json")
        files = review["source_hashes"]["release_fixture_files"]
        for item in files:
            relative = str(Path(item["path"]).relative_to("config/minecraft/fixtures/mining_workshop_restart"))
            assert fixture["sha256"][relative] == sha(ROOT / item["path"])
        commands = []
        if kind == "native":
            reference = load(episode / "reference.json")
            assert reference["task_sha256"] == configs[track]["source"]["sha256"]
            names = set()
            admitted = {tool.name: tool for tool in agent_tools()}
            for path in sorted((episode / "commands").glob("*.json")):
                value = load(path)
                if "commands" in value:
                    validate_actions(value["commands"])
                    names.update(c["name"] for c in value["commands"])
                for action in value.get("actions", []):
                    assert action["name"] in task.tools
                    assert action["name"] in admitted
                    validate_tool(action["name"], action["arguments"])
                    names.add(action["name"])
                commands.append(pin(path))
            assert result["evaluation"]["success"] is True
            assert 0 < result["elapsed_seconds"] < task.time_limit_seconds
        else:
            assert result["measurement"] == "valid" and result["status"] == "completed"
            assert (result["task_outcome"] == "success") == replay["success"]
            public_tools = agent_tools() if track == "structured_tool" else motor_tools()
            schemas = {tool.name: tool.parameters for tool in public_tools
                       if task.tools is None or tool.name in task.tools}
            assert {tool["name"]: tool["parameters"] for tool in result["tools"]} == schemas
            names = set()
        proofs.append({
            "kind": kind, "track": track, "result": pin(result_path),
            "environment": pin(episode / "game/environment.json"),
            "fixture": pin(episode / "game/fixture.json"),
            "fixture_release_files_equal": len(files), "snapshots": endpoints,
            "current_binding_initial_state_and_inventory": "passed",
            "exact_current_evaluation_equals_historical": True,
            "evaluation": replay,
            "command_manifest": {"files": len(commands), "canonical_sha256": hashlib.sha256(
                json.dumps(commands, sort_keys=True).encode()).hexdigest()},
            "public_command_names": sorted(names),
            "measurement": result.get("measurement"), "outcome": result.get("task_outcome"),
        })
    return proofs


def route_bridge(review, tasks):
    proofs = []
    current_world = Path(tasks["visual_motor"].fixture["world_path"])
    layout = build_layout(5, (0, 0, 201))
    sections = sorted({(x // 16, z // 16, y // 16)
                       for x, y, z in list(layout["solid"]) + list(layout["walking"])})
    for row in (review["native_references"][0], review["native_references"][2]):
        episode = Path(row["path"]).parent
        result = load(episode / "result.json")
        task = tasks[result["task"]["task_type"]]
        old = result["task"]
        assert hashlib.sha256(old["source"]["content"].encode()).hexdigest() == old["source"]["sha256"]
        assert old["evaluator_parameters"] == task.evaluator_parameters == {"variant": 5, "origin": [0, 0, 201]}
        assert old["time_limit_seconds"] == task.time_limit_seconds
        assert old["tools"] == (list(task.tools) if task.tools is not None else None)
        assert {k: v for k, v in old["fixture"].items() if k != "world_path"} == {
            k: v for k, v in task.fixture.items() if k != "world_path"}
        assert task.task == old["task"].replace(
            "final enlarged chamber.", "final enlarged chamber. Complete the route without dying or respawning.", 1)
        original_world = Path(old["fixture"]["world_path"])
        fixture = load(episode / "game/fixture.json")
        for name, digest in fixture["sha256"].items():
            assert sha(original_world / name) == digest
        for sx, sy, sz in sections:
            low, high = (sx * 16, sy * 16, sz * 16), (sx * 16 + 15, sy * 16 + 15, sz * 16 + 15)
            assert read_blocks(original_world, low, high, "minecraft:overworld") == read_blocks(
                current_world, low, high, "minecraft:overworld")
            states = []
            for world in (original_world, current_world):
                chunk = _chunk(world / "region", sx, sz)
                section = next(s for s in chunk["sections"] if int(s["Y"]) == sy)
                states.append(str(section["block_states"]))
            assert states[0] == states[1]
        levels = [nbtlib.load(w / "level.dat")["Data"] for w in (original_world, current_world)]
        changed = sorted(k for k in levels[0].keys() | levels[1].keys()
                         if str(levels[0].get(k)) != str(levels[1].get(k)))
        assert changed == ["LastPlayed", "clearWeatherTime"]
        assert all(int(level["clearWeatherTime"]) > 2700 * 20 for level in levels)
        endpoints = [snapshot(episode / phase) for phase in ("before", "after")]
        b = binding(task)
        b.game.player_uuid = UUID(endpoints[0]["player_uuid"])
        assert endpoints[0]["player_uuid"] == endpoints[1]["player_uuid"]
        b.game.player_state.verify(nbtlib.load(
            episode / "before/playerdata" / f"{b.game.player_uuid}.dat"), b.game.player_uuid)
        b.verify_initial(episode / "before")
        replay = b.evaluate(episode / "before", episode / "after")
        assert replay["success"] is True
        assert b.metrics(episode / "before", episode / "after")["deaths"]["count"] == 0
        assert 0 < result["active_seconds"] < task.time_limit_seconds
        action_count = 0
        for line in (episode / "public-trace.jsonl").open():
            action = json.loads(line)
            if action["event"] != "action":
                continue
            action_count += 1
            if task.task_type == "visual_motor":
                validate_actions(action["commands"])
            else:
                assert action["name"] in task.tools
                validate_tool(action["name"], action["arguments"])
        proofs.append({
            "track": task.task_type, "result": recorded(row),
            "environment": pin(episode / "game/environment.json"),
            "fixture": pin(episode / "game/fixture.json"),
            "snapshots": endpoints, "public_trace": pin(episode / "public-trace.jsonl"),
            "validated_public_action_batches": action_count,
            "complete_native_success_on_current_scorer": True,
            "current_evaluation": replay,
            "historical_evaluation_byte_semantics_equal": replay == result["evaluation"],
            "scorer_revision_boundary": "ST predates explicit death guard; current scorer independently reads actual native zero-death statistics, not a synthesized field. VM evaluation already includes death guard. Historical objects unchanged.",
            "fixture_bridge": {
                "original_source_files_verified_against_episode_receipt": len(fixture["sha256"]),
                "route_intersecting_sections": len(sections),
                "block_cells_equal": len(sections) * 4096,
                "block_states_including_properties_equal": True,
                "level_different_fields": changed,
                "weather": "Both clear-weather timers exceed the full2700-second cap; all gamerules, difficulty, time and other level fields equal.",
                "boundary": "Required route and surrounding intersecting sections match, not byte-identical entire world or an exhaustive alternate-route audit. Distinct save timestamps/runner markers are not route evidence; current scorer independently validates the actual observer datapack, identity-bound continuous native trajectory and tick bounds.",
            },
            "prompt_delta": "Adds explicit no-death/no-respawn sentence. Both native witnesses actually have zero deaths; no formal performance equivalence inferred.",
        })
    return proofs


def main():
    quality, inventory = load(QUALITY), load(INVENTORY)
    reviews = {r["task_id"]: r for r in quality["original_reference_coverage"]}
    selected = runtime()
    report = {
        "schema": "livequest-minecraft-original-reference-closure/1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "main_head": git("rev-parse", "HEAD"), "scope": list(IDS),
        "method": "Archived native facts, exact current scorer replay and read-only selected-runtime admission. No hidden-field synthesis, no hash waiver, no fresh game/model episodes.",
        "review": pin(QUALITY), "inventory_snapshot": pin(INVENTORY),
        "manifest": pin(ROOT / "docs/reference_tasks_manifest.json"),
        "selected_runtime": selected,
        "new_native_or_model_episodes": 0, "tasks": [],
        "focused_validation": {
            "result": "15 passed, 1 deselected",
            "log": pin(DEV / "checks/minecraft-original-reference-closure-tests.log"),
            "command": "env -u LIVEQUEST_MINECRAFT_TEST output/temp/task_development/MC-final-admission-python/bin/python -m pytest -q -m 'not game and not live' tests/test_game/minecraft/test_game.py tests/test_game/minecraft/test_install.py --basetemp=output/test/minecraft-original-reference-closure",
            "meaning": "Offline regression support only; whole completion comes from native snapshots and original terminal evaluations.",
            "route_result": "4 passed",
            "route_log": pin(DEV / "checks/minecraft-original-route-closure-tests.log"),
            "route_command": "env -u LIVEQUEST_MINECRAFT_TEST output/temp/task_development/MC-final-admission-python/bin/python -m pytest -q -m 'not game and not live' tests/test_game/minecraft/test_route_transfer.py --basetemp=output/test/minecraft-original-route-closure",
        },
        "replay_script": pin(__file__),
        "replay_command": "output/temp/task_development/MC-final-admission-python/bin/python checks/minecraft_original_reference_closure.py",
        "python_environment": pin(DEV / "MC-final-admission-python/pyvenv.cfg"),
        "shared_source": [pin(ROOT / p) for p in (
            "game/minecraft/binding.py", "game/minecraft/game.py",
            "game/minecraft/init_player_state.py", "game/minecraft/runtime/session.py",
            "game/minecraft/runtime/client.py", "game/minecraft/runtime/install.py",
            "game/minecraft/structured_tools/interface.py", "game/minecraft/visual_motor/interface.py",
            "game/backends/x11/interface.py",
            "game/minecraft/evaluators/world.py", "game/minecraft/evaluators/deaths.py",
            "game/minecraft/evaluators/state.py", "game/minecraft/evaluators/inventory.py",
        )],
        "compatibility_boundary": [
            "The 9af8c6ae historical client is not admitted as current. Current39b0c2e is admitted without rebuilding or mutating any runtime.",
            "Compared f98a1a4 release scorer against current source: inventory unchanged; state adds optional gamemode predicate, not enabled by mining. Exact archived native predicates replay unchanged.",
            "NativeBridge changes add optional vitals, corrected ST placement confirmation, and retained container/cart inspection. NativeInventory changes only container inspection; mining witness uses furnace/craft/dig/move, not PlaceTool or container inspection. VM uses unchanged X11 keyboard/mouse actions.",
            "Historical measured task text differs by wrapping and a removed redundant control-release/text-finish sentence. This is a declared development-equivalence bridge, not an exact-prompt performance replication.",
            "Independent bounded construct/difficulty review already exists for all six; ratings2–4 are design judgments, not model causal or statistical claims.",
        ],
        "release_scorer_comparison": {
            "release_commit": git("rev-parse", "f98a1a4"),
            "files": [{
                "path": p,
                "release_sha256": hashlib.sha256(subprocess.check_output(
                    ["git", "show", f"f98a1a4:{p}"], cwd=ROOT)).hexdigest(),
                "current_sha256": sha(ROOT / p),
            } for p in ("game/minecraft/evaluators/state.py",
                        "game/minecraft/evaluators/inventory.py")],
        },
    }
    blockers = {
        "abandoned_mine_cargo": "Missing whole legal VM success on frozen release fixture. Older pilot and recovery/shallow-pit successes have12/18 differing fixture files, including terrain; no equivalence waiver.",
        "expedition_record_reconstruction": "Missing whole legal VM retrieval of all three originals plus grounded living return; archived formal VM is valid failure, not success.",
        "prepared_village_defense": "Missing whole legal VM raid victory/Hero/return. Existing reference terminated on unsupported mouse_move_absolute; use mouse_move_to, not a game/control workaround.",
        "shared_crossing_camp": "Missing whole legal two-peer VM crossing, shelter, food and living reunion; current VM formal has partial progress only.",
        "route_schema_transfer": "Missing valid released-mapping5 formal ST/VM pair. Both earlier formal diagnostics are mapping2 and cannot supply it. Mapping5 native ST/VM success now replays under the current no-death scorer with actual zero-death statistics and matching route geometry.",
    }
    for task_id in IDS:
        review = reviews[task_id]
        inv = next(r for r in inventory["tasks"] if r["stable_id"] == "minecraft/" + task_id)
        definitions = [recorded(x) for x in review["source_hashes"]["definitions"]]
        tasks = {load_task(ROOT / p["path"]).task_type: load_task(ROOT / p["path"]) for p in definitions}
        source = [pin(p["path"]) for p in review["source_hashes"]["implementation"]]
        for t in tasks.values():
            if not t.participants:
                binding(t)
        formal = {
            track: {"result": recorded(r["result"]), "evaluation": recorded(r["evaluation"]),
                    "measurement": r["measurement"], "outcome": r["outcome"],
                    "fixture_matches_release": r["fixture"]["all_release_files_match"]}
            for track, r in review["formal_measurements"].items()
        }
        native = [
            {"result": recorded(r), "success": r.get("evaluation_success"),
             "fixture_matches_release": r["fixture"]["all_release_files_match"],
             "differing_fixture_files": r["fixture"]["mismatched_or_missing_release_files"]}
            for r in review["native_references"]
        ]
        row = {
            "task_id": task_id, "previous_category": inv["category"],
            "current_exact_version": {"definitions": definitions, "scorer": source,
                                     "fixture": [recorded(p) for p in review["source_hashes"]["release_fixture_files"]],
                                     "runtime_source_sha256": selected["source_sha256"]},
            "independent_review": {"reviewer": quality["reviewer"], "construct": review["construct_findings"],
                                   "difficulty": review["difficulty"], "source": pin(QUALITY)},
            "historical_formal": formal, "historical_native": native,
            "remaining_gates": [], "category_recommendation": "implemented_awaiting_tests",
            "historical_outcomes_unchanged": True, "fresh_current_native_completion": False,
        }
        if task_id == "mining_workshop_restart":
            row["bridge"] = mining_bridge(review, tasks)
            row["category_recommendation"] = "fully_validated_integrated"
            row["qualification_scope"] = "Development readiness: pinned historical whole-legal ST/VM success, valid historical model pair, exact current predicate replay, declared task-text equivalence and current selected-runtime read-only compatibility; not fresh current-runtime gameplay/statistical calibration."
        else:
            row["remaining_gates"] = [blockers[task_id]]
            if task_id == "route_schema_transfer":
                row["bridge"] = route_bridge(review, tasks)
            else:
                row["bridge"] = other_archives(review, tasks)
            row["next_validation"] = {
                "authorization": "NOT AUTHORIZED; parent approval required before any native/model episode",
                "definitions": definitions, "source_manifest": report["manifest"],
                "runtime": selected["ready"], "runtime_home": selected["home"],
                "episode_cap_seconds": 2700, "repetitions": 1,
                "track": "visual_motor" if task_id != "route_schema_transfer" else "structured_tool and visual_motor",
                "actors": 2 if task_id == "shared_crossing_camp" else 1,
                "method": "Whole public-control native witness, no model required" if task_id != "route_schema_transfer" else "One valid formal diagnostic per track on released mapping5; retain failures as failures. No replacement native pair needed for the bounded development bridge.",
                "controls": "VM screenshots plus admitted X11 keyboard/mouse only; mouse_move_to for GUI. ST only frozen YAML tools/public observations. No private NBT, scorer, route journal or telemetry as controller input.",
                "success_check": {"evaluator": tasks["visual_motor"].evaluator,
                                  "parameters": tasks["visual_motor"].evaluator_parameters},
                "output_identity": f"output/task-validation/original-minecraft/{task_id}/closure-v1/<approved-launch-id>/<track>",
                "required_artifacts": ["source/fixture/runtime hashes", "captured resolved configuration and launch ID", "public action/observation journal", "before/after native snapshots with original integrity receipts", "environment and fixture receipts", "whole terminal evaluation and native deaths", "measurement validity and unedited task outcome", "team identities/both snapshots where applicable"],
                "stop": "One bounded episode per approved condition; preserve failures, no auto retries, changes to goal/score/fixture, or expansion to other tasks.",
            }
            if task_id == "route_schema_transfer":
                row["next_validation"]["model"] = load(
                    review["formal_measurements"]["structured_tool"]["result"]["path"])["agent"]
                row["next_validation"]["history_policy"] = "responses-visible-history-v1; fresh episode history per track, no imported mapping2 solution or private native controller trace"
                row["next_validation"]["task_variant"] = 5
                row["next_validation"]["aggregate_episode_cap_seconds"] = 5400
        report["tasks"].append(row)
    report["eligible_promotions"] = ["minecraft/mining_workshop_restart"]
    report["other_to_awaiting_recommendation"] = ["minecraft/route_schema_transfer"]
    report["route_category_reason"] = "Definition mapping5 is unambiguous; remaining evidence gaps are validation work, not an unresolved task implementation or substituted mapping2 condition."
    for target in (ROOT / "checks/minecraft-original-reference-closure.json",
                   DEV / "checks/minecraft-original-reference-closure.json"):
        target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"eligible_promotions": report["eligible_promotions"],
                      "remaining": {r["task_id"]: r["remaining_gates"] for r in report["tasks"]}}))


if __name__ == "__main__":
    main()
