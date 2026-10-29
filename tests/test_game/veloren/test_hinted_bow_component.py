import importlib.util
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.error import HTTPError

import pytest

from game.backends.x11.actions import ActionError


path = Path(__file__).parents[2] / "fixtures/veloren/hinted_bow_component.py"
spec = importlib.util.spec_from_file_location("hinted_bow_component", path)
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)


def test_component_shot_budget_is_global_and_preserves_charge_release_settling():
    commands, shots = component.bounded_commands([["shot", "south"]], {"north": 11})
    assert sum(shots.values()) == 12
    assert [row["name"] for row in commands] == [
        "mouse_down", "wait", "mouse_up", "wait", "release_all", "wait"]
    assert commands[-1]["arguments"]["milliseconds"] == 250
    with pytest.raises(ValueError, match="at most12"):
        component.bounded_commands([["shot", "south"]], shots)


def test_component_rejects_nonpublic_operations_and_oversized_batches():
    with pytest.raises(ValueError, match="Unknown"):
        component.bounded_commands([["teleport", 1, 2, 3]], {})
    with pytest.raises(ValueError, match="bound"):
        component.bounded_commands([["wait", 9600]], {})


def test_actual_oversized_scroll_is_rejected_locally_before_any_dispatch():
    with pytest.raises(ActionError, match="steps"):
        component.bounded_commands([["hold", "w", 100], ["scroll", 24], ["wait", 400]], {})


def test_http_rejection_is_persisted_without_releasing_an_ambiguous_shot_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(component, "OUT", tmp_path)
    (tmp_path / "component-ready.json").write_text(json.dumps({
        "start": time.monotonic(), "deadline": time.monotonic() + 30}))
    (tmp_path / "control.json").write_text('{"url":"http://127.0.0.1:12345"}')

    def rejected(request, timeout):
        raise HTTPError(request.full_url, 500, "Rejected", {}, BytesIO(b'{"error":"rejected"}'))

    monkeypatch.setattr(component, "urlopen", rejected)
    with pytest.raises(HTTPError):
        component.control(['[["shot","south"]]'])
    error = json.loads((tmp_path / "component-errors.jsonl").read_text())
    assert error["response"] == '{"error":"rejected"}'
    assert error["shot_attempts_remain_reserved"] == {"south": 1}
    assert json.loads((tmp_path / "component-shots.json").read_text()) == {"south": 1}
