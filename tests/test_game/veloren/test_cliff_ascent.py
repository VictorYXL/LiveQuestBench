"""Composed route/2 task admission; synthetic checks are not native qualification."""

from copy import deepcopy

import pytest

from benchmark.config import load_task
from tests.test_game.veloren.test_itinerary import score
from tests.test_game.veloren.test_qualified_tasks import ROOT, bind, endpoints


@pytest.fixture(params=["structured_tools", "visual_motor"])
def cliff(request):
    return load_task(ROOT / "config/veloren/tasks" / request.param / "cliff_ledge_ascent.yaml")


def snapshots(task):
    initial, final = score([deepcopy(task.evaluator_parameters["visits"][0]["target"])])
    for row in (initial, final):
        row["tick"] = row["private_route_evidence"]["through_tick"]
        row["position"] = task.fixture["player_state"]["position"]
        row["private_route_evidence"]["route_samples"][0]["position"] = row["position"]
        row["inventory"] = {"items": [
            {"item": {"id": {"Simple": goal["item"]}, "amount": goal["min_count"]}}
            for goal in task.evaluator_parameters["inventory"]
        ]}
    final["survival"]["health"]["current"] = .390625
    return initial, final


def test_cliff_pair_admits_and_requires_a_new_upper_visit(cliff, tmp_path):
    binding = bind(cliff, tmp_path / "game")
    binding.game.phase = "ready"
    _, tools = binding.controls()
    if cliff.task_type == "structured_tool":
        assert {tool.name for tool in tools} == set(cliff.tools)
    initial, final = snapshots(cliff)
    assert not binding.evaluate(*endpoints(tmp_path, initial, initial))["success"]
    assert binding.evaluate(*endpoints(tmp_path, initial, final))["success"]


@pytest.mark.parametrize("failure", ["wrong_floor", "inventory", "dead", "airborne", "moving"])
def test_cliff_scorer_preserves_region_and_endpoint_requirements(cliff, tmp_path, failure):
    initial, final = snapshots(cliff)
    if failure == "wrong_floor":
        final["private_route_evidence"]["route_samples"][1]["position"][2] += 2
    elif failure == "inventory":
        final["inventory"]["items"] = []
    elif failure == "dead":
        final["survival"]["health"]["current"] = 0
    elif failure == "airborne":
        final["on_ground"] = False
    else:
        final["velocity"] = [1, 0, 0]
    assert not bind(cliff, tmp_path / "game").evaluate(*endpoints(tmp_path, initial, final))["success"]


def test_cliff_does_not_relabel_historical_route_v1(cliff, tmp_path):
    initial, final = snapshots(cliff)
    for row in (initial, final):
        row["private_route_evidence"]["route_schema"] = "native-client-route/1"
    with pytest.raises(ValueError, match="schema mismatch"):
        bind(cliff, tmp_path / "game").evaluate(*endpoints(tmp_path, initial, final))
