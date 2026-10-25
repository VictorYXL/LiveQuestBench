"""Delayed client synchronization must not admit a wrong native fixture."""

import asyncio
from copy import deepcopy
import importlib.util
from types import ModuleType, SimpleNamespace
import sys
import os
from pathlib import Path
from uuid import uuid4

import pytest

from game.veloren import fixture as fixtures


def load_worker(monkeypatch, setup=None):
    upstream(monkeypatch, setup if setup is not None else SimpleNamespace())
    package = sys.modules["scripts.rpg_benchmark"]
    package.runtime = SimpleNamespace()

    class Renderer:
        async def envelope(self, request, *, origin, timeout):
            return {"timeout": timeout}

    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.native", SimpleNamespace(
        Journal=object, NativeBridge=object, NativeConfig=object, NativeRefusal=RuntimeError,
    ))
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.renderer", SimpleNamespace(RendererBridge=Renderer))
    monkeypatch.setitem(sys.modules, "game.veloren.runtime.server", SimpleNamespace(fixture_server=object))
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location(
        "test_veloren_worker", Path(fixtures.__file__).parent / "runtime/worker.py",
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


def test_only_public_native_steps_drop_transport_deadline(monkeypatch):
    worker = load_worker(monkeypatch)
    actor = worker.LocalRenderer()
    for origin, command, expected in (
        ("agent", "step", None), ("agent", "observe", 60),
        ("setup", "step", 60), ("cleanup", "cancel", 60),
    ):
        assert asyncio.run(actor.envelope({"cmd": command}, origin=origin)) == {"timeout": expected}
    assert asyncio.run(actor.envelope({"cmd": "observe"}, origin="setup", timeout=5)) == {"timeout": 5}


def test_setup_protects_only_administrator_and_requires_native_readback(monkeypatch):
    admin = object()
    calls = []
    protected = {"self_identity": {"uid": 17}, "survival": {"buffs": [{"kind": "Invulnerability"}]}}

    async def command(target, *args):
        assert target is admin
        calls.append(args)

    async def wait_observation(target, predicate, reason):
        assert target is admin
        assert calls == [("buff", "invulnerability", 1, 3600)]
        assert not predicate({"survival": {"buffs": []}})
        assert not predicate({"survival": {"buffs": [{"kind": "Regeneration"}]}})
        assert predicate(protected)
        return protected

    worker = load_worker(monkeypatch, SimpleNamespace(command=command, wait_observation=wait_observation))
    assert asyncio.run(worker.protect_administrator(admin)) == protected

    async def failed_readback(*args):
        raise RuntimeError("Administrator protection not observed")

    worker.setup.wait_observation = failed_readback
    with pytest.raises(RuntimeError, match="Administrator protection not observed"):
        asyncio.run(worker.protect_administrator(admin))


def player_scene(health=35):
    fixture = {"native_site": "Test", "player_state": {
        "position": [0, 0, 1], "look": [0, 1, 0], "health": health,
        "inventory": {}, "equipment": {},
    }}
    observation = {
        "current_site": {"location_name": "Test", "loaded_chunk": True},
        "position": [0, 0, 1], "look": [0, 1, 0], "velocity": [0, 0, 0],
        "on_ground": True, "survival": {"health": {"current": health}, "buffs": []},
        "inventory": {"items": [], "equipment": {}},
        "known_recipes": {"items": [], "omitted": 0},
    }
    return fixture, observation


def upstream(monkeypatch, setup, combat=None):
    scripts = ModuleType("scripts")
    package = ModuleType("scripts.rpg_benchmark")
    package.setup = setup
    scripts.rpg_benchmark = package
    monkeypatch.setitem(sys.modules, "scripts", scripts)
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", package)
    if combat is not None:
        monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.combat_support", combat)


@pytest.mark.parametrize(("health", "stale_health"), [(35, 100), (100, 99.98828125)])
def test_initialize_waits_for_actual_health(monkeypatch, health, stale_health):
    fixture, expected = player_scene(health)
    fixture.update(time_of_day="12:00")
    stale = deepcopy(expected)
    stale["survival"]["health"]["current"] = stale_health
    calls = []

    class Actor:
        name = "Player"

        async def request(self, command, **kwargs):
            calls.append(command)
            return deepcopy(expected if "health" in calls else stale)

    async def ready(actor):
        return deepcopy(stale)

    async def command(admin, name, *args):
        if "health" in args:
            calls.append("health")

    async def goto(*args, **kwargs):
        pass

    monkeypatch.setattr(fixtures, "validate_fixture", lambda value: value)
    upstream(monkeypatch, SimpleNamespace(ready_observation=ready, command=command, goto=goto))
    result = asyncio.run(fixtures.initialize_fixture(object(), Actor(), fixture))
    fixtures.verify_player(fixture, result["opening"])
    assert result["opening"]["survival"]["health"]["current"] == health


def test_player_wait_times_out_with_mismatch_and_does_not_repair_state():
    fixture, observed = player_scene()
    observed["survival"]["health"]["current"] = 100

    class Actor:
        async def request(self, command, **kwargs):
            assert command == "observe"
            return observed

    with pytest.raises(RuntimeError, match="health.*100.*35"):
        asyncio.run(fixtures.wait_player(Actor(), fixture, observed, timeout=.01))
    assert observed["survival"]["health"]["current"] == 100


def test_player_wait_does_not_swallow_transport_failure():
    fixture, observed = player_scene()
    observed["on_ground"] = False

    class Actor:
        async def request(self, command, **kwargs):
            raise RuntimeError("bridge disconnected")

    with pytest.raises(RuntimeError, match="bridge disconnected"):
        asyncio.run(fixtures.wait_player(Actor(), fixture, observed))


def test_player_wait_keeps_inventory_and_position_strict():
    fixture, observed = player_scene()
    observed["position"] = [1, 0, 1]
    with pytest.raises(RuntimeError, match="position"):
        fixtures.verify_player(fixture, observed)
    observed["position"] = fixture["player_state"]["position"]
    fixture["player_state"]["inventory"] = {"common.items.food.cheese": 1}
    with pytest.raises(RuntimeError, match="inventory"):
        fixtures.verify_player(fixture, observed)


@pytest.mark.parametrize("alignment", ["Enemy", "Npc"])
def test_encounter_does_not_bind_late_arriving_admin(monkeypatch, alignment):
    body = {"BipedSmall": {"species": "GreenLegoom", "body_type": "Male"}}
    admin_entity = {"uid": 1, "body_identity": {"Humanoid": {}},
                    "health": {"current": 100, "dead": False}}
    enemy = {"uid": 126, "body_identity": body, "health": {"current": 25, "dead": False}}
    observed = iter([{"nearby_entities": [admin_entity]}, {"nearby_entities": [admin_entity, enemy]}])
    bindings = []

    class Actor:
        async def request(self, command, **kwargs):
            return {"nearby_entities": []}

    async def goto(*args):
        pass

    async def command(*args):
        return {"status": "completed"}

    async def wait(actor, predicate, reason):
        for row in observed:
            if predicate(row):
                return row
        raise AssertionError(reason)

    async def binding(actor, uid):
        bindings.append(uid)
        return {"uid": uid, "body": body, "alignment": alignment, "health": 25, "dead": False}

    upstream(monkeypatch, SimpleNamespace(goto=goto, command=command, wait_observation=wait),
             SimpleNamespace(native_binding=binding))
    spec = {"role": "enemy", "asset": "common.entity.benchmark.male_green_legoom"}
    if alignment != "Enemy":
        with pytest.raises(RuntimeError, match="Enemy alignment"):
            asyncio.run(fixtures.initialize_encounter(object(), Actor(), spec, [0, 0, 1]))
        assert bindings == [126]
        return
    result = asyncio.run(fixtures.initialize_encounter(object(), Actor(), spec, [0, 0, 1]))
    assert bindings == [126]
    assert result["binding"]["uid"] == 126
    assert result["public"]["uid"] == 126


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_VELOREN_TEST") != "1", reason="Opt-in native fixture checks")
@pytest.mark.parametrize("mode", ["structured_tools", "visual_motor"])
@pytest.mark.parametrize("task_id", ["recover_health", "craft_equip", "defeat_legoom"])
def test_native_regression_fixture(mode, task_id):
    from benchmark.config import load_task
    from game.veloren.game import VelorenGame
    import json

    root = Path(__file__).resolve().parents[3]
    fixture = load_task(root / f"config/veloren/tasks/{mode}/{task_id}.yaml").fixture
    output = root / "output/test" / f"veloren-initialization-{mode}-{task_id}-{uuid4().hex}"
    print(f"Veloren initialization artifacts: {output}")
    game = VelorenGame(output_dir=output, fixture=fixture,
                       track="structured_tool" if mode == "structured_tools" else mode,
                       headless=True, recording=False)

    async def scenario():
        try:
            await game.start()
            snapshot = await game.save_snapshot(output / "opening-check")
            observed = json.loads((snapshot / "observation.json").read_text())
            fixtures.verify_player(fixture, observed)
            initialized = json.loads((output / "fixture.json").read_text())
            retired_uid = initialized["administrator_retirement"]["uid"]
            assert initialized["administrator_retirement"]["confirmed_absent"]
            for target in initialized["encounters"]:
                assert target["binding"]["alignment"] == "Enemy"
                assert target["binding"]["uid"] != retired_uid
                assert target["public"]["uid"] == target["binding"]["uid"]
            await game.begin()
            await game.end()
        finally:
            await game.close()

    asyncio.run(scenario())
