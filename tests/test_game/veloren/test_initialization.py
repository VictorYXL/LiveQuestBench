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
@pytest.mark.parametrize("respawn_at_start", [False, True])
def test_initialize_waits_for_actual_health(monkeypatch, health, stale_health, respawn_at_start):
    fixture, expected = player_scene(health)
    fixture.update(time_of_day="12:00")
    if respawn_at_start:
        fixture["respawn_at_start"] = True
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
        if "set_waypoint" in args:
            assert args == ("Player", "set_waypoint")
            assert "health" in calls
            calls.append("set_waypoint")
            return {"status": "completed", "native_command": "set_waypoint"}

    async def goto(*args, **kwargs):
        pass

    monkeypatch.setattr(fixtures, "validate_fixture", lambda value: value)
    upstream(monkeypatch, SimpleNamespace(ready_observation=ready, command=command, goto=goto))
    result = asyncio.run(fixtures.initialize_fixture(object(), Actor(), fixture))
    fixtures.verify_player(fixture, result["opening"])
    assert result["opening"]["survival"]["health"]["current"] == health
    assert ("set_waypoint" in calls) is respawn_at_start
    assert result["initial_waypoint_receipt"] == (
        {"status": "completed", "native_command": "set_waypoint"} if respawn_at_start else None
    )


@pytest.mark.parametrize("value", [True, 999, 10001, 1000.5])
def test_contract_funding_rejects_invalid_reserves(value):
    from benchmark.config import load_task

    fixture = load_task(Path("config/veloren/tasks/structured_tools/native_contract_settlement.yaml")).fixture
    fixture["contract"]["giver_funding"] = value
    with pytest.raises(ValueError, match="giver_funding"):
        fixtures.validate_fixture(fixture)


def test_optional_native_recovery_fields_preserve_legacy_defaults():
    from benchmark.config import load_task

    fixture = load_task(Path("config/veloren/tasks/structured_tools/native_contract_settlement.yaml")).fixture
    fixture["contract"].pop("giver_funding")
    fixture.pop("respawn_at_start")
    assert "giver_funding" not in fixtures.validate_fixture(fixture)["contract"]
    fixture["contract"]["giver_funding"] = 3000
    fixture["respawn_at_start"] = True
    assert fixtures.validate_fixture(fixture)["contract"]["giver_funding"] == 3000
    fixture["respawn_at_start"] = 1
    with pytest.raises(ValueError, match="respawn_at_start"):
        fixtures.validate_fixture(fixture)


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


def test_declared_initial_armor_is_equipped_before_inventory_cleanup(monkeypatch):
    old, new = "common.items.armor.misc.chest.worker_purple_brown", "common.items.armor.hide.rawhide.chest"
    observed = {"inventory": {"equipment": {"chest": {"id": {"Simple": old}}},
                             "items": []}}
    calls = []

    class Actor:
        async def request(self, command):
            return deepcopy(observed)

    actor = Actor()

    async def gift(admin, target, name, amount):
        assert target is actor and name == new and amount == 1
        calls.append("gift")
        observed["inventory"]["items"] = [{"loadout_idx": 0, "slot_idx": 3,
                                           "item": {"id": {"Simple": new}, "amount": 1}}]
        return deepcopy(observed)

    async def action(target, name, **args):
        assert target is actor and name == "equip"
        assert args == {"equip_slot": "chest", "loadout_idx": 0, "slot_idx": 3}
        calls.append("equip")
        observed["inventory"]["equipment"]["chest"] = {"id": {"Simple": new}}
        observed["inventory"]["items"][0]["item"]["id"]["Simple"] = old

    async def wait(target, predicate, reason):
        assert predicate(observed)
        return deepcopy(observed)

    upstream(monkeypatch, SimpleNamespace(
        gift=gift, action=action, wait_observation=wait,
        slot=lambda row: {key: row[key] for key in ("loadout_idx", "slot_idx")},
    ))
    asyncio.run(fixtures.initialize_equipment(object(), actor, {"chest": new}))
    assert calls == ["gift", "equip"]
    assert fixtures.inventory_counts(observed) == {old: 1}
    asyncio.run(fixtures.initialize_equipment(object(), actor, {"chest": new}))
    assert calls == ["gift", "equip"]


def test_distant_supply_uses_private_readback_without_player_visibility(monkeypatch):
    supply = {
        "uid": 7, "player_target": None, "item": "common.items.food.apple", "amount": 1,
        "expiry_game_time_estimate": 300, "entity": {"position": [50, 0, 1]},
    }
    entity = {"uid": 7, "pickup": {"id": {"Simple": supply["item"]}, "amount": 1}}
    private = {"nearby_entities": [entity], "survival": {"buff_clock": {"now": 10}}}
    player = {"nearby_entities": [], "survival": {"buff_clock": {"now": 11}}}
    original_player = deepcopy(player)

    class Admin:
        async def request(self, command, **kwargs):
            assert command == "observe" and kwargs == {"origin": "private-validation"}
            return deepcopy(private)

    admin = Admin()

    async def goto(controller, target, point):
        assert controller is target is admin
        assert point == [50, 0, 1]

    upstream(monkeypatch, SimpleNamespace(goto=goto))
    with pytest.raises(RuntimeError, match="identity-matched"):
        fixtures.verify_aged_supplies({"supplies": [supply]}, player)
    asyncio.run(fixtures.observe_remote_supplies(admin, [supply]))
    fixtures.verify_aged_supplies({"supplies": [supply]}, player)
    assert player == original_player
    player["survival"]["buff_clock"]["now"] = 286
    with pytest.raises(RuntimeError, match="identity-matched"):
        fixtures.verify_aged_supplies({"supplies": [supply]}, player)
    for entries in ([], [{**entity, "uid": 8}], [{**entity, "pickup": {**entity["pickup"], "amount": 2}}]):
        private["nearby_entities"] = entries
        with pytest.raises(RuntimeError, match="private native readback"):
            asyncio.run(fixtures.observe_remote_supplies(admin, [supply]))


