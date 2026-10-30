from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest
import yaml

from benchmark.config import load_task
from benchmark.factory import make_game
from game.veloren.fixture import validate_fixture
from game.veloren.prototypes.combat_response_assets import ABILITY_PATH, render_response
from game.veloren.prototypes.combat_response_runtime import SCHEMA, tree_digest
from game.veloren.prototypes.combat_response_transfer import build_instance
from game.veloren.runtime import combat_response as response
from game.veloren.runtime.session import runtime_configuration


@pytest.mark.parametrize("track,folder", [("structured_tool", "structured_tools"), ("visual_motor", "visual_motor")])
def test_registered_c1_preserves_original_fixture_score_and_public_choice(tmp_path, track, folder):
    path = Path("config/veloren/tasks") / folder / "native_combat_response_transfer_c1.yaml"
    registered = yaml.safe_load(path.read_text())
    original, _ = build_instance(path.parent / registered["fixture"]["world_path"], 1, track)
    expected = deepcopy(original)
    expected["fixture"]["world_path"] = registered["fixture"]["world_path"]
    expected["task"] = registered["task"]
    assert registered == expected
    binding = make_game(load_task(path), tmp_path / "game", headless=True, recording=False, recording_fps=5)
    assert binding.game.track == track
    changed = deepcopy(registered["fixture"])
    changed["encounters"][0]["asset"] = "common.entity.benchmark.male_wolf"
    with pytest.raises(ValueError, match="Green Legoom"):
        validate_fixture({**changed, "world_path": str((path.parent / changed["world_path"]).resolve())})


def fake_runtime_pair(tmp_path, monkeypatch, track):
    entries = []
    for selection in range(2):
        directory = tmp_path / str(selection)
        directory.mkdir()
        encoded = json.dumps({"experimental_combat_response_assets": {"selection": selection}}).encode()
        (directory / "runtime.json").write_bytes(encoded)
        entries.append((str(selection), sha256(encoded).hexdigest()))
    monkeypatch.setattr(response, "RUNTIMES", {track: tuple(entries)})
    monkeypatch.setenv(response.ENVIRONMENT, str(tmp_path))


@pytest.mark.parametrize("track", ["structured_tool", "visual_motor"])
def test_private_selection_draws_once_without_default_override_or_public_mutation(tmp_path, monkeypatch, track):
    fake_runtime_pair(tmp_path, monkeypatch, track)
    fixture = {"experimental_combat_response": response.PROFILE}
    original = deepcopy(fixture)
    draws = iter([1, 0])
    monkeypatch.setattr(response.secrets, "randbelow", lambda n: next(draws))
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(tmp_path / "must-not-use.json"))
    assert runtime_configuration(fixture, track=track)[1]["experimental_combat_response_assets"]["selection"] == 1
    assert runtime_configuration(fixture, track=track)[1]["experimental_combat_response_assets"]["selection"] == 0
    assert fixture == original
    # Even a draw that would choose B must reject a missing or altered A.
    (tmp_path / "0/runtime.json").write_text("{}")
    with pytest.raises(ValueError, match="exact audit93"):
        runtime_configuration(fixture, track=track)
    with pytest.raises(ValueError, match="explicit supported track"):
        runtime_configuration(fixture)


@pytest.mark.parametrize("other", ["runtime_profile", "scene_observation", "message_contract", "route_evidence", "peer_group"])
def test_conflicting_profiles_fail_before_any_runtime_read(other):
    with pytest.raises(ValueError, match="cannot share"):
        runtime_configuration({"experimental_combat_response": response.PROFILE, other: {}}, track="visual_motor")
    with pytest.raises(ValueError, match="Unsupported C1"):
        runtime_configuration({"experimental_combat_response": "C2"}, track="visual_motor")


@pytest.mark.parametrize("selection", [0, 1])
def test_worker_binds_one_complete_asset_tree_and_rejects_mixed_inputs(tmp_path, selection):
    stock = Path("tests/fixtures/veloren/green_legoom_doublestrike.ron").read_bytes()
    baseline = tmp_path / "stock/assets"
    (baseline / ABILITY_PATH).parent.mkdir(parents=True)
    (baseline / ABILITY_PATH).write_bytes(stock)
    (baseline / "untouched.ron").write_text("unchanged")
    files = {p.relative_to(baseline).as_posix(): sha256(p.read_bytes()).hexdigest()
             for p in baseline.rglob("*") if p.is_file()}
    baseline_manifest = tmp_path / "stock.json"
    baseline_manifest.write_text(json.dumps({"files_sha256": files, "tree_sha256": tree_digest(files)}))
    assets = tmp_path / "chosen/assets"
    shutil.copytree(baseline, assets)
    (assets / ABILITY_PATH).write_bytes(render_response(stock, selection))
    files[ABILITY_PATH.as_posix()] = sha256((assets / ABILITY_PATH).read_bytes()).hexdigest()
    manifest = tmp_path / "chosen.json"
    manifest.write_text(json.dumps({"files_sha256": files, "tree_sha256": tree_digest(files)}))
    declaration = {"schema": SCHEMA, "assets": str(assets), "manifest": str(manifest),
                   "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(), "selection": selection}
    cfg = {"experimental_combat_response_assets": declaration}
    fixture = {"experimental_combat_response": response.PROFILE}
    paths = {"assets": str(baseline), "assets_manifest": str(baseline_manifest)}
    response.bind_assets(cfg, fixture, paths, tmp_path)
    assert paths["assets"] == str(assets)
    receipt = json.loads((tmp_path / "experimental-assets-admission.json").read_text())
    assert receipt["selection"] == selection
    for runtime, task in ((cfg, {}), ({}, fixture)):
        with pytest.raises(ValueError, match="both explicit"):
            response.bind_assets(runtime, task, {}, tmp_path)
    paths["assets"] = str(baseline)
    wrong = deepcopy(cfg)
    wrong["experimental_combat_response_assets"]["selection"] = 1 - selection
    with pytest.raises(ValueError, match="more than the reviewed"):
        response.bind_assets(wrong, fixture, paths, tmp_path)
    (assets / "untouched.ron").write_text("mutation")
    with pytest.raises(ValueError, match="bytes differ"):
        response.bind_assets(cfg, fixture, paths, tmp_path)
