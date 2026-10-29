from copy import deepcopy

import pytest

from game.veloren.evaluators.harvest import harvest_checks, validate_harvest
from game.veloren.harvest import terrain_cell
from game.veloren.fixture import validate_fixture
from game.veloren.structured_tools.interface import validate_tool


PARAMETERS = {
    "source_cells": [[10, 0, 1], [12, 0, 1]],
    "inventory": [{"item": "common.items.food.mushroom", "min_count": 2, "min_delta": 2}],
    "position": {"target": [11, 0, 1], "horizontal_tolerance": 2,
                 "vertical_tolerance": .5, "max_speed": .1},
}


def snapshots():
    sites = []
    for point in PARAMETERS["source_cells"]:
        cell = {"position": point, "status": "loaded", "sprite": "Mushroom", "solid": False}
        query = {"terrain_query_schema_version": "1.0", "support_candidates": [
            {"foot_clearance": {"cells": [cell]}},
        ]}
        sites.append({"position": point, "cell": cell, "preparation_query": query})
    initial = {
        "session_id": "player", "self_identity": {"uid": 7}, "tick": 10,
        "survival": {"health": {"current": 100}},
        "position": [0, 0, 1], "velocity": [0, 0, 0], "on_ground": True,
        "inventory": {"items": []},
        "private_harvest_evidence": {
            "schema": "livequest-native-harvest/1", "phase": "opening",
            "registry": {"session_id": "player", "uid": 7, "opening_tick": 10,
                         "preparation": {"player_uid": 7, "session_id": "player", "sites": sites}},
            "cells": [{"position": site["position"], "cell": deepcopy(site["cell"])} for site in sites],
        },
    }
    final = deepcopy(initial)
    final.update(position=[11, 0, 1], tick=40)
    final["inventory"]["items"] = [
        {"item": {"id": {"Simple": "common.items.food.mushroom"}, "amount": 2}},
    ]
    evidence = final["private_harvest_evidence"]
    evidence["phase"] = "terminal"
    for cell in evidence["cells"]:
        cell["cell"]["sprite"] = "Empty"
        cell["query_binding"] = {"session_id": "player", "self_identity": {"uid": 7},
                                 "tick": 41, "actor_position": [11, 0, 1]}
    return initial, final


def test_source_plants_required_in_addition_to_fungible_inventory():
    initial, final = snapshots()
    assert harvest_checks(initial, initial, **PARAMETERS)["success"] is False
    assert harvest_checks(initial, final, **PARAMETERS)["success"] is True
    final["private_harvest_evidence"]["cells"][0]["cell"]["sprite"] = "Mushroom"
    assert harvest_checks(initial, final, **PARAMETERS)["success"] is False


def test_outside_query_range_is_a_failed_endpoint_not_invented_cell_state():
    initial, final = snapshots()
    final["position"] = [0, 0, 1]
    final["private_harvest_evidence"]["cells"] = [
        {"position": point, "status": "outside_native_query_range"}
        for point in PARAMETERS["source_cells"]
    ]
    assert harvest_checks(initial, final, **PARAMETERS)["success"] is False
    with pytest.raises(ValueError, match="within native query range"):
        validate_harvest(**{**PARAMETERS, "position": {**PARAMETERS["position"], "target": [0, 0, 1]}})


@pytest.mark.parametrize("change", ["registry", "stale", "observer"])
def test_native_harvest_rejects_rewritten_or_stale_identity(change):
    initial, final = snapshots()
    evidence = final["private_harvest_evidence"]
    if change == "registry":
        evidence["registry"]["uid"] = 8
    elif change == "stale":
        evidence["cells"][0]["query_binding"]["tick"] = 20
    else:
        evidence["cells"][0]["query_binding"]["self_identity"]["uid"] = 8
    with pytest.raises(ValueError):
        harvest_checks(initial, final, **PARAMETERS)


def test_local_terrain_cell_cannot_be_inferred_from_an_unloaded_or_conflicting_sample():
    cell = {"position": [1, 2, 3], "status": "loaded", "sprite": "Mushroom"}
    query = {"terrain_query_schema_version": "1.0", "samples": [cell]}
    assert terrain_cell(query, [1, 2, 3]) == cell
    query["samples"].append({**cell, "sprite": "Empty"})
    with pytest.raises(ValueError, match="consistent loaded"):
        terrain_cell(query, [1, 2, 3])


def test_collect_is_an_integer_voxel_primitive_not_a_navigation_command():
    assert validate_tool("CollectTool", {"x": 1, "y": 2, "z": 3}) == (
        "collect", {"position": [1, 2, 3]},
    )
    with pytest.raises(ValueError):
        validate_tool("CollectTool", {"x": 1.5, "y": 2, "z": 3})


def test_source_plot_rejects_injected_actors(veloren_fixture):
    fixture = deepcopy(veloren_fixture)
    fixture.update(harvest_sites=[[18708, 10806, 501]], merchant={})
    with pytest.raises(ValueError, match="without injected actors"):
        validate_fixture(fixture)


@pytest.mark.parametrize("refused", [False, True])
def test_public_terrain_inspection_preserves_native_readout_and_refusal(tmp_path, veloren_fixture, refused):
    import asyncio
    from types import SimpleNamespace
    from game.veloren.game import VelorenGame

    query = {"terrain_query_schema_version": "1.0", "samples": [
        {"position": [1, 2, 3], "status": "loaded", "sprite": "Mushroom", "solid": False},
    ]}
    native = ({"action_type": "inspect_terrain", "status": "refused",
               "detail": {"code": "terrain_query_out_of_bounds"}} if refused else query)

    async def request(operation, **arguments):
        assert operation == "action"
        assert arguments == {"timeout": None, "action_type": "inspect_terrain", "position": [1, 2, 3]}
        return native

    game = VelorenGame(output_dir=tmp_path, fixture=veloren_fixture, track="structured_tool")
    game.phase = "running"
    game._session = SimpleNamespace(check_ready=lambda: None, request=request)
    result = asyncio.run(game._call_tool("InspectTerrainTool", {"x": 1, "y": 2, "z": 3}))
    assert result == (native if refused else {
        "action_type": "inspect_terrain", "status": "completed", "detail": query,
    })
