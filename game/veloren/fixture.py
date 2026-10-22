"""Validate explicit native world and actor initialization, never implicit presets."""

from copy import deepcopy
import math
from pathlib import Path
import re


MAX_VOXELS = 8192


def cuboid(value: object, label: str) -> tuple[list, list]:
    region = fields(value, {"origin", "size"}, label)
    origin = vector(region["origin"], label + ".origin", integer=True)
    size = vector(region["size"], label + ".size", integer=True)
    if any(n < 1 for n in size) or math.prod(size) > MAX_VOXELS:
        raise ValueError(f"{label} must have positive dimensions and at most {MAX_VOXELS} voxels")
    return origin, size


def solid_voxels(fixture: dict) -> set[tuple[int, int, int]]:
    platform = fixture["platform"]
    regions = [{"origin": platform["origin"], "size": [*platform["size"], 1]}, *fixture.get("blocks", [])]
    voxels = set()
    for region in regions:
        origin, size = cuboid(region, "block region")
        voxels.update((origin[0] + x, origin[1] + y, origin[2] + z)
                      for x in range(size[0]) for y in range(size[1]) for z in range(size[2]))
        if len(voxels) > MAX_VOXELS:
            raise ValueError(f"Fixture exceeds {MAX_VOXELS} authored voxels")
    return voxels


def require_standing_point(point: list, voxels: set[tuple[int, int, int]], label: str) -> None:
    x, y, z = (math.floor(value) for value in point)
    if point[2] != z or (x, y, z - 1) not in voxels or any((x, y, z + dz) in voxels for dz in (0, 1)):
        raise ValueError(f"{label} must have authored support and two empty headroom cells")


def fields(value: object, required: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} requires exactly {sorted(required)}")
    return value


def vector(value: object, label: str, *, integer: bool = False) -> list:
    if not isinstance(value, list) or len(value) != 3 or any(
        type(item) not in ((int,) if integer else (int, float)) or not math.isfinite(item) for item in value
    ):
        raise ValueError(f"{label} must contain three finite {'integers' if integer else 'numbers'}")
    return value


