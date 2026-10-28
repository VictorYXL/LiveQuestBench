"""World-copy isolation, server cleanup and opt-in native fixture initialization."""

import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from benchmark.config import load_experiment, load_task
from game.veloren.fixture import verify_player


ROOT = Path(__file__).resolve().parents[2]


def test_retired_expedition_is_rejected_before_native_launch(tmp_path):
    pytest.importorskip("nbtlib")
    from game.minecraft.runtime.session import MinecraftSession

    (tmp_path / "livequest-expedition.json").write_text("{}")
    session = object.__new__(MinecraftSession)
    session.world = tmp_path
    with pytest.raises(ValueError, match="Retired expedition fixtures"):
        session.preflight()


@pytest.mark.parametrize("game", ["minecraft", "veloren"])
@pytest.mark.parametrize("mode", ["structured_tools", "visual_motor"])
@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.4-nano"])
def test_all_experiments_include_exactly_l1_through_l3(game, mode, model):
    directory = ROOT / "tests/fixtures/legacy/config" / game / "experiments" / f"{model}-low"
    combined = load_experiment(directory / f"{mode}_all.yaml")
    levels = [load_experiment(directory / f"{mode}_L{level}.yaml") for level in (1, 2, 3)]
    expected = {task.source.path: task for level in levels for task in level.tasks}
    assert len(combined.tasks) == len(expected) == 30
    assert {task.source.path: task for task in combined.tasks} == expected
    assert all(level.agents == combined.agents for level in levels)
    assert all(level.repetitions == combined.repetitions for level in levels)
    assert len(combined.agents) == 6
    assert all(agent.model.name == model and agent.model.reasoning_effort == "low"
               for agent in combined.agents)
    assert model.replace(".", "_").replace("-", "_") in combined.id
    if game == "minecraft":
        exploratory = load_task(ROOT / f"tests/fixtures/legacy/config/minecraft/tasks/{mode}/lost_expedition.yaml")
        assert exploratory.source.path not in expected


def test_model_profiles_change_only_model_and_identifiers():
    from dataclasses import asdict

    for game in ("minecraft", "veloren"):
        directory = ROOT / "tests/fixtures/legacy/config" / game / "experiments"
        for source in (directory / "gpt-6-astra-low").glob("*.yaml"):
            baseline = load_experiment(source)
            for model in ("gpt-5.6-sol", "gpt-5.4-nano"):
                compared = load_experiment(directory / f"{model}-low" / source.name)
                assert compared.tasks == baseline.tasks
                assert compared.repetitions == baseline.repetitions
                assert [a.name for a in compared.agents] == [a.name for a in baseline.agents]
                for left, right in zip(baseline.agents, compared.agents, strict=True):
                    expected, actual = asdict(left), asdict(right)
                    expected["id"] = actual["id"]
                    expected["model"]["name"] = model
                    assert expected == actual


def test_world_reset_copies_are_isolated(tmp_path):
    pytest.importorskip("nbtlib")
    from game.minecraft.evaluators.world import read_blocks
    from game.minecraft.init_player_state import PlayerState
    from game.minecraft.runtime.session import copy_world

    source_file = ROOT / "tests/fixtures/legacy/config/minecraft/tasks/structured_tools/collect_logs.yaml"
    relative = load_task(source_file)
    source = Path(relative.fixture["world_path"])
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob("*") if p.is_file()}
    state = PlayerState.from_dict(relative.fixture["player_state"])
    for name in ("first", "second"):
        destination = tmp_path / name
        copy_world(source, destination, state, UUID(int=1))
        assert read_blocks(destination, (0, 71, 0), (0, 72, 0), state.dimension) == {
            (0, 71, 0): "minecraft:grass_block", (0, 72, 0): "minecraft:air",
        }
        if name == "first":
            (destination / "region/r.0.0.mca").write_bytes(b"deliberately damaged disposable working copy")
    assert hashes == {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in source.rglob("*") if p.is_file()}
    assert not (source / "playerdata").exists()


