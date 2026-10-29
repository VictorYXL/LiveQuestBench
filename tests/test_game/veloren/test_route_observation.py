"""Versioned route views must fail closed, not merely hide a default HUD setting."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import AsyncMock

import pytest

from benchmark.config import load_task
from game.veloren.fixture import validate_fixture
from tests.test_game.veloren.test_initialization import load_worker


SCHEMA = "native-route-local-view/1"
CAMERA = "native-local-camera/1"
SCENE = "native-solid-scene/1"
PROFILES = [("route_observation", SCHEMA), ("camera_observation", CAMERA), ("scene_observation", SCENE)]


def test_route_observation_is_explicit_versioned_and_route_only():
    fixture = load_task(Path("config/veloren/tasks/visual_motor/route_schema_transfer.yaml")).fixture
    assert "route_observation" not in validate_fixture(fixture)
    assert validate_fixture({**fixture, "route_observation": SCHEMA})["route_observation"] == SCHEMA
    for changed in (
        {**fixture, "route_observation": True},
        {**fixture, "route_observation": "native-route-local-view/2"},
        {**fixture, "route_observation": SCHEMA, "route_evidence": False},
    ):
        with pytest.raises(ValueError, match="route_observation"):
            validate_fixture(changed)


@pytest.mark.parametrize("field,schema", PROFILES)
def test_old_runtime_cannot_claim_local_route_view(monkeypatch, tmp_path, field, schema):
    worker = load_worker(monkeypatch)
    monkeypatch.setattr(worker, "validate_fixture", lambda value: value)
    session = worker.Session({
        "native_protection": "disabled by explicit renderer launch environment",
        "route_evidence": "native-client-route/2",
    }, tmp_path, "visual_motor", {"route_evidence": True, field: schema})
    with pytest.raises(ValueError, match="declared .* observation"):
        asyncio.run(session.start())


@pytest.mark.parametrize("field,schema", [("camera_observation", CAMERA), ("scene_observation", SCENE)])
def test_non_route_profiles_are_versioned_and_do_not_require_a_route_fixture(field, schema):
    fixture = load_task(Path("config/veloren/tasks/visual_motor/native_contract_settlement.yaml")).fixture
    fixture.pop("runtime_profile")
    assert validate_fixture({**fixture, field: schema})[field] == schema
    for version in (True, schema.replace("/1", "/2")):
        with pytest.raises(ValueError, match=field):
            validate_fixture({**fixture, field: version})


@pytest.mark.parametrize("field,schema", PROFILES)
@pytest.mark.parametrize("requested,advertised,accepted", [
    (None, None, True),
    (SCHEMA, SCHEMA, True),
    (SCHEMA, None, False),
    (None, SCHEMA, False),
])
def test_native_renderer_attestation_and_environment_are_required(
    monkeypatch, tmp_path, requested, advertised, accepted, field, schema,
):
    worker = load_worker(monkeypatch)
    requested = schema if requested is not None else None
    advertised = schema if advertised is not None else None
    environment_key = "LIVEQUEST_" + field.upper()
    monkeypatch.setenv(environment_key, "undeclared-inherited-profile")
    monkeypatch.setitem(sys.modules, "scripts.rpg_benchmark.lifecycle", SimpleNamespace(
        process_start_ticks=lambda pid: 1,
    ))
    actor = worker.LocalRenderer()
    actor.out, actor.name, actor.port, actor.frames = tmp_path, "Player", 1, tmp_path / "frames"
    actor.renderer = {"paths": {"assets": "unused-assets", "executable": "unused-renderer"}}
    setattr(actor, field, requested)
    actor._read = AsyncMock()

    async def launch(*args, **kwargs):
        assert kwargs["env"][environment_key] == (requested or "")
        actor.ready.set_result({})
        data = {"same_client": True}
        if advertised is not None:
            data[field] = advertised
        actor.renderer_ready.set_result({"data": data})
        return SimpleNamespace(pid=1)

    monkeypatch.setattr(worker.asyncio, "create_subprocess_exec", launch)

    async def check():
        try:
            if accepted:
                await actor.start()
            else:
                with pytest.raises(RuntimeError, match="declared .* observation"):
                    await actor.start()
        finally:
            await actor.reader_task
            actor.stderr.close()

    asyncio.run(check())
