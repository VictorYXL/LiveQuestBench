"""Native source-cell clearing plus fungible holdings at the surveyed site."""

import math
from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state
from game.veloren.harvest import terrain_cell


def validate_harvest(*, source_cells: list[list[int]], **state) -> None:
    if (not isinstance(source_cells, list) or not 1 <= len(source_cells) <= 16
            or any(not isinstance(point, list) or len(point) != 3
                   or any(type(value) is not int for value in point) for point in source_cells)
            or len({tuple(point) for point in source_cells}) != len(source_cells)):
        raise ValueError("Harvest sources require distinct native integer voxel positions")
    validate_state(**state)
    endpoint = state.get("position")
    if endpoint is None or any(
        math.dist(endpoint["target"][:2], [point[0] + .5, point[1] + .5])
        + endpoint["horizontal_tolerance"] > 9
        or abs(endpoint["target"][2] - point[2]) + endpoint["vertical_tolerance"] > 1.8
        for point in source_cells
    ):
        raise ValueError("Harvest endpoint must keep every scored source within native query range")


def harvest_checks(initial: dict, final: dict, *, source_cells: list[list[int]], **state) -> dict:
    validate_harvest(source_cells=source_cells, **state)
    first, last = (row["private_harvest_evidence"] for row in (initial, final))
    registry = first["registry"]
    if (first["schema"] != "livequest-native-harvest/1" or last["schema"] != first["schema"]
            or last["registry"] != registry or first["phase"] != "opening"
            or last["phase"] not in ("opening", "terminal")
            or registry["session_id"] != initial["session_id"]
            or registry["session_id"] != final["session_id"]
            or registry["uid"] != initial["self_identity"]["uid"]
            or registry["uid"] != final["self_identity"]["uid"]
            or registry["opening_tick"] != initial["tick"]):
        raise ValueError("Native harvest registry or player identity changed")
    preparation = registry["preparation"]
    if (preparation["player_uid"] != registry["uid"]
            or preparation["session_id"] != registry["session_id"]):
        raise ValueError("Native mushroom preparation belongs to another player")
    prepared = {tuple(site["position"]): site for site in preparation["sites"]}
    current = {tuple(site["position"]): site for site in last["cells"]}
    if len(prepared) != len(preparation["sites"]) or len(current) != len(last["cells"]):
        raise ValueError("Duplicate native source-cell evidence")
    result = state_checks(initial, final, **state)
    collected = []
    for point in source_cells:
        site = prepared[tuple(point)]
        if (site["cell"]["status"] != "loaded" or site["cell"]["sprite"] != "Mushroom"
                or terrain_cell(site["preparation_query"], point) != site["cell"]):
            raise ValueError("Source did not begin as an actual native mushroom")
        cell = current[tuple(point)]
        passed = False
        if "cell" in cell and last["phase"] == "terminal":
            binding = cell["query_binding"]
            target = [point[0] + .5, point[1] + .5, point[2]]
            if (binding["session_id"] != final["session_id"]
                    or binding["self_identity"]["uid"] != registry["uid"]
                    or type(binding["tick"]) is not int or binding["tick"] <= initial["tick"]
                    or binding["tick"] < final["tick"]
                    or math.dist(binding["actor_position"][:2], target[:2]) > 10
                    or abs(binding["actor_position"][2] - target[2]) > 2):
                raise ValueError("Harvest source readback is not a fresh local native observation")
            observed = cell["cell"]
            passed = (observed["position"] == point and observed["status"] == "loaded"
                      and observed["sprite"] == "Empty" and observed["solid"] is False)
        elif "cell" not in cell and cell.get("status") != "outside_native_query_range":
            raise ValueError("Native harvest source evidence is missing")
        collected.append({"position": point, "passed": passed})
    result["checks"].append({"kind": "native_source_plants_cleared", "cells": collected,
                             "passed": all(cell["passed"] for cell in collected)})
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " Declared source plants must change from native Mushroom to Empty, observed locally "
        "at the final surveyed site. Inventory is fungible; no returned item-instance UID claim. "
        "This proves cleared plants, not player-owned harvest-event attribution. "
        "No harvestable plant is replaced after readiness."
    )
    return result


def evaluate_harvest(before: Path, after: Path, **parameters) -> dict:
    return harvest_checks(*load_pair(before, after), **parameters)
