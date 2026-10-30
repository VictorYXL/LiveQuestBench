"""Delayed client synchronization must not admit a wrong native fixture."""

import asyncio
from copy import deepcopy
import importlib.util
from types import ModuleType, SimpleNamespace
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock
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
        monkeypatch.setattr("game.veloren.native_bindings.combat_binding", combat.native_binding)


@pytest.mark.parametrize(("fraction", "native_health"), [(.4, 16), (.96, 38.3984375)])
def test_injured_companion_waits_for_post_injury_native_binding(monkeypatch, fraction, native_health):
    scene = {"self_identity": {"uid": 1}, "nearby_entities": []}
    pet = {"uid": 2, "position": [3, 0, 1], "control_target": {"uid": 2, "lifecycle": "pet"},
           "companion": {"owned_by_actor": True}, "same_native_group": True,
           "body_identity": {"QuadrupedSmall": {"species": "Sheep"}},
           "health": {"current": 40}}
    reads = []

    class Actor:
        name = "Player"

        async def request(self, *args, **kwargs):
            return deepcopy(scene)

    async def command(admin, *args):
        if args[2] == "spawn":
            scene["nearby_entities"] = [pet]
        elif args[2] == "health":
            assert args[-1] == 40 * fraction
            pet["health"]["current"] = native_health
        return {"status": "completed"}

    async def wait(actor, predicate, reason):
        assert predicate(scene)
        return deepcopy(scene)

    async def native_binding(actor, uid):
        if uid == 1:
            return {"uid": 1}
        assert uid == 2
        reads.append(uid)
        return {"uid": uid, "server_entity": "sheep", "alignment": {"Owned": 1},
                "health": 40 if len(reads) < 3 else native_health, "maximum_health": 40, "dead": False}

    upstream(monkeypatch, SimpleNamespace(command=command, wait_observation=wait),
             SimpleNamespace(native_binding=native_binding))
    result = asyncio.run(fixtures.initialize_companion(
        object(), Actor(), {"companion": {"position": [3, 0, 1], "initial_health_fraction": fraction}},
    ))
    assert result["initial_health"] == result["binding"]["health"] == native_health
    assert result["initial_public"]["health"]["current"] == native_health
    assert len(reads) == 3


def test_multiple_companions_prepare_once_with_native_stay_and_return_owner(monkeypatch):
    calls = []
    scene = {"nearby_entities": []}
    specifications = {
        role: {"species": "sheep", "position": [index * 10, 0, 1], "initial_health_fraction": .6}
        for index, role in enumerate(("practice", "west", "east"))
    }

    async def goto(admin, actor, point):
        calls.append(("goto", point))

    async def initialize(admin, actor, fixture):
        uid = len(scene["nearby_entities"]) + 1
        target = {"uid": uid, "lifecycle": str(uid)}
        scene["nearby_entities"].append({"control_target": target, "companion": {"pet_staying": False}})
        calls.append(("spawn", fixture["companion"]))
        return {"binding": {"uid": uid}, "player_target": target}

    async def action(actor, name, **arguments):
        assert name == "companion_action"
        assert arguments["operation"] == "pet_stay" and arguments["stay"] is True
        scene["nearby_entities"][-1]["companion"]["pet_staying"] = True
        calls.append(("stay", arguments["target"]))

    async def wait(actor, predicate, reason):
        assert predicate(scene)

    upstream(monkeypatch, SimpleNamespace(goto=goto, action=action, wait_observation=wait))
    monkeypatch.setattr(fixtures, "initialize_companion", initialize)
    result = asyncio.run(fixtures.initialize_companions(object(), object(), {
        "companions": specifications, "player_state": {"position": [5, 5, 1]},
    }))
    assert set(result) == set(specifications)
    assert [call[0] for call in calls] == ["goto", "spawn", "stay"] * 3 + ["goto"]
    assert calls[-1] == ("goto", [5, 5, 1])


def test_companion_opening_rejects_stale_generation_group_and_damage():
    prepared = {
        "binding": {"uid": 3, "server_entity": "sheep", "maximum_health": 30},
        "player_target": {"uid": 3, "lifecycle": "sheep-client"}, "initial_health": 28.80078125,
    }
    public = {"uid": 3, "control_target": prepared["player_target"],
              "companion": {"owned_by_actor": True}, "same_native_group": True,
              "health": {"current": 28.80078125, "dead": False}}
    native = {"uid": 3, "server_entity": "sheep", "alignment": {"Owned": 1}, "group": 7,
              "health": 28.80078125, "dead": False}
    scene, source = {"nearby_entities": [public]}, {"uid": 1, "group": 7}
    assert fixtures.bind_companion_opening(prepared, scene, [native], source) == prepared
    for field, value in (("server_entity", "replacement"), ("group", 8), ("health", 28),
                         ("alignment", {"Owned": 99}), ("dead", True)):
        with pytest.raises(RuntimeError, match="before measured play"):
            fixtures.bind_companion_opening(prepared, scene, [{**native, field: value}], source)
    with pytest.raises(RuntimeError, match="before measured play"):
        fixtures.bind_companion_opening(prepared, scene, [native, native], source)


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
    player["survival"]["buff_clock"]["now"] = 6
    fixtures.verify_aged_supplies({"supplies": [supply]}, player)
    supply["private_opening"]["clock"] = 286
    player["survival"]["buff_clock"]["now"] = 282
    with pytest.raises(RuntimeError, match="identity-matched"):
        fixtures.verify_aged_supplies({"supplies": [supply]}, player)
    supply["private_opening"]["clock"] = 10
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


