from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import replica
from game.minecraft.evaluators.replica import validate_replica


def test_original_model_cannot_be_its_own_replica():
    structure = {
        "target": {"structure": [[["stone"]]]},
        "region": {"min": [0, 72, 0], "max": [0, 72, 0]},
    }
    with pytest.raises(ValueError, match="overlap"):
        validate_replica(structure=structure, model_region=structure["region"])
    validate_replica(structure=structure, model_region={"min": [40, 72, 0], "max": [40, 72, 0]})


def test_model_and_replica_dimensions_must_agree():
    structure = {
        "target": {"structure": [[["stone"]]]},
        "region": {"min": [0, 72, 0], "max": [0, 72, 0]},
    }
    with pytest.raises(ValueError, match="dimensions"):
        validate_replica(structure=structure, model_region={"min": [40, 72, 0], "max": [41, 72, 0]})


@pytest.mark.parametrize("model,build,message", [
    ("minecraft:dirt", "minecraft:air", "visible model"),
    ("minecraft:stone", "minecraft:stone", "replica pad"),
])
def test_invalid_opening_is_not_scored_as_agent_success(monkeypatch, model, build, message):
    structure = {
        "target": {"structure": [[["stone"]]]},
        "region": {"min": [40, 72, 0], "max": [40, 72, 0]},
    }

    def blocks(world, low, high, dimension):
        return {low: model if low[0] == 0 else build}

    monkeypatch.setattr(replica, "read_blocks", blocks)
    monkeypatch.setattr(
        replica, "evaluate_state",
        lambda *_a, **_kw: {"success": True, "checks": [{"passed": True}], "semantics": ""},
    )
    with pytest.raises(ValueError, match=message):
        replica.evaluate_replica(
            Path("before"), Path("after"), UUID(int=1), structure=structure,
            model_region={"min": [0, 72, 0], "max": [0, 72, 0]},
        )


def test_entire_visible_model_must_be_declared_in_scorer():
    structure = {
        "target": {"structure": [[["stone"]]]},
        "region": {"min": [40, 72, 0], "max": [41, 72, 0]},
    }
    with pytest.raises(ValueError, match="target dimensions"):
        validate_replica(
            structure=structure, model_region={"min": [0, 72, 0], "max": [1, 72, 0]},
        )
