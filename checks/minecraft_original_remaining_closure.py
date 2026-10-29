"""Read-only final-condition replay and constructive review of two original tasks.

Private frozen terminal data are inspected only after diagnostics have closed,
never supplied to their public-motor controllers. No synthesized terminal state
is passed to a scorer, and no archived outcomes are overwritten.
"""
import argparse
from collections import Counter, deque
from copy import deepcopy
from datetime import datetime, timezone
import gzip
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import sys
from uuid import UUID
import zlib

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))

import nbtlib

from benchmark.config import load_task
from checks import minecraft_original_reference_closure as closure
from checks.minecraft_original_terminal_reconciliation import condition, pin, public_trace
from game.minecraft.evaluators.world import AIR, read_blocks


def saved_living(world):
    records, seen = [], set()
    for path in (world / "entities").glob("r.*.*.mca"):
        with path.open("rb") as stream:
            header = stream.read(8192)
            if not header:
                continue
            assert len(header) == 8192
            for index in range(1024):
                entry = header[index * 4:index * 4 + 4]
                sector, sectors = int.from_bytes(entry[:3], "big"), entry[3]
                if sector == sectors == 0:
                    continue
                assert sector >= 2 and sectors > 0
                stream.seek(sector * 4096)
                size = int.from_bytes(stream.read(4), "big")
                assert 1 <= size <= sectors * 4096 - 4
                payload = stream.read(size)
                assert len(payload) == size
                codec, raw = payload[0], payload[1:]
                if codec == 1:
                    raw = gzip.decompress(raw)
                elif codec == 2:
                    raw = zlib.decompress(raw)
                else:
                    assert codec == 3, "Unsupported entity encoding; do not infer missing evidence"
                chunk = nbtlib.File.parse(BytesIO(raw))
                assert int(chunk["DataVersion"]) == 3700
                pending = list(chunk["Entities"])
                while pending:
                    entity = pending.pop()
                    pending.extend(entity.get("Passengers", []))
                    if "Health" not in entity or float(entity["Health"]) <= 0:
                        continue
                    identity = tuple(map(int, entity["UUID"]))
                    assert identity not in seen
                    seen.add(identity)
                    records.append({
                        "id": str(entity["id"]), "uuid": list(identity),
                        "position": list(map(float, entity["Pos"])),
                        "health": float(entity["Health"]),
                        "raid_id": int(entity.get("RaidId", -1)),
                        "wave": int(entity.get("Wave", -1)),
                    })
    return records


def ground_path(blocks, start, goals, y=72):
    """Conservative cardinal path on full grass/wool/stone ground and air headroom."""
    floor = {"minecraft:grass_block", "minecraft:cobblestone", "minecraft:stone",
             "minecraft:yellow_wool", "minecraft:oak_planks"}
    safe = {(x, z) for (x, level, z), name in blocks.items() if level == y - 1
            and name in floor and all(blocks.get((x, level + dy, z)) in AIR for dy in (1, 2))}
    assert start in safe, ("start_not_ground_clear", start)
    parents, queue = {start: None}, deque([start])
    found = None
    while queue:
        point = queue.popleft()
        if point in goals:
            found = point
            break
        x, z = point
        for nxt in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if nxt in safe and nxt not in parents:
                parents[nxt] = point
                queue.append(nxt)
    assert found is not None, "No conservative saved-world ground continuation"
    path = []
    while found is not None:
        path.append([found[0], y, found[1]])
        found = parents[found]
    return list(reversed(path))


