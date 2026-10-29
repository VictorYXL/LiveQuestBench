"""Contract identity readback must not weaken the declared opening checks."""

import asyncio
from copy import deepcopy
from types import ModuleType, SimpleNamespace
import sys
from unittest.mock import AsyncMock

import pytest

from game.veloren import contracts, fixture as fixtures, native_bindings


@pytest.mark.parametrize("injured", [False, True])
def test_contract_readback_restores_position_but_not_health(monkeypatch, injured):
    fixture = {
        "native_site": "Test", "time_of_day": "12:00", "contract": {},
        "player_state": {
            "position": [0, 0, 1], "look": [0, 1, 0], "health": 100,
            "inventory": {}, "equipment": {},
        },
    }
    observation = {
        "current_site": {"location_name": "Test", "loaded_chunk": True},
        "position": [0, 0, 1], "look": [0, 1, 0], "velocity": [0, 0, 0],
        "on_ground": True, "survival": {"health": {"current": 100}, "buffs": []},
        "inventory": {"items": [], "equipment": {}},
        "known_recipes": {"items": [], "omitted": 0},
        "self_identity": {"uid": 7},
    }
    events = []
    actor = SimpleNamespace(name="Player")

    async def observe(*args, **kwargs):
        return deepcopy(observation)

    async def goto(admin, target, point, **kwargs):
        if target is actor:
            events.append("position")
            observation["position"] = list(point)

    async def prepare_contract(*args):
        events.append("contract")
        observation["position"][1] -= .5078125
        if injured:
            observation["survival"]["health"]["current"] = 99
        return {"target": {"binding": {"uid": 8}, "public": {"uid": 8}}}

    actor.request = observe
    scripts, package = ModuleType("scripts"), ModuleType("scripts.rpg_benchmark")
    scripts.rpg_benchmark = package
    package.setup = SimpleNamespace(ready_observation=observe, goto=goto, command=AsyncMock())
    monkeypatch.setitem(sys.modules, "scripts", scripts)
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", package)
    binding = AsyncMock(return_value={"health": 100, "dead": False})
    monkeypatch.setattr(native_bindings, "combat_binding", binding)
    monkeypatch.setattr(fixtures, "validate_fixture", lambda value: value)
    monkeypatch.setattr(contracts, "initialize_contract", prepare_contract)

    if injured:
        with pytest.raises(fixtures.FixtureMismatch, match="Initial health"):
            asyncio.run(fixtures.initialize_fixture(object(), actor, fixture))
    else:
        result = asyncio.run(fixtures.initialize_fixture(object(), actor, fixture))
        assert result["opening"]["position"] == fixture["player_state"]["position"]
        assert result["source_binding"]["health"] == 100
    assert events == ["position", "contract", "position"]
