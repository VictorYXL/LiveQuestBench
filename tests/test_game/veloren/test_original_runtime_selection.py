import hashlib
import json
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.fixture import validate_fixture
from game.veloren.runtime import session


@pytest.mark.parametrize("profile,setting", list(session.ORIGINAL_RUNTIME_ENVIRONMENTS.items()))
def test_original_override_requires_exact_qualified_manifest(tmp_path, monkeypatch, profile, setting):
    generic = tmp_path / "generic.json"
    original = tmp_path / "original.json"
    generic.write_text(json.dumps({"route_evidence": "native-client-route/2"}))
    original.write_text(json.dumps({"native_protection": "disabled by explicit renderer launch environment"}))
    monkeypatch.setattr(session, "ORIGINAL_RUNTIME_SHA256", hashlib.sha256(original.read_bytes()).hexdigest())
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(generic))
    monkeypatch.setenv(setting, str(original))
    assert session.runtime_configuration({"runtime_profile": profile})[0] == original
    assert session.runtime_configuration({})[0] == generic
    monkeypatch.delenv(setting)
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        session.runtime_configuration({"runtime_profile": profile})
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(original))
    assert session.runtime_configuration({"runtime_profile": profile})[0] == original
    original.write_text(original.read_text() + "\n")
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        session.runtime_configuration({"runtime_profile": profile})


@pytest.mark.parametrize("addition", [
    {"route_evidence": True}, {"pickup_evidence": True}, {"market": {}}, {"message_contract": {}},
])
def test_original_profile_cannot_authorize_newer_task_capabilities(addition):
    task = load_task(Path("config/veloren/tasks/structured_tools/self_funded_expedition.yaml"))
    with pytest.raises(ValueError, match="cannot qualify newer native evidence"):
        validate_fixture({**task.fixture, **addition})


def test_unknown_runtime_profile_is_rejected_before_runtime_selection():
    with pytest.raises(ValueError, match="Unsupported"):
        session.runtime_configuration({"runtime_profile": "unreviewed/1"})