def validate_fixture(value: object) -> dict:
    required = {"world_path", "world_seed", "time_of_day", "day_length", "calendar", "platform", "player_state"}
    optional = {"blocks", "stations", "supplies", "recipe_groups", "recipes"}
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"Veloren fixture requires exactly {sorted(required)} plus optional {sorted(optional)}")
    fixture = value
    if not isinstance(fixture["world_path"], str) or not fixture["world_path"].strip():
        raise ValueError("world_path must explicitly identify a native map file")
    if not Path(fixture["world_path"]).is_file():
        raise FileNotFoundError(f"Required Veloren map file is missing: {fixture['world_path']}")
    if type(fixture["world_seed"]) is not int or not 0 <= fixture["world_seed"] < 2**32:
        raise ValueError("world_seed must be a u32")
    if fixture["calendar"] != "none":
        raise ValueError("The current fixture loader requires calendar: none, not wall-clock holidays")
    if not isinstance(fixture["time_of_day"], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", fixture["time_of_day"]):
        raise ValueError("time_of_day must be HH:MM")
    if type(fixture["day_length"]) not in (int, float) or not math.isfinite(fixture["day_length"]) or fixture["day_length"] <= 0:
        raise ValueError("day_length must be positive finite minutes")
    platform = fields(fixture["platform"], {"origin", "size", "block"}, "platform")
    origin = vector(platform["origin"], "platform.origin", integer=True)
    size = platform["size"]
    if (not isinstance(size, list) or len(size) != 2
            or any(type(n) is not int or not 2 <= n <= 1024 for n in size)
            or math.prod(size) > MAX_VOXELS):
        raise ValueError(f"platform.size must be in [2, 1024] with at most {MAX_VOXELS} cells")
    if platform["block"] != "Rock":
        raise ValueError("The current native fixture author supports Rock platforms only")
    player = fields(fixture["player_state"], {"position", "look", "health", "inventory", "equipment"}, "player_state")
    point = vector(player["position"], "player_state.position")
    if not all(origin[i] < point[i] < origin[i] + size[i] for i in range(2)):
        raise ValueError("Player must start on the declared platform")
    for key in ("blocks", "stations", "supplies", "recipe_groups"):
        if key in fixture and not isinstance(fixture[key], list):
            raise ValueError(f"{key} must be a list")
    voxels = solid_voxels(fixture)
    # setup.site teleports the actor here before any additional blocks are authored.
    setup_start = [origin[0] + 2.5, origin[1] + size[1] / 2 + .5, origin[2] + 1]
    require_standing_point(setup_start, solid_voxels({**fixture, "blocks": []}), "Native setup start")
    require_standing_point(setup_start, voxels, "Native setup start")
    require_standing_point(point, voxels, "Player")
    occupied = set(voxels)
    for station in fixture.get("stations", []):
        fields(station, {"position", "sprite"}, "station")
        station_point = vector(station["position"], "station.position")
        require_standing_point(station_point, occupied, "Station")
        if station["sprite"] not in ("CraftingBench", "TanningRack"):
            raise ValueError("Only CraftingBench and TanningRack stations are supported")
        occupied.add(tuple(math.floor(value) for value in station_point))
    for station in fixture.get("stations", []):
        x, y, z = station["position"]
        require_standing_point([x - 2, y, z], occupied, "Station approach")
    require_standing_point(point, occupied, "Player")
    require_standing_point(setup_start, occupied, "Native setup start")
    for supply in fixture.get("supplies", []):
        fields(supply, {"position", "item", "amount"}, "supply")
        require_standing_point(vector(supply["position"], "supply.position"), occupied, "Supply")
        if (not isinstance(supply["item"], str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", supply["item"])
                or type(supply["amount"]) is not int or not 1 <= supply["amount"] <= 99):
            raise ValueError("Supply requires a native item ID and amount in [1, 99]")
    groups = fixture.get("recipe_groups", [])
    if any(not isinstance(group, str) or not re.fullmatch(r"common\.items\.recipes\.[a-z0-9_.]+", group)
           for group in groups) or len(set(groups)) != len(groups):
        raise ValueError("recipe_groups must contain unique native recipe group IDs")
    recipes = fixture.get("recipes", {})
    if not isinstance(recipes, dict) or any(
        not isinstance(recipe, str) or not re.fullmatch(r"[a-z0-9_]+", recipe) or type(known) is not bool
        for recipe, known in recipes.items()
    ):
        raise ValueError("recipes must map recipe keys to expected knowledge booleans")
    look = vector(player["look"], "player_state.look")
    if look != [0, 1, 0]:
        raise ValueError("The current native character profile requires initial look [0, 1, 0]")
    if type(player["health"]) not in (int, float) or not 0 < player["health"] <= 100:
        raise ValueError("Initial health must be in (0, 100]")
    inventory = player["inventory"]
    equipment = player["equipment"]
    if not isinstance(inventory, dict) or any(
        not isinstance(k, str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", k)
        or type(v) is not int or not 1 <= v <= 99 for k, v in inventory.items()
    ):
        raise ValueError("inventory must map native item IDs to positive counts")
    if not isinstance(equipment, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", v)
        for k, v in equipment.items()
    ):
        raise ValueError("equipment must map native equipped slots to item IDs")
    return deepcopy(fixture)


def item_id(item: dict) -> str:
    identifier = item["id"]
    if not isinstance(identifier, dict) or set(identifier) != {"Simple"}:
        raise ValueError("Fixture verification requires a simple native item identifier")
    return identifier["Simple"]


def inventory_counts(observation: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in observation["inventory"]["items"]:
        item = entry["item"]
        name = item_id(item)
        counts[name] = counts.get(name, 0) + item["amount"]
    return counts


async def recipe_observation(actor, fixture: dict, observation: dict | None = None) -> dict:
    """Supplement truncated recipe lists with private native knowledge evidence."""
    row = await actor.request("observe", origin="snapshot") if observation is None else observation
    listed = {entry["recipe"] for entry in row["known_recipes"]["items"]}
    outputs = {
        "mushroom_stick": "common.items.food.mushroom_stick",
        "simple_leather": "common.items.crafting_ing.leather.simple_leather",
        "rawhide_chest": "common.items.armor.hide.rawhide.chest",
    }
    evidence = {}
    for recipe in fixture.get("recipes", {}):
        if recipe in listed or not row["known_recipes"]["omitted"]:
            continue
        if recipe not in outputs:
            raise ValueError(f"No private native output mapping for omitted recipe: {recipe}")
        query = await actor.request("goal_recipes", {
            "output_item_id": outputs[recipe], "offset": 0, "page_size": 32,
        }, origin="private-validation")
        matches = [entry for entry in query["items"] if entry["recipe"] == recipe]
        if len(matches) != 1 or type(matches[0].get("character_known")) is not bool:
            raise RuntimeError(f"Native recipe query did not establish knowledge: {recipe}")
        evidence[recipe] = query
    return {**row, "private_recipe_evidence": evidence}


def verify_player(fixture: dict, observation: dict) -> None:
    player = fixture["player_state"]
    if math.dist(observation["position"], player["position"]) > .2:
        raise RuntimeError("Initial player position differs from the fixture")
    if math.dist(observation["look"], player["look"]) > .01:
        raise RuntimeError("Initial player look differs from the fixture")
    if (abs(observation["survival"]["health"]["current"] - player["health"]) > .01
            or observation["survival"]["buffs"] or observation["on_ground"] is not True
            or math.sqrt(sum(v * v for v in observation["velocity"])) >= .1):
        raise RuntimeError("Initial health, buffs or settled state differs from the fixture")
    equipped = {slot: item_id(item) for slot, item in observation["inventory"]["equipment"].items() if item is not None}
    if inventory_counts(observation) != player["inventory"] or equipped != player["equipment"]:
        raise RuntimeError("Initial inventory or equipment differs from the fixture")
    if fixture.get("recipes"):
        from game.veloren.evaluators.endpoints import known_recipes
        known = known_recipes(observation, required=list(fixture["recipes"]))
        if any((recipe in known) != expected for recipe, expected in fixture["recipes"].items()):
            raise RuntimeError("Initial recipe knowledge differs from the fixture")


async def initialize_fixture(admin, actor, fixture: dict) -> dict:
    """Author absolute geometry, set player/time fields and verify native readback."""
    from scripts.rpg_benchmark import setup

    fixture = validate_fixture(fixture)
    await setup.ready_observation(actor)
    platform = fixture["platform"]
    construction = await setup.site(
        admin, actor, "flat", {"flat_origin": platform["origin"]}, size=tuple(platform["size"]),
    )
    base = solid_voxels({**fixture, "blocks": []})
    additional = solid_voxels(fixture) - base
    blocks = await setup.author_voxels(admin, [list(point) for point in sorted(additional)]) if additional else []
    stations = []
    for station in fixture.get("stations", []):
        stations.append(await setup.station(admin, station["position"], station["sprite"], "flat"))
    for group in fixture.get("recipe_groups", []):
        await setup.learn(admin, actor, group)
    if inventory_counts(await actor.request("observe")) != fixture["player_state"]["inventory"]:
        await setup.clean_inventory(admin, actor)
        for name, amount in fixture["player_state"]["inventory"].items():
            await setup.gift(admin, actor, name, amount)
    supplies = []
    for supply in fixture.get("supplies", []):
        supplies.append(await setup.drop_supply(
            admin, supply["position"], supply["item"], supply["amount"], "flat",
        ))
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    await setup.command(admin, "time", fixture["time_of_day"])
    await setup.command(admin, "sudo", actor.name, "health", fixture["player_state"]["health"])
    opening = await recipe_observation(actor, fixture, await setup.ready_observation(actor))
    verify_player(fixture, opening)
    return {"fixture": fixture, "construction": construction, "blocks": blocks,
            "stations": stations, "supplies": supplies, "opening": opening}