def verify_diagnostic(root, task_id, folder, runtime):
    episode = root / "output/task-validation/original-minecraft-resume-20261029" / folder
    task = load_task(SOURCE / f"config/minecraft/tasks/visual_motor/{task_id}.yaml")
    source, result = closure.load(episode / "source.json"), closure.load(episode / "result.json")
    assert condition(source["task"]) == condition(task.resolved())
    assert result["task_sha256"] == task.source.sha256
    assert result["time_limit_seconds"] == task.time_limit_seconds
    assert result["kind"] == "route_disclosed_public_motor_diagnostic_not_model_measurement"
    assert source["final_task_fixture_and_resources_modified"] is False
    assert closure.sha(episode / "controller-harness.py") == source["harness_sha256"]
    fixture = closure.load(episode / "game/fixture.json")
    world = Path(task.fixture["world_path"])
    files = {str(path.relative_to(world)): closure.sha(path)
             for path in world.rglob("*") if path.is_file()}
    assert fixture["sha256"] == files
    environment = closure.load(episode / "game/environment.json")
    assert environment["client_build_sha256"] == runtime["source_sha256"]
    endpoints = [closure.snapshot(episode / phase) for phase in ("before", "after")]
    assert [row["phase"] for row in endpoints] == ["ready", "ended"]
    assert endpoints[0]["player_uuid"] == endpoints[1]["player_uuid"]
    assert endpoints[0]["boundaries"]["ready_at_ns"] == endpoints[1]["boundaries"]["ready_at_ns"]
    binding = closure.binding(task)
    binding.game.player_uuid = UUID(endpoints[0]["player_uuid"])
    binding.game.player_state.verify(nbtlib.load(
        episode / "before/playerdata" / f"{binding.game.player_uuid}.dat"), binding.game.player_uuid)
    binding.verify_initial(episode / "before")
    assert binding.evaluate(episode / "before", episode / "after") == result["evaluation"]
    assert binding.metrics(episode / "before", episode / "after") == result["metrics"]
    trace = public_trace(episode, result, endpoints[1]["boundaries"])
    player = nbtlib.load(episode / "after/playerdata" / f"{binding.game.player_uuid}.dat")
    stats = closure.load(episode / "after/stats" / f"{binding.game.player_uuid}.json")["stats"]
    inventory = Counter()
    for item in player["Inventory"]:
        inventory[str(item["id"])] += int(item["Count"])
    leases = []
    for path in (root / "output/temp/task_development/leases").glob("*.json"):
        lease = closure.load(path)
        if lease["task"] == {
            "expedition_record_reconstruction": "original-expedition-route-access-20261029",
            "prepared_village_defense": "original-raid-public-composition-20261029",
        }[task_id]:
            assert lease["returncode"] == 0 and lease["status"] == "finished"
            assert not any(Path(f"/proc/{lease[k]}").exists() for k in ("lease_pid", "command_pid"))
            leases.append({"receipt": pin(path), "record": lease})
    assert len(leases) == 1
    return {
        "task_id": task_id, "source": pin(episode / "source.json"),
        "result": pin(episode / "result.json"), "terminal": result,
        "fixture": pin(episode / "game/fixture.json"), "release_fixture_files_exact": len(files),
        "environment": pin(episode / "game/environment.json"), "snapshots": endpoints,
        "trace": trace, "leases": leases, "terminal_inventory": dict(inventory),
        "terminal_statistics": stats, "terminal_position": list(map(float, player["Pos"])),
        "current_scorer_and_metrics_equal": True,
    }


