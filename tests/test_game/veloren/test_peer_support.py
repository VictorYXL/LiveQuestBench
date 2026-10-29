"""Safe opening healing and late healing cannot substitute for encounter support."""

from copy import deepcopy
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from game.team import create_team_binding
from game.veloren.evaluators.peer_support import support_checks
from tests.test_game.veloren.test_encounter import evidence
from tests.test_game.veloren.test_initialization import load_worker, player_scene


@pytest.mark.parametrize("encounters_pending", [False, True])
def test_group_setup_does_not_spawn_encounter_before_both_peers_are_ready(monkeypatch, encounters_pending):
    observed = {"self_identity": {"uid": 1},
                "nearby_entities": [{"uid": 2, "same_native_group": True}]}

    async def wait(actor, predicate, reason):
        assert predicate(observed)
        return observed

    worker = load_worker(monkeypatch, SimpleNamespace(wait_observation=wait))
    session = object.__new__(worker.Session)
    session.running = False
    session.team_role = "Alpha"
    session.fixture = {"peer_group": True}
    session.initialized = {"encounters_pending": encounters_pending, "supplies_pending": True}
    session.actor = SimpleNamespace(name="Alpha", request=AsyncMock(return_value=observed))
    session.finish_setup = AsyncMock()

    async def run():
        assert await session.dispatch("setup_peer_group", {"mode": "identity"}) == {"uid": 1, "alias": "Alpha"}
        await session.dispatch("setup_peer_group", {"mode": "verify", "uid": 2})
        if encounters_pending:
            session.finish_setup.assert_not_awaited()
        else:
            assert session.finish_setup.await_count == 2
            session.finish_setup.assert_awaited_with(finalize_encounters=False, finalize_supplies=False)
        assert session.peer_group_ready
        session.running = True
        with pytest.raises(PermissionError):
            await session.dispatch("setup_peer_group", {"mode": "identity"})

    asyncio.run(run())


@pytest.mark.parametrize(("ready", "running"), [(False, False), (True, True)])
def test_deferred_encounter_rejects_unverified_group_or_live_game(monkeypatch, ready, running):
    from game.veloren import fixture

    worker = load_worker(monkeypatch)
    session = object.__new__(worker.Session)
    session.setup_administrator = (object(), object(), 1)
    session.initialized = {"encounters_pending": True}
    session.peer_group_ready, session.running = ready, running
    spawn = AsyncMock()
    monkeypatch.setattr(fixture, "initialize_encounters", spawn)
    with pytest.raises(RuntimeError, match="verified Group before gameplay"):
        asyncio.run(session.finish_setup())
    spawn.assert_not_awaited()


@pytest.mark.parametrize("supplies_pending", [False, True])
def test_deferred_encounter_spawns_once_then_retires_admin_before_play(monkeypatch, tmp_path, supplies_pending):
    from game.veloren import fixture
    from game.veloren.runtime import records

    declared, opening = player_scene()
    opening["nearby_entities"] = []
    events = []

    async def wait(actor, predicate, reason):
        assert predicate(opening)
        events.append("absence_verified")
        return opening

    async def spawn(admin, actor, task, contract, *, binding_reader):
        assert binding_reader == session.encounter_binding
        events.append("spawn")
        return {"encounters": [{"role": "wolf"}], "source_binding": {"uid": 2}, "opening": opening}

    async def close():
        events.append("admin_retired")

    async def supplies(admin, specifications):
        events.append("supplies")
        return []

    worker = load_worker(monkeypatch, SimpleNamespace(wait_observation=wait))
    session = object.__new__(worker.Session)
    administrator = (
        SimpleNamespace(process=SimpleNamespace(returncode=0), cleanup={}),
        SimpleNamespace(aclose=close), 1,
    )
    session.setup_administrator = administrator
    session.initialized = {"encounters_pending": True, "supplies_pending": supplies_pending, "supplies": []}
    session.peer_group_ready, session.running = False, False
    session.fixture, session.actor = declared, SimpleNamespace(request=AsyncMock(return_value=opening))
    declared["supplies"] = []
    session.record, session.output = {"world_fixture": {}}, tmp_path
    monkeypatch.setattr(fixture, "initialize_encounters", spawn)
    monkeypatch.setattr(fixture, "initialize_supplies", supplies)
    monkeypatch.setattr(fixture, "observe_remote_supplies", AsyncMock())
    monkeypatch.setattr(worker, "recipe_observation", AsyncMock(return_value=opening))
    monkeypatch.setattr(records, "write_fixture_record", lambda *args: None)

    async def reconnect():
        events.append("admin_reconnected")
        session.setup_administrator = administrator

    session.reconnect_setup_administrator = reconnect

    async def run():
        await session.finish_setup(finalize_encounters=False, finalize_supplies=False)
        assert session.setup_administrator is None
        assert session.initialized["encounters_pending"]
        session.peer_group_ready = True
        if supplies_pending:
            with pytest.raises(RuntimeError, match="all peers ready"):
                await session.finish_setup()
            assert "admin_reconnected" not in events
        session.team_ready = True
        await session.finish_setup()
        await session.finish_setup()

    asyncio.run(run())
    assert events == ["admin_retired", "absence_verified", "admin_reconnected",
                      *(["supplies"] if supplies_pending else []),
                      "spawn", "admin_retired", "absence_verified"]
    assert session.setup_administrator is None
    assert session.initialized["encounters_pending"] is False
    assert session.initialized["encounters"] == [{"role": "wolf"}]