@pytest.mark.parametrize("fallback", [False, True])
def test_veloren_server_retires_after_success_or_map_fallback(tmp_path, monkeypatch, fallback):
    lifecycle = SimpleNamespace(
        free_port=Mock(side_effect=[14000, 14001]), protected_ports=lambda: set(),
        process_start_ticks=lambda pid: 123, assert_owned=Mock(),
        wait_for_server=AsyncMock(return_value=42),
    )
    package = ModuleType("scripts.rpg_benchmark")
    package.lifecycle = lifecycle
    native_module = ModuleType("scripts.rpg_benchmark.native")
    native_module.NativeConfig = object
    monkeypatch.setitem(sys.modules, "scripts", ModuleType("scripts"))
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark", package)
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.native", native_module)
    spec = importlib.util.spec_from_file_location("fixture_server_test", ROOT / "game/veloren/runtime/server.py")
    assert spec is not None and spec.loader is not None
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    fixture = load_task(ROOT / "tests/fixtures/legacy/config/veloren/tasks/structured_tools/move_2_metres.yaml").fixture
    world = Path(fixture["world_path"])
    digest = hashlib.sha256(world.read_bytes()).hexdigest()
    native = SimpleNamespace(
        require_inputs=Mock(), assets=tmp_path / "assets-without-map",
        server=tmp_path / "server", root=tmp_path,
    )
    provision = SimpleNamespace(
        communicate=AsyncMock(return_value=(b"", b"")), returncode=0,
    )
    spawn = AsyncMock(return_value=provision)
    monkeypatch.setattr(server.asyncio, "create_subprocess_exec", spawn)
    process = SimpleNamespace(
        pid=12345, returncode=0, poll=Mock(return_value=None),
        terminate=Mock(), wait=Mock(return_value=0),
    )

    def launch(*args, **kwargs):
        message = f"Assets found path={native.assets}\n"
        if fallback:
            message += "Couldn't parse modern map\n"
        kwargs["stdout"].write(message.encode())
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr(server.subprocess, "Popen", launch)
    record = {"username": "test-admin"}

    async def check():
        async with server.fixture_server(tmp_path, record, native, fixture):
            settings = (tmp_path / "userdata/server/server_config/settings.ron").read_text()
            assert f"map_file:Some(Load({json.dumps(str(world))}))" in settings
            assert "LoadAsset" not in settings
            assert record["world_fixture"]["map_path"] == str(world)
            assert record["world_fixture"]["map_sha256"] == digest

    if fallback:
        with pytest.raises(RuntimeError, match="fallback"):
            asyncio.run(check())
    else:
        asyncio.run(check())
    assert hashlib.sha256(world.read_bytes()).hexdigest() == digest
    assert record["server_stopped"] is True
    process.terminate.assert_called_once()


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_VELOREN_TEST") != "1", reason="Opt-in native fixture initialization")
def test_veloren_changed_configuration_is_applied(headless, recording):
    from game.veloren.game import VelorenGame

    fixture = load_task(ROOT / "tests/fixtures/legacy/config/veloren/tasks/structured_tools/move_2_metres.yaml").fixture
    fixture["platform"]["origin"][0] += 16
    fixture["player_state"]["position"][0] += 16
    fixture["player_state"]["health"] = 95
    fixture["player_state"]["inventory"] = {"common.items.food.cheese": 2}
    output = ROOT / "output/test" / f"veloren-fixture-parameters-{uuid4().hex}"
    game = VelorenGame(output_dir=output, fixture=fixture, track="structured_tool",
                       headless=headless, recording=recording)

    async def scenario():
        try:
            await game.start()
            before = await game.save_snapshot(output / "before")
            observation = json.loads((before / "observation.json").read_text())
            verify_player(fixture, observation)
            receipt = json.loads((output / "fixture.json").read_text())
            assert receipt["construction"]["origin"] == fixture["platform"]["origin"]
            assert receipt["world"]["configuration"] == fixture
            assert receipt["world"]["map_sha256"]
        finally:
            await game.close()

    asyncio.run(scenario())