def raid_continuation(root, proof):
    episode = root / "output/task-validation/original-minecraft-resume-20261029/raid-public-composition-01"
    world = episode / "after"
    living = saved_living(world)
    enemies = [row for row in living if row["id"] in {
        "minecraft:pillager", "minecraft:vindicator", "minecraft:ravager",
        "minecraft:evoker", "minecraft:witch", "minecraft:vex"}]
    assert len(enemies) == 1 and enemies[0]["id"] == "minecraft:pillager"
    assert enemies[0]["wave"] == 3 and enemies[0]["raid_id"] >= 0
    villagers = [row for row in living if row["id"] == "minecraft:villager"]
    assert villagers
    blocks = read_blocks(world, (-40, 71, -40), (65, 75, 40), "minecraft:overworld")
    player = proof["terminal_position"]
    start = math.floor(player[0]), math.floor(player[2])
    enemy = enemies[0]["position"]
    goal = math.floor(enemy[0]), math.floor(enemy[2])
    approach = ground_path(blocks, start, {goal})
    attack_stand = approach[-3]
    approach = approach[:-2]
    eye = (attack_stand[0] + .5, attack_stand[1] + 1.62, attack_stand[2] + .5)
    aim = (enemy[0], enemy[1] + 1, enemy[2])
    reach = math.dist(eye, aim)
    assert reach < 3
    for step in range(101):
        point = tuple(math.floor(a + (b - a) * step / 100) for a, b in zip(eye, aim))
        assert blocks[point] in AIR
    return_path = ground_path(blocks, (attack_stand[0], attack_stand[2]), {(16, 0)})
    elapsed = proof["terminal"]["elapsed_seconds"]
    budget = proof["terminal"]["time_limit_seconds"]
    inventory = proof["terminal_inventory"]
    assert inventory["minecraft:arrow"] >= 4
    assert inventory["minecraft:diamond_sword"] == inventory["minecraft:bow"] == 1
    assert inventory["minecraft:cooked_beef"] >= 4
    assert proof["terminal_statistics"]["minecraft:killed"]["minecraft:ravager"] == 1
    raid = nbtlib.load(world / "data/raids.dat")["data"]["Raids"]
    assert len(raid) == 1
    saved_raid = raid[0]
    assert str(saved_raid["Status"]) == "ongoing"
    assert int(saved_raid["GroupsSpawned"]) == int(saved_raid["NumGroups"]) == 3
    assert int(saved_raid["BadOmenLevel"]) == 1
    active_ticks = int(saved_raid["TicksActive"])
    assert 0 <= active_ticks < 48000
    native_remaining_seconds = (48000 - active_ticks) / 20
    hero_uuid = tuple(map(int, nbtlib.load(
        world / "playerdata" / f"{proof['snapshots'][0]['player_uuid']}.dat")["UUID"]))
    assert any(tuple(map(int, value)) == hero_uuid for value in saved_raid["HeroesOfTheVillage"])
    reserve = {
        "locating_and_following_last_pillager_seconds": 300,
        "closing_melee_or_bow_control_seconds": 120,
        "protected_recovery_allowance_seconds": 120,
        "return_and_settling_seconds": 120,
        "native_final_wave_victory_delay_seconds": 60,
    }
    assert sum(reserve.values()) < min(budget - elapsed, native_remaining_seconds)
    return {
        "kind": "post_terminal_constructive_same_episode_continuation_not_executed_success",
        "world": pin(world / "_livequest_snapshot.json"),
        "remaining_raiders": enemies, "living_residents": villagers,
        "ongoing_raid": {"groups_spawned": int(saved_raid["GroupsSpawned"]),
                        "groups_total": int(saved_raid["NumGroups"]),
                        "bad_omen_level": int(saved_raid["BadOmenLevel"]),
                        "native_hero_candidate_contains_initialized_player": True},
        "ground_approach": approach, "ground_return": return_path,
        "attack_position": attack_stand, "native_melee_reach_metres": reach,
        "static_attack_line_clear": True,
        "cardinal_ground_steps": len(approach) + len(return_path) - 2,
        "remaining_original_seconds": budget - elapsed,
        "native_raid_deadline": {
            "timeout_active_ticks": 48000, "terminal_active_ticks": active_ticks,
            "remaining_active_ticks": 48000 - active_ticks, "nominal_tps": 20,
            "nominal_remaining_seconds": native_remaining_seconds,
            "nominal_margin_after_plan_seconds": native_remaining_seconds - sum(reserve.values()),
            "basis": "Independent pinned1.20.4 Raid.tick review; active-tick conversion is not a measured wall-clock upper bound.",
        },
        "authored_control_allocation_not_measured_upper_bound": reserve,
        "allocation_total_seconds": sum(reserve.values()),
        "argument": "Both the original2700-second task deadline and the native48000-active-tick raid timeout constrain continuation; nominal native time remaining is tighter. The SAME saved episode has one ordinary third-wave pillager, living residents, initialized-player native hero candidacy, reachable level ground, sword/bow and surplus food/ammunition. Reacquire and track the moving target, manage exposure and food recovery, finish it, remain alive through40-tick native settlement, then return. Earlier public VM frames and this run demonstrate bow hits, killing the stronger ravager, recovery and legal controls. No result or native advancement is fabricated.",
        "limits": [
            "The path and ray verify frozen geometry, not future target position, dynamic hit timing, survival or elapsed time.",
            "The720-second allocation is an unexecuted plan, not a measured dynamic upper bound or model-latency guarantee. At20TPS the native remainder is1613.9seconds and nominal margin893.9seconds; task-only1855.55seconds is not unrestricted raid lifetime.",
            "Current terminal remains failure: raid_win0, Hero false, return false. A particular controller victory is not required by acceptance policy.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    closure.DEV = root / "output/temp/task_development"
    closure.HOME = closure.DEV / "minecraft-runtime/MC-R05-main-vitals-placement-cart-v1"
    runtime = closure.runtime()
    quality_path = closure.DEV / "checks/minecraft-independent-quality.json"
    reviews = {row["task_id"]: row for row in closure.load(quality_path)["original_reference_coverage"]}
    tasks = []
    for task_id, folder in (
        ("expedition_record_reconstruction", "expedition-route-access-01"),
        ("prepared_village_defense", "raid-public-composition-01"),
    ):
        proof = verify_diagnostic(root, task_id, folder, runtime)
        review = deepcopy(reviews[task_id])
        for row in review["formal_measurements"].values():
            row["result"]["path"] = str(root / row["result"]["path"])
        for row in review["native_references"]:
            row["path"] = str(root / row["path"])
        definitions = {track: load_task(SOURCE / f"config/minecraft/tasks/{directory}/{task_id}.yaml")
                       for track, directory in (("structured_tool", "structured_tools"), ("visual_motor", "visual_motor"))}
        proof["retained_archives_current_replay"] = closure.other_archives(review, definitions)
        proof["independent_mechanism_review"] = review["construct_findings"]
        proof["independent_difficulty_review"] = review["difficulty"]
        proof["independent_review"] = pin(quality_path)
        proof["known_blocking_task_bug"] = None
        proof["remaining_admission_gates"] = []
        proof["recommendation"] = "policy_supported_pending_independent_review_and_parent_integration"
        proof["nonblocking_calibration"] = "Deferred; no autonomous search/learning or model-performance claim."
        if task_id == "expedition_record_reconstruction":
            assert proof["terminal"]["evaluation"]["success"] is True
            proof["closure"] = {
                "feasibility": "One unchanged-world VM episode retrieved all three exact originals and returned alive, grounded and settled within493.15seconds; no stitched endpoints.",
                "information_access": "Public screenshots show Day1 office clues and revised Day3 quarry clues. Coordinates/routes were disclosed to this controller, so this is clue-readability/access evidence, not an unhinted reasoning measurement.",
                "screenshots": [pin(root / "output/task-validation/original-minecraft-resume-20261029" / folder / f"frame-{i:03d}-Player.png") for i in (3, 4, 11, 12, 40)],
                "final_condition_transfer": "Only controller information was simplified. Geometry, chest identity tags, materials, digging/step-up interactions, inventory, native death behavior and return predicates were unchanged and checked in this same episode.",
            }
        else:
            proof["constructive_continuation"] = raid_continuation(root, proof)
            proof["closure"] = {
                "controller_bug_resolved": "Archived mouse_move_absolute operator error is replaced by admitted mouse_move_to in the new diagnostic; three native respawns preserve the ongoing raid and inventory.",
                "feasibility": "Independent whole native ST evidence plus this exact-condition VM prefix and native-grounded remaining-stage argument; no fabricated VM victory.",
                "safety_learning": "The first low shelter-roof position did not prevent ravager damage. A higher legal cobblestone pillar, sneak-edge visibility and native bow attacks killed the ravager; the pillar was then dismantled with the initialized pickaxe.",
                "final_condition_transfer": "No reduced raider health or changed equipment, protected residents, loot, world or scoring. Only the diagnostic's control window was900seconds instead of the task2700seconds.",
            }
        tasks.append(proof)
    report = {
        "schema": "livequest-original-minecraft-remaining-closure/1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"root": str(SOURCE), "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip(),
            "checker": pin(Path(__file__)), "harness": pin(SOURCE / "checks/minecraft_original_motor_diagnostic.py")},
        "runtime": runtime, "tasks": tasks, "new_native_episodes": 2, "new_model_calls": 0,
        "focused_tests": {
            "log": pin(closure.DEV / "checks/resume-minecraft-remaining-tests-20261029.log"),
            "output": (closure.DEV / "checks/resume-minecraft-remaining-tests-20261029.log").read_text(),
            "selectors": ["tests/test_game/minecraft/test_original_terminal_reconciliation.py",
                          "tests/test_game/minecraft/test_game.py"],
            "markers": "not game and not live",
        },
        "max_concurrent_owned_native_episodes": 1,
        "final_task_fixture_runtime_changed": False, "main_integration_performed": False,
        "ledger_edits": False,
        "transferred_scope": {"task_id": "shared_crossing_camp", "own_changes_or_native_runs": 0,
                              "owner": "dedicated shared-camp worker", "not_part_of_this_recommendation": True},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "recommendations": [row["task_id"] for row in tasks]}))


if __name__ == "__main__":
    main()