def test_encounter_binding_uses_prevalidated_prefix_and_waits_for_current_uid(monkeypatch, tmp_path):
    from game.veloren.runtime import journal

    worker = load_worker(monkeypatch)
    session = object.__new__(worker.Session)
    session.running = False
    session.actor = object()
    session.oracle_output = tmp_path / "Alpha"
    session.snapshot_prefix = {"prepared": True}
    binding = {"uid": 12, "server_entity": "original-generation", "health": 100}
    calls = []

    def read(path, run_id, uid, *, prefix):
        calls.append((path, run_id, uid, prefix))
        return binding if len(calls) == 2 else None

    monkeypatch.setattr(journal, "snapshot_binding", read)
    assert asyncio.run(session.encounter_binding(session.actor, 12)) == binding
    assert calls == [(session.oracle_output / "private-native-oracle.ndjson", "Alpha",
                      12, session.snapshot_prefix)] * 2
    session.running = True
    with pytest.raises(RuntimeError, match="setup actor"):
        asyncio.run(session.encounter_binding(session.actor, 12))
    session.running = False
    with pytest.raises(RuntimeError, match="setup actor"):
        asyncio.run(session.encounter_binding(object(), 12))
    assert len(calls) == 2


def test_encounter_initialization_uses_same_reader_for_target_and_source(monkeypatch):
    from game.veloren import fixture

    declared, opening = player_scene()
    opening["self_identity"] = {"uid": 12}
    declared["encounters"] = [{"role": "wolf", "position": [10, 0, 1]}]
    actor = SimpleNamespace(request=AsyncMock(return_value=opening))
    reader = AsyncMock(return_value={"uid": 12, "health": 35, "dead": False})
    spawn = AsyncMock(return_value={"role": "wolf"})
    monkeypatch.setattr(fixture, "initialize_encounter", spawn)
    result = asyncio.run(fixture.initialize_encounters(
        "admin", actor, declared, binding_reader=reader,
    ))
    spawn.assert_awaited_once_with("admin", actor, declared["encounters"][0],
                                   [10, 0, 1], binding_reader=reader)
    reader.assert_awaited_once_with(actor, 12)
    assert result["source_binding"]["uid"] == 12
    opening["position"] = [1, 0, 1]
    with pytest.raises(fixture.FixtureMismatch, match="Initial player position"):
        asyncio.run(fixture.initialize_encounters("admin", actor, declared, binding_reader=reader))
    assert reader.await_count == 1


@pytest.mark.parametrize("count", [1, 3])
def test_native_group_rejects_unsupported_team_sizes_before_start(count):
    task = SimpleNamespace(
        game="veloren", tools=None, task_type="structured_tool",
        fixture={"peer_group": True}, participants=[None] * count,
    )
    with pytest.raises(ValueError, match="exactly two participants"):
        create_team_binding(task, Path("unused"), headless=True, recording=False, recording_fps=5)


def test_native_peer_heal_requires_original_enemy_hit_and_alive_window():
    first, last = evidence()
    initial, final = {}, {}
    for role, uid, entity in (("Alpha", 1, "player-generation-1"), ("Beta", 3, "peer-generation-1")):
        opening, closing = deepcopy(first), deepcopy(last)
        opening["self_identity"] = closing["self_identity"] = {"uid": uid}
        registry = {"run_id": "run", "nonce": "nonce", "opening_sequence": 10,
                    "identity": {"uid": uid}, "uid": uid, "server_entity": entity}
        for row, sequence in ((opening,10),(closing,20)):
            row["private_death_evidence"]={"schema":"livequest-player-deaths/1","registry":deepcopy(registry),
                                           "through_sequence":sequence,"events":[]}
        initial[role],final[role]=opening,closing
    damage=deepcopy(last["private_encounter_evidence"]["events"][0])
    damage.update(sequence=11)
    damage["data"].update(contributor={"Solo":2},contributor_entity="enemy-generation-1",
                          target_uid=1,target_entity="player-generation-1",server_time=5,
                          before=50,after=40,requested_amount=-10)
    heal=deepcopy(damage)
    heal.update(sequence=12)
    heal["data"].update(contributor={"Group":{"entity_uid":3,"group":7}},
                        contributor_entity="peer-generation-1",contributor_group=7,target_group=7,
                        cause={"Buff":"Regeneration"},before=40,after=42,requested_amount=2,server_time=20)
    lethal=deepcopy(last["private_encounter_evidence"]["events"][0]);lethal["sequence"]=13
    death=deepcopy(last["private_encounter_evidence"]["events"][1]);death["sequence"]=14
    final["Alpha"]["private_encounter_evidence"].update(events=[damage,heal,lethal,death],through_sequence=20)
    assert support_checks(initial,final,roles=["enemy"],window_seconds=30)["success"]
    for mutate in (
        lambda rows: rows[1]["data"].update(server_time=36),
        lambda rows: rows[0]["data"].update(contributor={"Solo":99}),
        lambda rows: rows[1]["data"].update(contributor={"Group":{"entity_uid":1,"group":7}},
                                            contributor_entity="player-generation-1"),
        lambda rows: rows[1]["data"].update(target_group=8),
    ):
        changed=deepcopy(final)
        mutate(changed["Alpha"]["private_encounter_evidence"]["events"])
        assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
        changed=deepcopy(final)
        rows=changed["Alpha"]["private_encounter_evidence"]["events"]
        rows[:]=[rows[0],rows[2],rows[1],rows[3]]
        for index,row in enumerate(rows):row["sequence"]=11+index
        assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
    changed=deepcopy(final)
    rows=changed["Alpha"]["private_encounter_evidence"]["events"]
    rows[:]=[rows[0],rows[2],rows[3],rows[1]]
    for index,row in enumerate(rows):row["sequence"]=11+index
    assert not support_checks(initial,changed,roles=["enemy"],window_seconds=30)["success"]
