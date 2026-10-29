"""Read-only exact L04 source/runtime bridge; optional publication, never a game run."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[1]
REVIEW = "132f98f9346426665bd3441925b8b91c20fed2d8"
BASE = "76720c8918208a7907a0827577f39efc84507f3d"
TASK = "three_choice_ballistic_path_reuse_v7_alive2"
EVIDENCE = ROOT / "output/temp/task_development"
COMPOSITION = "checks/VE-L04-reviewed-source-composition-20261029.json"
NUMERIC = "checks/VE-L04-finite-clearance-v7.json"
QUALITY = "docs/evidence/three-choice-ballistic-path-reuse-v7-alive2.json"
SCOPES = ("benchmark", "game/veloren", "game/backends/x11",
          "game/team.py", "game/base_game.py", "game/bindings.py")
PROTOTYPES = {
    f"game/veloren/prototypes/{name}.py"
    for name in ("__init__", "ballistic_aperture", "aperture_geometry_audit",
                 "aperture_counterpolicy", "aperture_probe")
}
BRIDGES = {
    "game/backends/x11/display.py": "Xvfb -noreset preserves the same1024x768 display across client reconnects; no public action/schema change.",
    "game/team.py": "Not selected by this single-player task.",
    "game/veloren/binding.py": "Additional evaluator registrations are inactive; L04 still selects encounter with the same roles/no_death/min_health.",
    "game/veloren/evaluators/encounter.py": "Optional required-attack/companion/team branches are inactive. New queued-attack events are accepted but not scored as damage. Historical core check parity is replayed.",
    "game/veloren/evaluators/endpoints.py": "Preserve current positive-health/not-downed guard. Publication explicitly versions this as alive/2; historical v5/v7 results stay unchanged.",
    "game/veloren/fixture.py": "Optional supplies, harvest, injured-enemy, companion and deferred-team setup are absent. Ordinary full-health GreenLegoom initialization uses the same identity checks with an incremental native binding reader.",
    "game/veloren/game.py": "Peer/energy/terrain additions are inactive. Default public projection and declared combat actions are checked against the reviewed module.",
    "game/veloren/native_bindings.py": "Incremental combat reader preserves latest validated native UID/entity binding semantics; no public channel added.",
    "game/veloren/runtime/journal.py": "Stronger prefix/journal guards and optional pickups retained. Single-player L04 has no prefix/pickups; queued attack records are not a new score obligation.",
    "game/veloren/runtime/records.py": "Defers large private authoring receipts until cleanup, not authoring or gameplay state.",
    "game/veloren/runtime/startup.py": "Bounded setup-only administrator reconnect, not a gameplay reset.",
    "game/veloren/runtime/worker.py": "Preserve current setup/journal/retirement guards. No peer, supplies, companion, route, terrain-query or RPG branch is selected; original public combat dispatch remains.",
    "game/veloren/runtime/server_extension.py": "Exact pinned runtime has no extension/composition/pickup capability; selector must return its original upstream server.",
    "game/veloren/runtime/install.py": "Not executed: no rebuild or default/current recipe admission. Only the exact existing renderer/server/helper are supported.",
    "game/veloren/structured_tools/interface.py": "New optional tools/peer/energy fields are outside L04's unchanged COMBAT_TOOLS/default projection; exact specs/conversions are checked.",
    "game/veloren/settlement.py": "Not selected: no merchant, contract or native_site fixture.",
}
INACTIVE = {
    "game/veloren/evaluators/active_build.py", "game/veloren/evaluators/attack.py",
    "game/veloren/evaluators/encounter_supplies.py", "game/veloren/evaluators/harvest.py",
    "game/veloren/evaluators/itinerary.py", "game/veloren/evaluators/peer_support.py",
    "game/veloren/evaluators/pickups.py", "game/veloren/evaluators/route_transfer.py",
    "game/veloren/evaluators/team_efficiency.py", "game/veloren/harvest.py",
    "game/veloren/runtime/composition.py", "game/veloren/patches/0007-native-pickups.patch",
    "game/veloren/patches/0008-native-physics-route-evidence.patch",
}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), "--no-pager", *args])


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_paths(commit):
    return {p for p in git("ls-tree", "-r", "--name-only", commit, "--", *SCOPES)
            .decode().splitlines() if p.endswith((".py", ".patch"))}


def publish():
    guard = json.loads((EVIDENCE / "checks/L04-integration-guard-20261029.json").read_text())
    assert guard["state"] == "held" and Path(f"/proc/{guard['pid']}").exists()
    assert git("rev-parse", "HEAD").decode().strip() == BASE
    assert not git("diff", "--cached", "--name-only")
    from game.veloren.prototypes.ballistic_aperture import build_instance

    for directory, track in (("structured_tools", "structured_tool"), ("visual_motor", "visual_motor")):
        task, private = build_instance(ROOT / "config/veloren/fixtures/veloren_0_18_0_0.bin", 0, track)
        task["id"] = TASK
        task["fixture"]["world_path"] = "../../fixtures/veloren_0_18_0_0.bin"
        path = ROOT / f"config/veloren/tasks/{directory}/{TASK}.yaml"
        with path.open("x") as stream:
            yaml.safe_dump(task, stream, sort_keys=False, default_flow_style=None)
        assert private["open_slot"] == 1
    for source, target in (
        (EVIDENCE / "checks/parallel-ve-learning-L04-source-composition-20261029.reviewed.json", COMPOSITION),
        (EVIDENCE / "parallel-ve-learning-20261029/l04-finite-clearance.json", NUMERIC),
    ):
        with (ROOT / target).open("xb") as stream:
            stream.write(source.read_bytes())
    audit = json.loads((EVIDENCE / "checks/veloren-acceptance-policy-audit-20261029.json").read_text())
    quality = {
        "task": TASK, "stable_id": "VE-L04", "name": "Three-choice ballistic-path discovery and reuse",
        "physical_definition": "Exact reviewed v7; no geometry, resources, timing, goals or public instruction change.",
        "publication_version": "v7-alive2",
        "scoring_revision": "veloren-original-reference-alive/2",
        "version_delta": "New narrow publication ID and relative world-path serialization only. Retain current-main not-downed guard explicitly as alive/2; do not silently relabel historical scorer versions.",
        "example_instance": "Seed0/choice1 published on both tracks; reviewed generator retains all3 choices. This author metadata is never policy input.",
        "reviewed_source": REVIEW, "main_bridge_base": BASE,
        "independent_review": audit["dated_addenda"][13],
        "runtime_scope": "Explicit387e3485 native runtime only, not a rebuilt/default runtime or historical loaded-Python attestation.",
        "historical_results": "v5 native valid partial failure; v6 navigation fall; v7 navigation-only encounterfalse. No whole native or VM victory.",
    }
    with (ROOT / QUALITY).open("x") as stream:
        json.dump(quality, stream, indent=2)
        stream.write("\n")


def check_sources():
    reviewed, baseline = source_paths(REVIEW), source_paths(BASE)
    expected = baseline | PROTOTYPES
    assert source_paths("HEAD") | PROTOTYPES == expected, "New execution sources need a fresh bridge"
    rows = []
    for path in sorted(expected):
        source = REVIEW if path in PROTOTYPES else BASE
        actual = (ROOT / path).read_bytes()
        assert actual == git("show", f"{source}:{path}"), f"Unreviewed source change: {path}"
        old = git("show", f"{REVIEW}:{path}") if path in reviewed else None
        same = old == actual
        assert same or path in BRIDGES or path in INACTIVE, path
        rows.append({
            "path": path, "main_sha256": digest(ROOT / path), "matches_review": same,
            "bridge": "Exact reviewed bytes" if same else BRIDGES.get(
                path, "Inactive evaluator/runtime recipe; no selected fixture/evaluator/capability reaches it."),
        })
    return rows


def check_runtime(composition, task):
    path = ROOT / "output/temp/veloren-native-route-20261027/runtime.json"
    assert digest(path) == composition["native_provenance"]["runtime_sha256"]
    config = json.loads(path.read_text())
    assert not set(config) & {"runtime_composition", "server_extension", "pickup_evidence"}
    pins = []
    for name, expected in config["sha256"].items():
        assert digest(name) == expected, name
        pins.append({"path": name, "sha256": expected})
    upstream = Path(config["upstream_runtime"])
    assert digest(upstream) == config["upstream_sha256"]
    code = (
        "import json,sys;from pathlib import Path;"
        "from scripts.rpg_benchmark import runtime;"
        "print(json.dumps(runtime.load_runtime(Path(sys.argv[1]),sys.argv[2],backend='renderer')))"
    )
    loaded = json.loads(subprocess.check_output(
        [config["python"], "-c", code, str(upstream), config["upstream_sha256"]], text=True,
    ))
    from game.veloren.runtime.server_extension import select_server
    server = Path(loaded["renderer"]["paths"]["server"])
    assert select_server(config, server) == server
    for name in ("server",):
        p = Path(loaded["renderer"]["paths"][name])
        pins.append({"path": str(p), "sha256": digest(p)})
    helper = Path(loaded["renderer_fixture_helper"]["executable"])
    pins.append({"path": str(helper), "sha256": digest(helper)})
    source = ROOT / composition["native_provenance"]["source_root"]
    for name, expected in composition["native_provenance"]["manifest_matching_files_sha256"].items():
        assert digest(source / name) == expected, name
    raw = json.loads(upstream.read_text())
    original_source = upstream.parent / raw["renderer"]["source_root"]
    blocks = [
        ("Primary", "voxygen/src/session/mod.rs", "GameInput::Primary => {", "GameInput::Secondary => {", False),
        ("ToggleWield", "voxygen/src/session/mod.rs", "GameInput::ToggleWield => {", "GameInput::", False),
        ("default_body", "client/src/agent_protocol/mod.rs", "fn default_body()", "fn ", False),
        ("aim_dir_offset", "voxygen/src/session/mod.rs", "let (is_aiming, aim_dir_offset) = {",
         "self.is_aiming = is_aiming;", True),
        ("camera_to_native_look", "voxygen/src/session/mod.rs", "let dir = if is_aiming",
         "self.inputs.look_dir = Dir::from_unnormalized(dir).unwrap();", True),
    ]
    for label, name, begin, end, include_end in blocks:
        snippets = []
        for root in (source, original_source):
            text = (root / name).read_text()
            start = text.index(begin)
            stop = text.index(end, start + len(begin)) + (len(end) if include_end else 0)
            snippets.append(text[start:stop])
        assert snippets[0] == snippets[1]
        assert hashlib.sha256(snippets[0].encode()).hexdigest() == (
            composition["native_provenance"]["identical_overlay_blocks_sha256"][label]
        )
    asset_root = Path(raw["renderer"]["assets"])
    manifest_path = upstream.parent / raw["renderer"]["assets_manifest"]
    manifest = json.loads(manifest_path.read_text())["files_sha256"]
    selected = {
        "common/abilities/ability_set_manifest.ron",
        "common/abilities/bow/arrow_shot.ron",
        "common/abilities/custom/green_legoom/doublestrike.ron",
    }
    queue = [
        *task["fixture"]["player_state"]["equipment"].values(),
        *task["fixture"]["player_state"]["inventory"],
        *(e["asset"] for e in task["fixture"]["encounters"]),
    ]
    while queue:
        name = queue.pop().replace(".", "/") + ".ron"
        if name in selected or not (asset_root / name).is_file():
            continue
        selected.add(name)
        queue.extend(re.findall(r'"(common\.[A-Za-z0-9_.-]+)"', (asset_root / name).read_text()))
    asset_pins = []
    for name in sorted(selected):
        actual = digest(asset_root / name)
        assert actual == manifest[name], f"Changed selected stock asset: {name}"
        if name in composition["native_provenance"]["stock_assets_sha256"]:
            assert actual == composition["native_provenance"]["stock_assets_sha256"][name]
        asset_pins.append({"path": str(asset_root / name), "sha256": actual})
    return {
        "path": str(path.relative_to(ROOT)), "sha256": digest(path),
        "constituents": pins, "upstream_sha256": digest(upstream),
        "asset_manifest_sha256": digest(manifest_path), "selected_assets": asset_pins,
        "reviewed_overlay_blocks_verified": [row[0] for row in blocks],
        "current_main_server_selector": "Original pinned server, no extension or composed runtime.",
        "explicit_environment": f"LIVEQUEST_VELOREN_RUNTIME={path}",
        "no_default_or_rebuilt_runtime_admission": True,
    }


def check():
    from benchmark.config import load_task
    from benchmark.factory import make_game
    from game.veloren.fixture import verify_player
    from game.veloren.prototypes.ballistic_aperture import build_instance
    from game.veloren.prototypes.aperture_geometry_audit import audit
    from game.veloren.structured_tools import interface as current
    from game.veloren.evaluators.encounter import evaluate_encounter
    from game.veloren.evaluators.endpoints import state_checks

    sources = check_sources()
    quality = json.loads((ROOT / QUALITY).read_text())
    review = quality["independent_review"]
    assert review["disposition"] == "supported" and review["source_commit"] == REVIEW
    refs = []
    for ref in review["evidence_refs"]:
        path = ROOT / (COMPOSITION if ref["path"].endswith("L04-source-composition-20261029.json") else ref["path"])
        assert digest(path) == ref["sha256"], str(path)
        refs.append({"path": str(path.relative_to(ROOT)), "sha256": digest(path)})
    composition = json.loads((ROOT / COMPOSITION).read_text())
    world = ROOT / "config/veloren/fixtures/veloren_0_18_0_0.bin"
    numeric = json.loads((ROOT / NUMERIC).read_text())
    assert audit(world) == numeric
    generated, _ = build_instance(world, 0)
    tasks = {}
    for directory, track in (("structured_tools", "structured_tool"), ("visual_motor", "visual_motor")):
        path = ROOT / f"config/veloren/tasks/{directory}/{TASK}.yaml"
        parsed = yaml.safe_load(path.read_text())
        expected, _ = build_instance(world, 0, track)
        parsed["id"] = expected["id"]
        parsed["fixture"]["world_path"] = str((path.parent / parsed["fixture"]["world_path"]).resolve())
        assert parsed == expected
        binding = make_game(load_task(path), ROOT / "output/not-started-l04-admission" / directory,
                            headless=True, recording=False, recording_fps=5)
        # Inspect schemas only; the live lifecycle readiness gate stays untouched.
        binding.game.get_agent_interface = lambda game=binding.game: game._interface
        _, tools = binding.controls()
        assert {t.name for t in tools} == (set(current.COMBAT_TOOLS) if track == "structured_tool" else {"action"})
        tasks[directory] = {"path": str(path.relative_to(ROOT)), "sha256": digest(path),
                            "tools": [t.name for t in tools], "native_started": False,
                            "control_binding_scope": "Offline schema access, not initialized native play."}
    old = ModuleType("reviewed_l04_interface")
    sys.modules[old.__name__] = old
    exec(compile(git("show", f"{REVIEW}:game/veloren/structured_tools/interface.py"),
                 "reviewed_l04_interface", "exec"), old.__dict__)
    assert old.COMBAT_TOOLS == current.COMBAT_TOOLS and old.FIELDS == current.FIELDS
    for name in old.COMBAT_TOOLS:
        assert old.SPECS[name] == current.SPECS[name], name
    cases = [
        ("MoveTool", {"direction": direction, "duration_ticks": ticks})
        for direction in ("forward", "backward", "left", "right") for ticks in (1, 2, 6, 60, 120)
    ] + [
        ("LookTool", {"x": 18712.5, "y": 10806, "z": 501}),
        ("TurnTool", {"degrees": -90}), ("StopTool", {}), ("WieldTool", {"wield": True}),
        ("AttackTool", {"channel": "primary", "duration_ticks": 60}),
    ]
    for name, args in cases:
        assert old.validate_tool(name, deepcopy(args)) == current.validate_tool(name, deepcopy(args))
    replays = []
    for directory in (
        "learning-L04-v5/native-st-1",
        "parallel-ve-learning-20261029/native-navigation-1",
    ):
        base = EVIDENCE / directory
        result = json.loads((base / "result.json").read_text())
        for stage in ("before", "after"):
            observation = json.loads((base / stage / "observation.json").read_text())
            assert old.project(observation) == current.project(observation)
            if stage == "before":
                verify_player(generated["fixture"], observation)
        replay = evaluate_encounter(base / "before", base / "after", **generated["evaluator"]["parameters"])
        previous = result["evaluation"]
        assert replay["success"] is previous["success"] is False
        assert replay["checks"] == previous["checks"]
        replays.append({"path": str(base.relative_to(ROOT)), "result_sha256": digest(base / "result.json"),
                        "success": False, "core_checks_equal": True,
                        "scope": "Historical scorer compatibility only; not a new or stitched v7 experiment."})
    downed = deepcopy(observation)
    downed["survival"]["health"]["downed"] = True
    assert not state_checks(observation, downed)["success"]
    runtime = check_runtime(composition, generated)
    test_log = EVIDENCE / "parallel-ve-learning-20261029/main-admission-tests.log"
    test_text = test_log.read_text()
    assert re.search(r"\b30 passed\b", test_text), "Missing focused main integration test receipt"
    return {
        "schema": "livequest-l04-exact-main-admission/1", "task_id": "VE-L04", "passed": True,
        "published_task_id": TASK, "reviewed_source": REVIEW, "main_parent": BASE,
        "checked_head": git("rev-parse", "HEAD").decode().strip(),
        "source_checks": sources, "task_pins": tasks,
        "publication_version": quality["publication_version"],
        "world_sha256": digest(world), "supported_runtime": runtime,
        "independent_review": review, "verified_review_refs": refs,
        "all_three_layouts_recomputed": True, "historical_scorer_replays": replays,
        "public_control_conversion_checks": len(cases),
        "public_projection_bridge": "Exact default projection on four archived native boundaries.",
        "opening_bridge": "Current verify_player accepts both archived openings; no new native readiness claimed.",
        "stronger_current_guards": "Current alive/2 not-downed rejection retained and checked; no old guard rolled back.",
        "VM_composition": composition["vm_argument"],
        "quality_document": {"path": QUALITY, "sha256": digest(ROOT / QUALITY)},
        "checker_sha256": digest(__file__),
        "light_tests": {
            "passed": 30, "log": str(test_log.relative_to(ROOT)), "sha256": digest(test_log),
            "scope": "21 aperture tests,8 current native-binding cursor tests,1 retained alive-guard test.",
        },
        "preserved_limits": quality["historical_results"],
        "new_native_or_model_executions": 0, "L02_admission": False,
    }


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.publish:
        publish()
    report = check()
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
