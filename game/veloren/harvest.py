"""Native mushroom authoring and actor-local, read-only source-cell evidence."""

from copy import deepcopy
import asyncio
import math


def terrain_cell(query: dict, position: list[int]) -> dict:
    if query.get("terrain_query_schema_version") != "1.0":
        raise ValueError("Unsupported native terrain query schema")
    matches = []

    def visit(value):
        if isinstance(value, dict):
            if value.get("position") == position and "sprite" in value and "status" in value:
                matches.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(query)
    if (not matches or any(cell != matches[0] for cell in matches)
            or matches[0]["status"] != "loaded"):
        raise ValueError("Native terrain query lacks a consistent loaded source cell")
    return deepcopy(matches[0])


async def initialize_harvest(admin, actor, positions: list[list[int]]) -> dict:
    from scripts.rpg_benchmark import setup

    sites = []
    for point in positions:
        target = [point[0] + .5, point[1] + .5, point[2]]
        await setup.goto(admin, admin, target)
        await setup.command(admin, "make_sprite", "Mushroom")
        query = None
        for _ in range(30):
            query = await admin.request("inspect_terrain", {"position": target})
            cell = terrain_cell(query, point)
            if cell["sprite"] == "Mushroom":
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError("Declared native mushroom sprite was not observed")
        sites.append({"position": point, "cell": cell, "preparation_query": query})
    player = await actor.request("observe")
    return {"sites": sites, "player_uid": player["self_identity"]["uid"],
            "session_id": player["session_id"],
            "scope": "Native make_sprite before readiness; no runtime replenishment or hidden collector."}


async def harvest_snapshot(actor, observation: dict, prepared: dict, registry: dict | None) -> dict:
    if registry is None:
        registry = {
            "session_id": observation["session_id"], "uid": observation["self_identity"]["uid"],
            "opening_tick": observation["tick"], "preparation": deepcopy(prepared),
        }
        return {"schema": "livequest-native-harvest/1", "registry": registry,
                "phase": "opening", "cells": [
                    {"position": site["position"], "cell": site["cell"]}
                    for site in prepared["sites"]
                ]}
    cells = []
    for site in prepared["sites"]:
        point = site["position"]
        target = [point[0] + .5, point[1] + .5, point[2]]
        position = observation["position"]
        if math.dist(position[:2], target[:2]) > 9.5 or abs(position[2] - target[2]) > 1.9:
            cells.append({"position": point, "status": "outside_native_query_range"})
            continue
        query = await actor.request("inspect_terrain", {"position": target}, origin="private-validation")
        cells.append({"position": point, "cell": terrain_cell(query, point),
                      "query_binding": query["binding"]})
    return {"schema": "livequest-native-harvest/1", "registry": registry,
            "phase": "terminal", "cells": cells}
