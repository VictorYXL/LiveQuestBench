"""Validate explicit native world and actor initialization, never implicit presets."""

from copy import deepcopy
import math
import re


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
    fixture = fields(value, {"map_asset", "world_seed", "time_of_day", "day_length", "calendar", "platform", "player_state"},
                     "Veloren fixture")
    if not isinstance(fixture["map_asset"], str) or not re.fullmatch(r"world\.map\.[A-Za-z0-9_]+", fixture["map_asset"]):
        raise ValueError("map_asset must explicitly identify an installed world.map asset")
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
            or any(type(n) is not int or not 2 <= n <= 32 for n in size)):
        raise ValueError("platform.size must contain two integers in [2, 32]")
    if platform["block"] != "Rock":
        raise ValueError("The current native fixture author supports Rock platforms only")
    player = fields(fixture["player_state"], {"position", "look", "health", "inventory", "equipment"}, "player_state")
    point = vector(player["position"], "player_state.position")
    if not all(origin[i] < point[i] < origin[i] + size[i] for i in range(2)) or point[2] != origin[2] + 1:
        raise ValueError("Player must start on the declared platform")
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


async def initialize_fixture(admin, actor, fixture: dict) -> dict:
    """Author absolute geometry, set player/time fields and verify native readback."""
    from scripts.rpg_benchmark import setup

    fixture = validate_fixture(fixture)
    await setup.ready_observation(actor)
    platform = fixture["platform"]
    construction = await setup.site(
        admin, actor, "flat", {"flat_origin": platform["origin"]}, size=tuple(platform["size"]),
    )
    if inventory_counts(await actor.request("observe")) != fixture["player_state"]["inventory"]:
        await setup.clean_inventory(admin, actor)
        for name, amount in fixture["player_state"]["inventory"].items():
            await setup.gift(admin, actor, name, amount)
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    await setup.command(admin, "time", fixture["time_of_day"])
    await setup.command(admin, "sudo", actor.name, "health", fixture["player_state"]["health"])
    opening = await setup.ready_observation(actor)
    verify_player(fixture, opening)
    return {"fixture": fixture, "construction": construction, "opening": opening}
