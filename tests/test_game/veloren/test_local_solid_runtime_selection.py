import hashlib
import json
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.fixture import validate_fixture
from game.veloren.runtime import session


PROFILES = {
    "camera_observation": "native-local-camera/1",
    "scene_observation": "native-solid-scene/1",
}


@pytest.mark.parametrize("route", [False, True])
def test_solid_runtime_is_explicit_hash_bound_and_does_not_inject_route(tmp_path, monkeypatch, route):
    generic = tmp_path / "generic.json"
    solid = tmp_path / "solid.json"
    generic.write_text("{}")
    solid.write_text(json.dumps(PROFILES))
    monkeypatch.setattr(session, "LOCAL_SOLID_RUNTIME_SHA256", hashlib.sha256(solid.read_bytes()).hexdigest())
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(generic))
    monkeypatch.setenv("LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME", str(solid))
    fixture = dict(PROFILES)
    if route:
        fixture.update(route_evidence=True, route_observation="native-route-local-view/1")
    before = dict(fixture)
    assert session.runtime_configuration(fixture)[0] == solid
    assert fixture == before
    assert session.runtime_configuration({})[0] == generic
    monkeypatch.delenv("LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME")
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        session.runtime_configuration(fixture)
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(solid))
    assert session.runtime_configuration(fixture)[0] == solid
    solid.write_text(solid.read_text() + "\n")
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        session.runtime_configuration(fixture)


@pytest.mark.parametrize("conflict", [
    {"runtime_profile": "self-funded-expedition/1"},
    {"message_contract": {"initialization_protocol": "initial-message-v3"}},
    {"market": {}},
])
def test_task_specific_runtime_profiles_cannot_be_combined_with_observation_profiles(conflict):
    fixture = load_task(Path("config/veloren/tasks/visual_motor/route_schema_transfer.yaml")).fixture
    with pytest.raises(ValueError, match="cannot qualify"):
        validate_fixture({**fixture, **PROFILES, **conflict})
    with pytest.raises(ValueError, match="cannot share"):
        session.runtime_configuration({**PROFILES, **conflict})


@pytest.mark.parametrize("fixture,setting,contents", [
    ({"message_contract": {"initialization_protocol": "initial-message-v2"}},
     "LIVEQUEST_VELOREN_INITIAL_MESSAGE_V2_RUNTIME", {"initial_message_protocol": "initial-message-v2"}),
    ({"message_contract": {"initialization_protocol": "initial-message-v3"}},
     "LIVEQUEST_VELOREN_INITIAL_MESSAGE_V3_RUNTIME", {"initial_message_protocol": "initial-message-v3"}),
    ({"market": {}}, "LIVEQUEST_VELOREN_MARKET_RUNTIME", {}),
])
def test_information_selectors_ignore_unrequested_solid_runtime(tmp_path, monkeypatch, fixture, setting, contents):
    runtime = tmp_path / "information.json"
    runtime.write_text(json.dumps(contents))
    monkeypatch.setenv(setting, str(runtime))
    monkeypatch.setenv("LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME", str(tmp_path / "must-not-open.json"))
    assert session.runtime_configuration(fixture)[0] == runtime
