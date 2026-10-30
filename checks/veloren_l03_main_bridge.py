"""Offline C1 semantic/pin and complete retained endpoint bridge; never launches a game."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import yaml

from benchmark.config import load_experiment
from benchmark.factory import validate_experiment
from game.veloren.evaluators.deaths import evaluate_deaths
from game.veloren.evaluators.encounter import evaluate_encounter
from game.veloren.prototypes.combat_response_runtime import admit_response_assets
from game.veloren.runtime.combat_response import RUNTIMES


ROOT = Path(__file__).resolve().parents[1]
WORKTREE = ROOT / "output/temp/task_development/worktrees/dedicated-ve-l03-20261029"
OUTPUT = WORKTREE / "output/checks"
CHECKS = ROOT / "output/temp/task_development/checks"
REVIEW_SHA = "906eed607ae2a8afebbb9b991a5afcadc26fb2f5ef3a47b3cbb00f737ed4075d"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    review = json.loads((CHECKS / "veloren-acceptance-policy-audit-20261029.json").read_text())["dated_addenda"][93]
    assert hashlib.sha256(json.dumps(review, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest() == REVIEW_SHA
    before = json.loads((CHECKS / "L03-main-integration-before-20261030.json").read_text())
    exact_sources = {}
    for module in ("combat_family", "combat_response_assets", "combat_response_runtime",
                   "combat_response_transfer", "combat_source_binding"):
        name = f"game/veloren/prototypes/{module}.py"
        assert (ROOT / name).read_bytes() == (WORKTREE / name).read_bytes()
        exact_sources[name] = digest(ROOT / name)
    unchanged = {}
    for name in (
        "benchmark/factory.py", "game/veloren/binding.py", "game/veloren/native_bindings.py",
        "game/veloren/runtime/journal.py", "game/veloren/runtime/item_use.py",
        "game/veloren/evaluators/encounter.py", "game/veloren/evaluators/deaths.py",
        "game/veloren/structured_tools/interface.py", "game/veloren/visual_motor/interface.py",
    ):
        base = subprocess.check_output(["git", "show", f"{before['head']}:{name}"], cwd=ROOT)
        assert (ROOT / name).read_bytes() == base
        unchanged[name] = digest(ROOT / name)
    task_mappings = {}
    for track, folder in (("structured_tool", "structured_tools"), ("visual_motor", "visual_motor")):
        old_path = OUTPUT / "native-runtime-parameter-a" / f"prototype-{track}.yaml"
        new_path = ROOT / "config/veloren/tasks" / folder / "native_combat_response_transfer_c1.yaml"
        assert old_path.read_bytes() == (OUTPUT / "native-runtime-parameter-b" / old_path.name).read_bytes()
        old, new = (yaml.safe_load(p.read_text()) for p in (old_path, new_path))
        old_world = Path(old["fixture"]["world_path"])
        new_world = (new_path.parent / new["fixture"]["world_path"]).resolve()
        assert digest(old_world) == digest(new_world)
        expected_text = old["task"].replace(
            "NONCANONICAL EXPERIMENT: NOT AN ACCEPTED LEARNING TASK.",
            "DEVELOPMENTAL C1: OPTIONAL SAME-EPISODE COMBAT-RESPONSE REUSE.",
        ).replace(
            "this bundle does not change observation permissions or claim ST readiness.",
            "this task does not change observation permissions.",
        ).replace(
            "This proposal has not established that history helps over safe generic play,\n"
            "that the shared encounter is feasible, or that difficulty is moderate.",
            "Learning is optional. This endpoint score does not measure learning or whole-task\n"
            "learning benefit. Generic tactics remain legal; population difficulty is uncertain.",
        )
        assert new["task"] == expected_text
        old["task"] = expected_text
        old["fixture"]["world_path"] = new["fixture"]["world_path"]
        assert old == new
        task_mappings[track] = {
            "historical_sha256": digest(old_path), "registered_path": str(new_path.relative_to(ROOT)),
            "registered_sha256": digest(new_path), "world_sha256": digest(new_world),
            "changes_only": ["status/claim wording, exact replacements checked", "equivalent world path"],
        }
    validate_experiment(load_experiment(ROOT / "config/veloren/experiments/native_combat_response_transfer_c1.yaml"))
    runtimes, assets = {}, {}
    for track, options in RUNTIMES.items():
        for selection, (directory, expected) in enumerate(options):
            path = OUTPUT / directory / "runtime.json"
            assert digest(path) == expected
            cfg = json.loads(path.read_text())
            for name, pin in cfg["sha256"].items():
                assert digest(name) == pin, name
            assert digest(cfg["upstream_runtime"]) == cfg["upstream_sha256"]
            declaration = cfg["experimental_combat_response_assets"]
            assert declaration["selection"] == selection
            if selection not in assets:
                upstream_path = Path(cfg["upstream_runtime"])
                upstream = json.loads(upstream_path.read_text())["renderer"]

                def bound(name):
                    p = Path(upstream[name])
                    return p if p.is_absolute() else upstream_path.parent / p

                assets[selection] = admit_response_assets(
                    declaration, bound("assets"), bound("assets_manifest"),
                )
            runtimes[f"{track}_{selection}"] = {
                "path": str(path.relative_to(ROOT)), "sha256": expected,
                "all_declared_pins_verified": True,
                "selection": selection, "asset_manifest_sha256": declaration["manifest_sha256"],
            }
    roles = json.loads((OUTPUT / "runtime-role-bindings.json").read_text())["roles"]
    binaries = {}
    for name in ("server", "fixture_helper", "selected_patched_renderer"):
        row = roles[name]
        assert digest(row["path"]) == row["sha256"]
        binaries[name] = row
    composition = json.loads((OUTPUT / "composed-source-verification.json").read_text())
    cfg = json.loads((OUTPUT / RUNTIMES["visual_motor"][0][0] / "runtime.json").read_text())
    manifest = next(Path(p) for p in cfg["sha256"] if p.endswith("/native/source.json"))
    expected_source = json.loads(manifest.read_text())["files_sha256"]
    expected_source.update(composition["patched_file_sha256"])
    source = Path(cfg["source"])
    actual_source = {p.relative_to(source).as_posix(): digest(p) for p in source.rglob("*") if p.is_file()}
    assert actual_source == expected_source
    source_tree = hashlib.sha256(json.dumps(actual_source, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert source_tree == composition["composed_source_tree_sha256"]
    old_results = json.loads(subprocess.check_output([
        sys.executable, "-c",
        "import json;from pathlib import Path;"
        "from game.veloren.evaluators.encounter import evaluate_encounter;"
        "from game.veloren.evaluators.deaths import evaluate_deaths;"
        "root=Path('output/checks');result={}\n"
        "for p in sorted(root.glob('native-*/after/observation.json')):\n"
        " b=p.parents[1]/'before';a=p.parent;o=json.loads((b/'observation.json').read_text());"
        " roles=[r['role'] for r in o.get('private_encounter_evidence',{}).get('registry',{}).get('targets',[])];"
        " result[p.parents[1].name]={'score':evaluate_encounter(b,a,roles=roles,no_death=True,min_health=1) if roles else None,"
        "'metrics':evaluate_deaths(b,a)}\n"
        "print(json.dumps(result))",
    ], cwd=WORKTREE, text=True))
    replays = []
    for episode, historical in old_results.items():
        directory = OUTPUT / episode
        first = json.loads((directory / "before/observation.json").read_text())
        roles = [r["role"] for r in first.get("private_encounter_evidence", {}).get("registry", {}).get("targets", [])]
        score = evaluate_encounter(directory / "before", directory / "after", roles=roles, no_death=True, min_health=1) if roles else None
        metrics = evaluate_deaths(directory / "before", directory / "after")
        assert metrics == historical["metrics"]
        if score is not None:
            expected = dict(historical["score"])
            expected["semantics"] = expected["semantics"].replace(
                "No last-blow requirement; disappearance", "No last-blow requirement. Disappearance")
            assert score == expected, episode
        frozen = json.loads((directory / "result.json").read_text())
        frozen_scores = {key: value for key, value in frozen.items() if key.endswith("_score")}
        for value in frozen_scores.values():
            expected = dict(value)
            expected["semantics"] = expected["semantics"].replace(
                "No last-blow requirement; disappearance", "No last-blow requirement. Disappearance")
            assert score == expected, episode
        replays.append({
            "episode": episode,
            "inputs": {name: digest(directory / name) for name in ("before/observation.json", "after/observation.json", "result.json")},
            "complete_score": score, "complete_metrics": metrics,
            "isolated_full_replay_equal_except_documented_semantics_punctuation": True,
            "persisted_score_keys_equal_except_documented_semantics_punctuation": list(frozen_scores),
            "scope": "Original/simplified/component conditions remain distinct; no new native evidence.",
        })
    for name, expected in before["preserved_files"].items():
        assert digest(ROOT / name) == expected, name
    assert digest(CHECKS / "task-delivery-status.json") == before["ledger_sha256"]
    assert digest(CHECKS / "task-delivery-status.csv") == before["csv_sha256"]
    receipt = {
        "schema": "VE-L03-main-C1-bridge/1", "integration_base_head": before["head"],
        "isolated_quality_source": review["source_commit"], "review93_canonical_sha256": REVIEW_SHA,
        "actual_main_review": "Pending immutable commit/tree review; not admission.",
        "claim": "Optional same-episode response reuse; provisional learning2/high uncertainty; native-observed ST versus task-level constructive VM.",
        "exact_copied_sources": exact_sources, "unchanged_shared_sources": unchanged,
        "task_semantic_mappings": task_mappings, "exact_runtime_mappings": runtimes,
        "complete_asset_admissions": assets, "binary_pins": binaries,
        "composed_native_source": {"files": len(actual_source), "sha256": source_tree},
        "runtime_selection": "One secrets.randbelow(2) draw at each single-use session startup; both exact options checked first; no public selection/seed or global environment mutation; common private assets root for all native roles.",
        "replays": replays,
        "shared_fix_policy": "Reused current native binding cursor, lifecycle, server selector, item wrapper and scorer; no old whole-file imports.",
        "focused_checks": {
            "integration_selectors_assets_public_projection_scorer": "100 passed; no native/model launch.",
            "existing_initialization_suite": "31 passed,6 skipped,1 pre-existing failure in test_injured_companion_waits_for_post_injury_native_binding: its stub requires UID2 but shared warm-up first requests player UID1. Same exact failure reproduced with pre-integration74b4774 fixture module loaded in memory; no companion code or dirty test was changed.",
            "initial_validation_corrections": "Missing pytest-basetemp parent and incorrect task-relative world path were diagnosed and corrected before the final100pass checks.",
            "logs": {name: digest(CHECKS / name) for name in (
                "L03-main-focused-tests-20261030.txt",
                "L03-main-initialization-tests-20261030.txt",
                "L03-main-baseline-initialization-check-20261030.txt",
            )},
        },
        "historical_preservation": "675/46d3dbe/a3429b2 and all earlier outcomes remain unchanged; no four-kill endpoint invented. C2, .90 controller, navigation repair and stronger-sword diagnostic not registered.",
        "unrelated_files_and_ledger_verified_unchanged": True, "new_native_or_model_episodes": 0,
    }
    target = ROOT / "checks/VE-L03-main-integration-bridge-20261030.json"
    target.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(target.relative_to(ROOT)), "sha256": digest(target),
                      "replays": len(replays), "source_files": len(actual_source),
                      "complete_asset_inventories": len(assets), "native_episodes": 0}))


if __name__ == "__main__":
    main()
