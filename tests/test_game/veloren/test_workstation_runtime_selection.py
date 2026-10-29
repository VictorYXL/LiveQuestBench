import hashlib
import json
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.evaluators.itinerary import route_samples
from game.veloren.fixture import validate_fixture
from game.veloren.runtime import workstation
from game.veloren.runtime.session import runtime_configuration
from tests.test_game.veloren.test_workstation import PARAMETERS, boundaries, workstation_checks


def task_for(track="structured_tools"):
    return load_task(Path("config/veloren/tasks") / track / "directions_to_workstation.yaml")


def binding(task, output, **overrides):
    arguments = dict(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools, output_dir=output,
        headless=True, recording=False, recording_fps=10,
    )
    return create_binding(**(arguments | overrides))


def test_workstation_exact_override_does_not_downgrade_generic_runtime(tmp_path, monkeypatch):
    original = tmp_path / "original.json"
    generic = tmp_path / "generic.json"
    config = {"route_evidence": "native-client-route/1"}
    original.write_text(json.dumps(config))
    generic.write_text(json.dumps({"route_evidence": "native-client-route/2"}))
    monkeypatch.setattr(workstation, "RUNTIME_SHA256", hashlib.sha256(original.read_bytes()).hexdigest())
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    monkeypatch.setattr(workstation, "CONFIG_SHA256", hashlib.sha256(canonical).hexdigest())
    monkeypatch.setenv(workstation.ENVIRONMENT, str(original))
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(generic))
    fixture = task_for().fixture
    assert runtime_configuration(fixture)[0] == original
    assert runtime_configuration({})[0] == generic
    assert workstation.expected_route_schema(fixture, config) == "native-client-route/1"
    assert workstation.expected_route_schema({}, config) == "native-client-route/2"
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        workstation.expected_route_schema(fixture, {**config, "unqualified_change": True})
    monkeypatch.delenv(workstation.ENVIRONMENT)
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        runtime_configuration(fixture)
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(original))
    assert runtime_configuration(fixture)[0] == original
    original.write_text(original.read_text() + "\n")
    with pytest.raises(ValueError, match="exact independently qualified runtime"):
        runtime_configuration(fixture)


@pytest.mark.parametrize("track", ["structured_tools", "visual_motor"])
def test_workstation_registers_both_tracks_and_rejects_received_opening_directions(tmp_path, track):
    task = task_for(track)
    result = binding(task, tmp_path / "game")
    before = tmp_path / "before"
    before.mkdir()
    (before / "observation.json").write_text(json.dumps({"dialogue_markers": []}))
    result.verify_initial(before)
    (before / "observation.json").write_text(json.dumps({"dialogue_markers": [{}]}))
    with pytest.raises(RuntimeError, match="without received directions"):
        result.verify_initial(before)


def test_workstation_profile_cannot_authorize_generic_route_evaluators(tmp_path):
    task = task_for()
    with pytest.raises(ValueError, match="profile and evaluator must match"):
        binding(task, tmp_path / "generic", evaluator="itinerary")
    fixture = dict(task.fixture)
    fixture.pop("runtime_profile")
    with pytest.raises(ValueError, match="profile and evaluator must match"):
        binding(task, tmp_path / "unbound", fixture=fixture)
    with pytest.raises(ValueError, match="requires its original route evidence"):
        validate_fixture({**task.fixture, "route_evidence": False})
    with pytest.raises(ValueError, match="cannot qualify newer native evidence"):
        validate_fixture({**task.fixture, "route_observation": "native-route-local-view/1"})


def test_route_versions_are_not_relabelled_and_downed_guard_is_retained():
    first, last = boundaries()
    assert workstation_checks(first, last, **PARAMETERS)["success"]
    with pytest.raises(ValueError, match="schema mismatch"):
        route_samples(first, last)
    last["survival"]["health"]["downed"] = True
    assert not workstation_checks(first, last, **PARAMETERS)["success"]
    for boundary in (first, last):
        boundary["private_route_evidence"]["route_schema"] = "native-client-route/2"
    assert route_samples(first, last)
    with pytest.raises(ValueError, match="schema mismatch"):
        workstation_checks(first, last, **PARAMETERS)