@pytest.mark.parametrize("shared_world", [False, True])
def test_team_initialization_defers_original_supplies_without_duplicate_drop(monkeypatch, shared_world):
    fixture, opening = player_scene()
    fixture.update(time_of_day="12:00", supplies=[{"item": "leather", "amount": 4}])
    actor = SimpleNamespace(name="Alpha", request=AsyncMock(return_value=opening))
    upstream(monkeypatch, SimpleNamespace(
        ready_observation=AsyncMock(return_value=opening),
        command=AsyncMock(), goto=AsyncMock(),
    ))
    monkeypatch.setattr(fixtures, "validate_fixture", lambda value: value)
    drop = AsyncMock()
    monkeypatch.setattr(fixtures, "initialize_supplies", drop)
    result = asyncio.run(fixtures.initialize_fixture(
        object(), actor, fixture, shared_world=shared_world, defer_supplies=True,
    ))
    assert result["supplies"] == []
    assert result.get("supplies_pending", False) is not shared_world
    drop.assert_not_awaited()


def test_deferred_original_supplies_require_ready_peers_and_spawn_once(monkeypatch, tmp_path):
    from game.veloren.runtime import records

    fixture, opening = player_scene()
    opening["nearby_entities"] = []
    fixture["supplies"] = [{"item": "leather", "amount": 4}]
    events = []
    source = {"uid": 7, "item": "leather", "amount": 4}

    async def wait(actor, predicate, reason):
        assert predicate(opening)
        return opening

    async def close():
        events.append("admin_retired")

    async def drop(admin, specifications):
        assert session.team_ready and specifications == fixture["supplies"]
        events.append("original_drop")
        return [source]

    worker = load_worker(monkeypatch, SimpleNamespace(wait_observation=wait))
    session = object.__new__(worker.Session)
    session.running, session.team_role = False, "Alpha"
    session.actor = SimpleNamespace(request=AsyncMock(return_value=opening))
    session.fixture, session.output = fixture, tmp_path
    session.record = {"world_fixture": {}}
    session.initialized = {"supplies": [], "supplies_pending": True}
    administrator = (SimpleNamespace(process=SimpleNamespace(returncode=0), cleanup={}),
                     SimpleNamespace(aclose=close), 99)
    session.setup_administrator = administrator
    monkeypatch.setattr(fixtures, "initialize_supplies", drop)
    monkeypatch.setattr(fixtures, "observe_remote_supplies", AsyncMock())
    verified = []
    monkeypatch.setattr(fixtures, "verify_aged_supplies",
                        lambda initialized, observation: verified.append(list(initialized["supplies"])))
    monkeypatch.setattr(worker, "recipe_observation", AsyncMock(return_value=opening))
    monkeypatch.setattr(records, "write_fixture_record", lambda *args: None)

    async def reconnect():
        events.append("admin_reconnected")
        session.setup_administrator = administrator

    session.reconnect_setup_administrator = reconnect

    async def run():
        with pytest.raises(RuntimeError, match="all peers ready"):
            await session.finish_setup()
        await session.finish_setup(finalize_supplies=False)
        assert events == ["admin_retired"]
        await session.dispatch("setup_team_ready", {})
        assert events == ["admin_retired"]
        await session.finish_setup()
        await session.finish_setup()
        session.running = True
        with pytest.raises(PermissionError, match="before declared peer play"):
            await session.dispatch("setup_team_ready", {})

    asyncio.run(run())
    assert events == ["admin_retired", "admin_reconnected", "original_drop", "admin_retired"]
    assert verified == [[], [source]]
    assert source["player_target"] is None
    assert session.initialized["supplies_pending"] is False
    assert session.setup_administrator is None


@pytest.mark.parametrize("failure_stage", ["drop", "readback", "binding", "cancelled"])
def test_failed_original_supply_creation_cannot_be_retried(monkeypatch, failure_stage):
    worker = load_worker(monkeypatch)
    session = object.__new__(worker.Session)
    session.running, session.team_ready = False, True
    session.fixture = {"supplies": [{"item": "leather", "amount": 4}]}
    session.initialized = {"supplies": [], "supplies_pending": True}
    session.setup_administrator = (object(), object(), 99)
    source = {"uid": 7, "item": "leather", "amount": 4}
    drop = AsyncMock(return_value=[source])
    actor = AsyncMock(return_value={"nearby_entities": []})
    session.actor = SimpleNamespace(request=actor)
    error = asyncio.CancelledError if failure_stage == "cancelled" else RuntimeError
    if failure_stage in ("drop", "cancelled"):
        drop.side_effect = error("injected partial native drop failure")
    elif failure_stage == "readback":
        actor.side_effect = error("injected native readback failure")
    else:
        def fail_binding(*args):
            raise RuntimeError("injected native binding failure")
        monkeypatch.setattr(fixtures, "bind_supplies", fail_binding)
    monkeypatch.setattr(fixtures, "initialize_supplies", drop)

    async def run():
        with pytest.raises(error, match="injected"):
            await session.finish_setup()
        with pytest.raises(RuntimeError, match="already started"):
            await session.finish_setup()

    asyncio.run(run())
    drop.assert_awaited_once()
    assert session.initialized["supplies_pending"] is True
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
    fixture = load_task(root / f"tests/fixtures/legacy/config/veloren/tasks/{mode}/{task_id}.yaml").fixture
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
