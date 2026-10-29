"""Replay retained crossing evidence and a fixture-grounded material counterexample.

This checker never launches a game, starts a controller, or edits an archive.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import nbtlib

from benchmark.config import load_task
from checks.minecraft_original_reference_closure import binding, snapshot
from game.minecraft.evaluators.crossing import BANK_BLOCKS, connected
from game.minecraft.evaluators.world import read_blocks


def load(path):
    return json.loads(path.read_text())


def pin(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def review(evidence_root):
    freeze_path = evidence_root / "output/task-validation/original-minecraft-closure/source-freeze.json"
    freeze = load(freeze_path)
    original_root = Path(freeze["source_root"])
    original_scorer = original_root / "game/minecraft/evaluators/crossing.py"
    spec = importlib.util.spec_from_file_location("frozen_crossing", original_scorer)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    fixture = ROOT / "config/minecraft/fixtures/shared_crossing_camp"
    fixture_hashes = {str(p.relative_to(fixture)): pin(p)["sha256"]
                      for p in sorted(fixture.rglob("*")) if p.is_file()}
    for name, digest in fixture_hashes.items():
        assert pin(original_root / "config/minecraft/fixtures/shared_crossing_camp" / name)["sha256"] == digest
    inputs = ["minecraft-original-reference-closure.json", "minecraft-independent-quality.json",
              "minecraft-acceptance-policy-audit-20261029.json", "resume-minecraft-20261029.json",
              "task-delivery-status.json"]
    report = {
        "schema": "original-minecraft-crossing-bank-review-v1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": "minecraft/shared_crossing_camp",
        "source": {
            "worktree": str(ROOT),
            "base_commit": freeze["source_commit"],
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "freeze": pin(freeze_path),
            "frozen_scorer": pin(original_scorer),
            "changed_files": [pin(ROOT / name) for name in (
                "game/minecraft/evaluators/crossing.py",
                "tests/test_game/minecraft/test_structure.py",
                "docs/reference_tasks.md", "checks/minecraft_crossing_bank_review.py")],
            "fixture_sha256": fixture_hashes,
            "task_definitions": [],
        },
        "review_inputs": [pin(evidence_root / "output/temp/task_development/checks" / name)
                          for name in inputs],
        "policy": pin(evidence_root / "output/survey/task_difficulty_and_capability_acceptance_20261027.md"),
        "new_native_episodes": 0, "new_model_calls": 0, "new_agents": 0,
        "main_integration_performed": False, "ledger_edits": False,
        "historical_outcomes_rewritten": False,
        "archives": [],
    }
    test_log = evidence_root / "output/temp/task_development/checks/parallel-mc-crossing-20261029-tests.log"
    if test_log.is_file():
        report["focused_tests"] = {"log": pin(test_log), "output": test_log.read_text()}
    closure = load(evidence_root / "output/temp/task_development/checks/minecraft-original-reference-closure.json")
    retained = next(t for t in closure["tasks"] if t["task_id"] == "shared_crossing_camp")
    for directory, track in (("structured_tools", "structured_tool"), ("visual_motor", "visual_motor")):
        definition = ROOT / f"config/minecraft/tasks/{directory}/shared_crossing_camp.yaml"
        assert pin(definition)["sha256"] == freeze["task_sources"][str(definition.relative_to(ROOT))]
        report["source"]["task_definitions"].append(pin(definition))
        task = load_task(definition)
        b = binding(task)
        old = retained["historical_formal"][track]
        result_path = evidence_root / old["result"]["path"]
        evaluation_path = evidence_root / old["evaluation"]["path"]
        assert pin(result_path)["sha256"] == old["result"]["sha256"]
        assert pin(evaluation_path)["sha256"] == old["evaluation"]["sha256"]
        episode = result_path.parent.parent
        configuration = next(p / "config.json" for p in episode.parents if (p / "config.json").is_file())
        captured = load(configuration)["tasks"][0]
        assert captured["evaluator_parameters"] == task.evaluator_parameters
        assert captured["time_limit_seconds"] == task.time_limit_seconds == 2700
        owner_fixture = load(episode / "game/Alpha/fixture.json")
        assert owner_fixture["sha256"] == fixture_hashes
        roles = {}
        for role, member in b.game.members.items():
            receipts = [snapshot(episode / phase / role) for phase in ("before", "after")]
            assert receipts[0]["player_uuid"] == receipts[1]["player_uuid"]
            player = member.game.player_uuid = UUID(receipts[0]["player_uuid"])
            member.game.player_state.verify(
                nbtlib.load(episode / "before" / role / "playerdata" / f"{player}.dat"), player)
            final = nbtlib.load(episode / "after" / role / "playerdata" / f"{player}.dat")
            journal_path = episode / "participants" / role / "recording/chat/agent.jsonl"
            journal = [json.loads(line) for line in journal_path.read_text().splitlines()]
            final_messages = [{"line": i, "content": row["message"]["content"]}
                              for i, row in enumerate(journal, 1)
                              if row.get("event") == "message"
                              and row.get("message", {}).get("role") == "assistant"
                              and row["message"].get("content")]
            roles[role] = {
                "snapshots": receipts,
                "position": list(map(float, final["Pos"])),
                "health": float(final["Health"]), "food": int(final["foodLevel"]),
                "inventory": {str(item["id"]): int(item["Count"]) for item in final["Inventory"]},
                "public_journal": pin(journal_path),
                "last_public_text": final_messages[-1] if final_messages else None,
            }
        b.verify_initial(episode / "before")
        replay = b.evaluate(episode / "before", episode / "after")
        historical = load(evaluation_path)
        normalized = deepcopy(historical)
        normalized["schema"] = "team-endpoints"
        for role in roles:
            normalized["checks"][2]["roles"][role]["checks"][1]["result"]["version"] = "minecraft-1.20.4-structure"
        normalized["checks"][0]["result"]["semantics"] = replay["checks"][0]["result"]["semantics"]
        assert normalized == replay
        result = load(result_path)
        assert result["measurement"] == "valid"
        assert (result["task_outcome"] == "success") == replay["success"]
        report["archives"].append({
            "track": track, "episode": str(episode), "result": pin(result_path),
            "evaluation": pin(evaluation_path), "configuration": pin(configuration),
            "owner_fixture": pin(episode / "game/Alpha/fixture.json"),
            "fixture_bytes_match": True, "native_receipts_verified": True,
            "launch_id": result["launch_id"], "configuration_sha256": result["configuration_sha256"],
            "active_wall_seconds": result["timing"]["active_wall_seconds"],
            "deadline_reached": result["deadline_reached"], "roles": roles,
            "historical_measurement": result["measurement"],
            "historical_outcome": result["task_outcome"],
            "corrected_replay": replay, "all_predicate_values_and_verdicts_preserved": True,
            "normalization": ["team schema label", "structure version labels", "crossing semantics text"],
        })

    goal = task.evaluator_parameters["crossing"]
    initial = read_blocks(fixture, goal["region"]["min"], goal["region"]["max"], "minecraft:overworld")
    banks = frozenset(p for p, material in initial.items() if p[1] == 71 and material in BANK_BLOCKS)
    gap = [(x, 71, 0) for x in range(6, 11)]
    assert all(initial[p] == "minecraft:air" for p in gap)
    legal = initial | {p: "minecraft:oak_planks" for p in gap}
    mixed = legal | {(6, 71, 0): "minecraft:yellow_wool"}
    assert original.connected(mixed, **goal)
    assert not connected(mixed, banks=banks, **goal)
    assert connected(legal, banks=banks, **goal)
    resources = read_blocks(fixture, [-20, 71, -12], [32, 78, 22], "minecraft:overworld")
    assert resources[0, 71, 0] == "minecraft:yellow_wool"
    counts = Counter(material for p, material in resources.items() if p[1] >= 72)
    report["counterexample"] = {
        "kind": "offline_block-map_counterexample_not_a_native_episode",
        "source_wool": [0, 71, 0], "destination_wool": [6, 71, 0],
        "remaining_deck": [[x, 71, 0] for x in range(7, 11)],
        "frozen_scorer_accepts": True, "corrected_scorer_accepts": False,
        "all_declared_material_deck_still_passes": True,
        "legal_resource_route": "Break the spare spawn marker, not either crossing endpoint; use its ordinary wool drop for one interior cell and four oak planks for the others.",
        "scope": "A concrete material-rule false positive, not proof of a whole-task exploit episode.",
        "preserved_bank_repairs": "Historical ST moves yellow wool from x12 to x11 on the existing bank. Bank support remains allowed at originally grass/wool cells; no new material-identity or contributor rule.",
    }
    report["feasibility"] = {
        "status": "resource_and_geometry_grounded_plan_with_unresolved_VM_composition",
        "sample_region": {"min": [-20, 71, -12], "max": [32, 78, 22]},
        "accessible_above_ground_resources": {
            "oak_logs": counts["minecraft:oak_log"], "stone": counts["minecraft:stone"],
            "crafting_table": [-1, 72, 7],
        },
        "construction_balance": {
            "bridge": {"oak_planks": 5},
            "shelter": {"cobblestone": 7, "oak_planks": 16, "empty_cells": 4},
            "minimum_harvest": {"oak_logs": 6, "stone": 7},
            "planks_from_six_logs": 24, "plank_surplus": 3,
            "initial_team_bread": 8, "required_terminal_bread": 4,
            "scaffold_material": "Separate dirt or surplus stone; remove any obstruction to headroom/door/interior. Not part of the accepted new deck.",
        },
        "legal_role_allocation": [
            "Either peer may mine seven stone with the supplied iron pickaxe and build the seven-block lower shelter perimeter.",
            "Either peer may harvest six oak logs with the supplied iron axe, craft 24 planks in the inventory grid, build the five-cell deck and sixteen shelter planks.",
            "Alternatively one builder can gather/build everything; the other crosses and reunites later. Chat and balanced contributions are optional.",
        ],
        "navigation": "Initial west-bank resources are reachable on y72. Bridge x6..10 at y71/z0 leads to the east bank. Travel east then south to the white 3x3 footprint x24..26/z8..10; the reunion yellow marker is x22/z9, not the bank marker x12/z0.",
        "joint_endpoint": "Retain the bridge, leave shelter doorway/interior clear, keep at least four bread total, and release inputs with both living players grounded within horizontal distance 3 of (22.5,72,9.5). No death-free history is required.",
        "observations": "Public text supplies materials, north-facing doorway, footprint and relative landmarks. VM uses screenshots/inventory UI and keyboard/mouse only. These offline NBT coordinates/resources are reviewer evidence, not permitted live controller input.",
        "time": "Both retained episodes ended voluntarily near 914 seconds, not at the 2700-second cap. ST demonstrates joint physical endpoints; VM demonstrates legal deck construction, mining and food retention. Spare time alone is not a measured VM shelter/return bound.",
        "unresolved": "No retained VM shelter construction or correct-marker reunion evidence. ST and VM partials are not concatenated into a success. GUI crafting, roof placement/reach, landmark identification and both-player completion must be independently grounded within one lawful budget.",
    }
    report["acceptance"] = {
        "known_bug": "Interior yellow-wool/grass deck false positive fixed in isolated source; not integrated.",
        "construct": "Shared building/resource dependencies and distinct starts support optional coordination. No causal cooperation advantage or equal-participation necessity is claimed.",
        "difficulty": "Historical ST3/VM4 provisional only; nonblocking calibration deferred under October29 policy.",
        "remaining_gate": "Parent choice on scoring-source integration and targeted VM composition evidence; no mandatory authored-controller or model victory.",
        "targeted_native_proposal": "If capacity is approved, use one separately identified public-VM shelter/reunion diagnostic to test log-to-plank GUI crafting, the exact 23-block shell/roof and two living players reaching the correct marker. Bind any supplied materials/start-state changes explicitly; do not infer original gathering/time composition from it. Alternatively obtain an exact-condition VM construction/timing witness. No launch authorized or performed.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = review(args.evidence_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "archives_replayed": len(report["archives"]),
                      "new_native_episodes": 0, "material_counterexample_rejected": True}))


if __name__ == "__main__":
    main()
