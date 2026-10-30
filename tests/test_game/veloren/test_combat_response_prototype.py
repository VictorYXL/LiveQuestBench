from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game.veloren.prototypes.combat_response_assets import (
    ABILITY_PATH,
    PUBLIC_PROPOSAL,
    RESPONSE_PARAMETERS,
    STOCK_SHA256,
    build_candidate,
    render_response,
)


STOCK = Path(__file__).parents[2] / "fixtures/veloren/green_legoom_doublestrike.ron"


def test_native_response_edits_preserve_all_other_ability_bytes():
    stock = STOCK.read_bytes()
    outputs = []
    for selection, (buildup, recovery) in enumerate(RESPONSE_PARAMETERS):
        candidate = render_response(stock, selection)
        outputs.append(candidate)
        restored = candidate.decode().replace(
            f"            buildup_duration: {buildup},", "            buildup_duration: 1,", 1
        ).replace(
            f"            recover_duration: {recovery},", "            recover_duration: 1.2,", 1
        ).replace("    auto_progress: true,\n", "", 1)
        assert restored.encode() == stock
    assert outputs[0] != outputs[1]


def test_unreviewed_native_source_is_rejected_before_output_creation(tmp_path):
    assets = tmp_path / "assets"
    source = assets / ABILITY_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes(STOCK.read_bytes().replace(b"damage: 8", b"damage: 9"))
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="Unreviewed native ability"):
        build_candidate(assets, output, 0)
    assert not output.exists()


def test_bundles_share_truthful_public_identity_without_activating_a_task(tmp_path):
    assets = tmp_path / "assets"
    source = assets / ABILITY_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes(STOCK.read_bytes())
    variants = set()
    for seed in range(8):
        output = tmp_path / str(seed)
        receipt = build_candidate(assets, output, seed)
        target = output / receipt["overlay_asset"]
        variants.add(target.read_bytes())
        assert sha256(target.read_bytes()).hexdigest() == receipt["candidate_sha256"]
        assert (output / "public-instructions.txt").read_text() == PUBLIC_PROPOSAL
        assert json.loads((output / "private-candidate.json").read_text()) == receipt
        assert not receipt["canonical"] and not receipt["qualified"] and not receipt["runnable_task"]
        assert receipt["native_validation"] == "not_run"
        assert {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} == {
            "private-candidate.json", "public-instructions.txt", "overlay/" + ABILITY_PATH.as_posix(),
        }
    assert len(variants) == 2
    assert sha256(source.read_bytes()).hexdigest() == STOCK_SHA256


def test_existing_bundle_and_source_tree_are_not_overwritten(tmp_path):
    assets = tmp_path / "assets"
    source = assets / ABILITY_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes(STOCK.read_bytes())
    with pytest.raises(ValueError, match="source asset tree"):
        build_candidate(assets, assets / "candidate", 0)
    output = tmp_path / "candidate"
    receipt = build_candidate(assets, output, 0)
    with pytest.raises(FileExistsError):
        build_candidate(assets, output, 1)
    assert json.loads((output / "private-candidate.json").read_text()) == receipt


@pytest.mark.parametrize("seed", [True, -1, 2**64, 0.5])
def test_invalid_seed_does_not_read_or_write_any_asset(tmp_path, seed):
    with pytest.raises(ValueError, match="u64"):
        build_candidate(tmp_path / "missing", tmp_path / "output", seed)
    assert not (tmp_path / "output").exists()


def test_actual_st_projection_preserves_identity_but_does_not_export_raw_timing_or_score():
    from game.veloren.structured_tools.interface import FIELDS, project

    raw = {name: None for name in FIELDS}
    raw["nearby_entities"] = [{
        "uid": 12, "body_identity": {"BipedSmall": {"species": "GreenLegoom", "body_type": "Male"}},
        "position": [1, 2, 3], "health": {"current": 25, "maximum": 25, "dead": False},
    }]
    projections = []
    for duration in (0.4, 1.2):
        observation = deepcopy(raw)
        observation["combat_perception"] = {
            "nearby_combat": [{"active_melee_strike": {"buildup_s": duration, "recover_s": duration}}],
        }
        observation["private_encounter_evidence"] = {"author_only": True}
        projected = project(observation)
        assert projected["nearby_entities"] == raw["nearby_entities"]
        assert "combat_perception" not in projected
        assert "private_encounter_evidence" not in projected
        projections.append(projected)
    assert projections[0] == projections[1]


def test_st_attack_result_does_not_bypass_the_observation_projection():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from game.veloren.game import VelorenGame

    async def check():
        game = object.__new__(VelorenGame)
        game._io = asyncio.Lock()
        public = {"action_type": "attack_primary", "status": "completed",
                  "started_tick": 10, "finished_tick": 15, "detail": {"input": "Primary"}}
        session = SimpleNamespace(request=AsyncMock(return_value={
            **public,
            "observation": {"combat_perception": {"nearby_combat": [{"second_buildup": 0.4}]}},
            "private_encounter_evidence": {"author_only": True},
        }))
        game._check_running = lambda: session
        assert await game._call_tool("AttackTool", {"channel": "primary", "duration_ticks": 5}) == public
        assert game._active_tool is None

    asyncio.run(check())
