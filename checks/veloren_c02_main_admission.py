"""C02-only offline admission against explicit reviewed source and native runtime."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType


REVIEW = "5e1738f432d36789fcf2dfd2922b9b3ea56ded6e"
TASK = "sceptre_and_sword_team"
SCOPES = (
    "benchmark", "game/veloren", "game/backends/x11",
    "game/team.py", "game/base_game.py", "game/bindings.py",
)
BRIDGED = {
    "game/team.py": (
        "bc80b21d245fce6f2d0f37cc457c5339e6d8f97a26fe4d7f7b4b62c37ed86245",
        "Reviewed C05-only escort branches are absent; C02 has neither escort nor companion. "
        "Its team controls, member fixture, support, endpoint and metric paths are retained.",
    ),
    "game/veloren/binding.py": (
        "5825a2549bb0268d00e198fdd85615796c73b25674af7fcfe60134df7298b50e",
        "Additional active_build/encounter_supplies registrations are not selected: "
        "C02 participant bindings use state with the unchanged minimum-health predicate.",
    ),
    "game/veloren/evaluators/encounter.py": (
        "85ff1a3e8f6590492d2cd1a178e5c3a7ce0543a9c3df0508ac99099b42611551",
        "C05-only zero-floor companion/escort additions are absent. C02 has no companion; "
        "source-bound original-target death and support helpers are unchanged.",
    ),
    "game/veloren/fixture.py": (
        "377b1f09c35ec837f8dd1fdc55870821f0a4e689e690ed339866519f22482443",
        "Immediate fallback bindings use a cursor and warm it once. C02 defers encounters "
        "until both grouped peers are ready and injects its existing validated reader. "
        "No companion, immediate fallback, supply ageing or live setup branch is selected.",
    ),
    "game/veloren/native_bindings.py": (
        "4afac9e88311893308ab002ef57332ca9013766cdb86930c4acf1b3dc39cc296",
        "New combat cursor is not used by C02's injected deferred group reader. "
        "Existing loaded-actor cursor defaults remain unchanged.",
    ),
    "game/veloren/runtime/server_extension.py": (
        "eb8961a8c24af1ece20873c1fd964afb2edf0a3590b7009fdc451526752b9830",
        "New composition branch is unreachable: the exact supported C02 manifest has "
        "no runtime_composition, server_extension or pickup_evidence.",
    ),
    "game/veloren/runtime/worker.py": (
        "9fe13c1dc6d843da37fe9dc9ec4c2fb56b311f330179fd35aa58b2750dc7d8dc",
        "Reviewed optional provenance writes are absent; no claim of prospective loaded "
        "inventories is made for main. Additional swap_weapons is outside C02's ST allowlist. "
        "Group setup, strict opening validation and native action implementation are preserved.",
    ),
    "game/veloren/structured_tools/interface.py": (
        "cb53fabd08b08167aaa30f06f2413ac88e8accfb8b706ab38efd530bb40111fc",
        "Only SwapWeaponsTool registration added outside this exact C02 allowlist. "
        "All declared specs, 112 actual conversions and boundary projections are checked.",
    ),
    "game/veloren/evaluators/active_build.py": (
        "5fdb906d832c5f80ddb5168351e1caa877d692b0ab877d6e9859b95d72b24774",
        "New inactive evaluator; neither C02 team nor participant binding selects it.",
    ),
    "game/veloren/evaluators/encounter_supplies.py": (
        "8a42df9f895a457252cafb614044fcc0dd5bccc98f64e662bdab42ec53080470",
        "New inactive evaluator; C02 has no supplies/pickup fixture or evaluator.",
    ),
    "game/veloren/runtime/composition.py": (
        "229262805b83d287a60b4959e72ecad1e930a70d27b8e51bc82b057a3e0844a8",
        "New inactive runtime selector; supported C02 manifest is not composed.",
    ),
    "game/veloren/patches/0008-native-physics-route-evidence.patch": (
        "6208f2ff059bbde5af61eaf64a1bf50043a5f8305d5cad958ac2fba60a3c07e7",
        "Current stronger route observer recipe is preserved, not rolled back. "
        "Admission uses the exact existing f90ca9 artifact and all1160 compiled-source pins; "
        "neither rebuilding current recipes nor another/default runtime is admitted.",
    ),
}
ABSENT = {
    "game/veloren/prototypes/__init__.py",
    "game/veloren/prototypes/sheltered_caravan.py",
    "game/veloren/runtime/provenance.py",
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), "--no-pager", *args])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_paths(root, commit):
    paths = git(root, "ls-tree", "-r", "--name-only", commit, "--", *SCOPES)
    return {path for path in paths.decode().splitlines() if path.endswith((".py", ".patch"))}


def check_sources(root):
    head = git(root, "rev-parse", "HEAD").decode().strip()
    reviewed, current = source_paths(root, REVIEW), source_paths(root, head)
    records = []
    for path in sorted(reviewed | current):
        old = git(root, "show", f"{REVIEW}:{path}") if path in reviewed else None
        if path not in current:
            assert path in ABSENT and not (root / path).exists(), path
            records.append({
                "path": path, "review_sha256": digest(old), "main_sha256": None,
                "bridge": "Absent C05-only prototype or optional private provenance logger; "
                          "not a C02 gameplay dependency or retrospective loaded-process claim.",
            })
            continue
        committed = git(root, "show", f"{head}:{path}")
        assert committed == (root / path).read_bytes(), f"Dirty execution source: {path}"
        same = old == committed
        if not same:
            assert path in BRIDGED, f"Unreviewed source delta: {path}"
            assert digest(committed) == BRIDGED[path][0], f"Changed bridged source: {path}"
        records.append({
            "path": path, "review_sha256": digest(old) if old is not None else None,
            "main_sha256": digest(committed), "worktree_matches_head": True,
            "matches_review": same,
            "bridge": "Exact bytes" if same else BRIDGED[path][1],
        })
    manifest = "docs/reference_tasks_manifest.json"
    assert (root / manifest).read_bytes() == git(root, "show", f"{head}:{manifest}")
    return head, records, {"path": manifest, "sha256": digest((root / manifest).read_bytes())}


def check(root, evidence_root):
    sys.path.insert(0, str(root))
    head, sources, manifest = check_sources(root)
    task_pins = {}
    for track in ("structured_tools", "visual_motor"):
        path = f"config/veloren/tasks/{track}/{TASK}.yaml"
        actual = (root / path).read_bytes()
        assert actual == git(root, "show", f"{REVIEW}:{path}"), path
        task_pins[track] = {"path": path, "sha256": digest(actual)}

    script = git(root, "show", f"{REVIEW}:checks/cooperation_supported_admission.py")
    helper = ModuleType("reviewed_cooperation_admission")
    helper.__file__ = str(root / "checks/cooperation_supported_admission.py")
    exec(compile(script, f"{REVIEW}:cooperation_supported_admission.py", "exec"), helper.__dict__)
    runtime_path = evidence_root / "veloren-route-v2-contact-fix/candidate-runtime.json"
    runtime = json.loads(runtime_path.read_text())
    assert not any(key in runtime for key in ("runtime_composition", "server_extension", "pickup_evidence"))
    supported_runtime = helper.runtime_lock(runtime_path)
    historical = helper.historical_interface(
        evidence_root / "veloren-interaction/VE-C02-independent-peer-ready-st"
    )
    bindings = helper.current_bindings(evidence_root)

    from benchmark.config import load_task
    from benchmark.factory import make_game
    readiness = {}
    for track in task_pins:
        task = load_task(root / task_pins[track]["path"])
        assert task.evaluator == "team" and task.time_limit_seconds == 2700
        assert task.fixture["peer_group"] is True and task.fixture["route_evidence"] is True
        assert not set(task.fixture) & {"companion", "supplies", "contract", "pickup_evidence"}
        assert not set(task.evaluator_parameters) & {"escort", "cargo", "crossing"}
        assert "SwapWeaponsTool" not in (task.tools or ())
        binding = make_game(
            task, root / "output/not-started-c02-admission" / track,
            headless=True, recording=False, recording_fps=5,
        )
        binding.verify_initial(
            evidence_root / "veloren-interaction/VE-C02-selected-recovery-colors-v2-vm/before"
        )
        readiness[track] = "Current strict initial validators accept unchanged archived route/2 opening; not a new ready session."

    audit_path = evidence_root / "checks/veloren-acceptance-policy-audit-20261029.json"
    audit = json.loads(audit_path.read_text())["dated_addenda"][4]
    assert audit["task_id"] == "VE-C02" and audit["disposition"] == "supported"
    assert REVIEW in audit["exact_scope"]["source_commits"]
    assert audit["exact_scope"]["runtime_sha256"] == supported_runtime["sha256"]
    for track, short in (("structured_tools", "st"), ("visual_motor", "vm")):
        assert task_pins[track]["sha256"] == audit["exact_scope"][f"{short}_task_sha256"]
    return {
        "schema": "livequest-c02-main-source-admission/1",
        "task_id": "VE-C02", "passed": True, "reviewed_source": REVIEW,
        "main_parent": head, "source_checks": sources, "task_pins": task_pins,
        "frozen_manifest_untouched": manifest,
        "supported_runtime": supported_runtime,
        "historical_ST_public_compatibility": historical,
        "current_main_both_track_archived_route2_replay": bindings,
        "current_main_initial_validation_bridge": readiness,
        "reviewed_checker_sha256": digest(script),
        "review": {
            "path": str(audit_path), "selector": "dated_addenda[4]",
            "file_sha256_at_check": digest(audit_path.read_bytes()),
            "addendum_sha256": digest(json.dumps(audit, sort_keys=True).encode()),
            "addendum": audit,
        },
        "preserved_limits": {
            "historical_actual_loaded_adapter": "Missing; not retroactively reconstructed.",
            "historical_ST": "Existing route/1 success retained on its own historical version; "
                             "current route/2 metrics explicitly reject route/1.",
            "historical_VM": "Existing route/2 valid failure retained; no whole-VM victory claim.",
            "current_execution": "Offline source/API/fixture/evaluator/native-artifact bridge only. "
                                 "No fresh current-runtime episode or blanket runtime admission.",
            "stronger_semantics": "Current alive/downed, source identity, 30s causal heal window, "
                                  "route identity and schema checks are retained unchanged.",
            "C05": "Excluded, including isolated d1448a7 startup optimization and escort support.",
        },
        "new_native_or_model_executions": 0,
        "ledger_mutation_by_checker": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.root.resolve(), args.development_root.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "source_files": len(result["source_checks"]),
                      "main_parent": result["main_parent"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
