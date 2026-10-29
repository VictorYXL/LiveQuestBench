import json
from pathlib import Path

import pytest

from benchmark.config import load_task
from game.veloren.binding import create_binding
from game.veloren.fixture import validate_fixture
from game.veloren.runtime.session import runtime_configuration


def test_information_runtime_overrides_do_not_replace_other_task_defaults(tmp_path, monkeypatch):
    base = tmp_path / "base.json"
    message = tmp_path / "message.json"
    market = tmp_path / "market.json"
    base.write_text(json.dumps({"route_evidence": "native-client-route/2"}))
    message.write_text(json.dumps({"initial_message_protocol": "initial-message-v3"}))
    market.write_text(json.dumps({"route_evidence": "native-client-route/1"}))
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(base))
    monkeypatch.setenv("LIVEQUEST_VELOREN_INITIAL_MESSAGE_V3_RUNTIME", str(message))
    monkeypatch.setenv("LIVEQUEST_VELOREN_MARKET_RUNTIME", str(market))
    assert runtime_configuration({})[0] == base
    assert runtime_configuration({"market": {}})[0] == market
    fixture = {"message_contract": {"initialization_protocol": "initial-message-v3"}}
    assert runtime_configuration(fixture)[0] == message
    monkeypatch.delenv("LIVEQUEST_VELOREN_INITIAL_MESSAGE_V3_RUNTIME")
    with pytest.raises(ValueError, match="matching native runtime"):
        runtime_configuration(fixture)
    monkeypatch.setenv("LIVEQUEST_VELOREN_RUNTIME", str(message))
    assert runtime_configuration(fixture)[0] == message


@pytest.mark.parametrize("track", ["structured_tools", "visual_motor"])
@pytest.mark.parametrize("task_id", ["native_message_courier_initial_v3", "market_stock_reconciliation"])
def test_reviewed_information_tasks_bind_exact_registered_tracks(tmp_path, track, task_id):
    task = load_task(Path("config/veloren/tasks") / track / f"{task_id}.yaml")
    assert task.time_limit_seconds == 2700
    assert not task.fixture.get("route_evidence")
    create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools, output_dir=tmp_path / "game",
        headless=True, recording=False, recording_fps=10,
    )


def test_incompatible_information_preparation_is_rejected_before_authoring():
    task = load_task(Path("config/veloren/tasks/structured_tools/native_message_courier_initial_v3.yaml"))
    with pytest.raises(ValueError, match="separate fixtures"):
        validate_fixture({**task.fixture, "market": {}})
    with pytest.raises(ValueError, match="harvest plot"):
        validate_fixture({**task.fixture, "harvest_sites": [[18703, 10809, 501]]})