def test_begin_does_not_open_public_gate_before_private_setup_finishes(monkeypatch):
    worker = load_worker(monkeypatch)
    session = object.__new__(worker.Session)
    session.running = False
    session.team_role = None
    session.track = "structured_tool"
    calls = []

    async def finish():
        assert not session.running
        calls.append("private-readback-and-admin-retirement")

    session.finish_setup = finish
    assert asyncio.run(session.dispatch("begin", {})) == {"running": True}
    assert calls == ["private-readback-and-admin-retirement"]

    async def fail():
        raise RuntimeError("Distant supply missing")

    session.running = False
    session.finish_setup = fail
    with pytest.raises(RuntimeError, match="Distant supply missing"):
        asyncio.run(session.dispatch("begin", {}))
    assert session.running is False


@pytest.mark.parametrize("alignment", ["Enemy", "Npc"])
@pytest.mark.parametrize("distance", [0, 80])
def test_encounter_does_not_bind_late_arriving_admin(monkeypatch, alignment, distance):
    body = {"BipedSmall": {"species": "GreenLegoom", "body_type": "Male"}}
    admin_entity = {"uid": 1, "body_identity": {"Humanoid": {}},
                    "health": {"current": 100, "dead": False}}
    enemy = {"uid": 126, "body_identity": body, "health": {"current": 25, "dead": False}}
    observed = iter([{"nearby_entities": [admin_entity]}, {"nearby_entities": [admin_entity, enemy]}])
    bindings = []

    class Actor:
        async def request(self, command, **kwargs):
            return {"position": [0, 0, 1], "nearby_entities": []}

    admin, player = Actor(), Actor()

    async def goto(*args):
        pass

    async def command(*args):
        return {"status": "completed"}

    async def wait(actor, predicate, reason):
        assert actor is (admin if distance > 24 else player)
        for row in observed:
            if predicate(row):
                return row
        raise AssertionError(reason)

    async def binding(actor, uid):
        assert actor is player
        bindings.append(uid)
        return {"uid": uid, "body": body, "alignment": alignment, "health": 25, "dead": False}

    upstream(monkeypatch, SimpleNamespace(goto=goto, command=command, wait_observation=wait),
             SimpleNamespace(native_binding=binding))
    spec = {"role": "enemy", "asset": "common.entity.benchmark.male_green_legoom"}
    if alignment != "Enemy":
        with pytest.raises(RuntimeError, match="Enemy alignment"):
            asyncio.run(fixtures.initialize_encounter(admin, player, spec, [distance, 0, 1]))
        assert bindings == [126]
        return
    result = asyncio.run(fixtures.initialize_encounter(admin, player, spec, [distance, 0, 1]))
    assert bindings == [126]
    assert result["binding"]["uid"] == 126
    assert result["public"] == (None if distance > 24 else enemy)
    assert result["setup_observation"] == enemy
    assert result["setup_observer"] == ("administrator" if distance > 24 else "player")


def test_distant_encounter_opening_requires_current_identity_and_undamaged_native_target():
    expected = {
        "uid": 126, "server_entity": "enemy-generation-1", "body": {"BipedSmall": {}},
        "alignment": "Enemy", "health": 25, "dead": False,
    }
    target = {"binding": expected, "public": None}
    observation = {"nearby_entities": []}
    rows = [{"event": "combat_entity_bindings", "data": {"bindings": [deepcopy(expected)]}}]
    fixtures.verify_encounter_opening([target], observation, rows)
    assert observation == {"nearby_entities": []}
    for change in (
        {"uid": 127}, {"server_entity": "replacement"}, {"body": {"Humanoid": {}}},
        {"alignment": "Npc"}, {"health": 24}, {"health": 0}, {"dead": True},
    ):
        latest = deepcopy(rows[0])
        latest["data"]["bindings"][0].update(change)
        with pytest.raises(RuntimeError, match="Designated target unavailable"):
            fixtures.verify_encounter_opening([target], observation, [*rows, latest])
    for bindings in ([], [deepcopy(expected), deepcopy(expected)]):
        with pytest.raises(RuntimeError, match="Designated target unavailable"):
            fixtures.verify_encounter_opening(
                [target], observation, [*rows, {"event": "combat_entity_bindings", "data": {"bindings": bindings}}],
            )
    with pytest.raises(RuntimeError, match="lack native opening bindings"):
        fixtures.verify_encounter_opening([target], observation, [])
    target["public"] = {"uid": 126}
    with pytest.raises(RuntimeError, match="Nearby designated target unavailable"):
        fixtures.verify_encounter_opening([target], observation, rows)
    observation["nearby_entities"] = [{"uid": 126, "health": {"current": 25, "dead": False}}]
    fixtures.verify_encounter_opening([target], observation, rows)


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_VELOREN_TEST") != "1", reason="Opt-in native fixture checks")
@pytest.mark.parametrize("mode", ["structured_tools", "visual_motor"])
@pytest.mark.parametrize("task_id", ["recover_health", "craft_equip", "defeat_legoom"])
def test_native_regression_fixture(mode, task_id):
    from benchmark.config import load_task
    from game.veloren.game import VelorenGame
    import json

    root = Path(__file__).resolve().parents[3]
    fixture = load_task(root / f"output/back/legacy-config-20261026/config/veloren/tasks/{mode}/{task_id}.yaml").fixture
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
