"""Validate explicit native world and actor initialization, never implicit presets."""

from copy import deepcopy
import asyncio
import math
from pathlib import Path
import re


MAX_VOXELS = 8192
MAX_ROUTE_VOXELS = 10240


class FixtureMismatch(RuntimeError):
    """Native readback has not established the declared player state."""


def cuboid(value: object, label: str) -> tuple[list, list]:
    region = fields(value, {"origin", "size"}, label)
    origin = vector(region["origin"], label + ".origin", integer=True)
    size = vector(region["size"], label + ".size", integer=True)
    if any(n < 1 for n in size) or math.prod(size) > MAX_VOXELS:
        raise ValueError(f"{label} must have positive dimensions and at most {MAX_VOXELS} voxels")
    return origin, size


def solid_voxels(fixture: dict) -> set[tuple[int, int, int]]:
    if "native_site" in fixture:
        return set()
    platform = fixture["platform"]
    regions = [{"origin": platform["origin"], "size": [*platform["size"], 1]}, *fixture.get("blocks", [])]
    voxels = set()
    limit = MAX_ROUTE_VOXELS if fixture.get("route_evidence") is True else MAX_VOXELS
    for region in regions:
        origin, size = cuboid(region, "block region")
        voxels.update((origin[0] + x, origin[1] + y, origin[2] + z)
                      for x in range(size[0]) for y in range(size[1]) for z in range(size[2]))
        if len(voxels) > limit:
            raise ValueError(f"Fixture exceeds {limit} authored voxels")
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
    required = {"world_path", "world_seed", "time_of_day", "day_length", "calendar", "player_state"}
    optional = {"blocks", "stations", "supplies", "recipe_groups", "recipes", "encounters",
                "motion_evidence", "glide_evidence", "platform", "native_site", "merchant",
                "sword_skill_points", "companion", "contract", "respawn_at_start", "route_evidence"}
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"Veloren fixture requires exactly {sorted(required)} plus optional {sorted(optional)}")
    fixture = value
    for flag in ("motion_evidence", "glide_evidence", "respawn_at_start", "route_evidence"):
        if flag in fixture and type(fixture[flag]) is not bool:
            raise ValueError(f"{flag} must be boolean")
    if "sword_skill_points" in fixture and (
        type(fixture["sword_skill_points"]) is not int or not 1 <= fixture["sword_skill_points"] <= 16
    ):
        raise ValueError("sword_skill_points must be an integer in [1, 16]")
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
    player = fields(fixture["player_state"], {"position", "look", "health", "inventory", "equipment"}, "player_state")
    point = vector(player["position"], "player_state.position")
    if ("platform" in fixture) == ("native_site" in fixture):
        raise ValueError("Declare exactly one authored platform or existing native_site")
    for key in ("blocks", "stations", "supplies", "recipe_groups"):
        if key in fixture and not isinstance(fixture[key], list):
            raise ValueError(f"{key} must be a list")
    if "native_site" in fixture:
        site = fixture["native_site"]
        if not isinstance(site, str) or not site.strip() or len(site) > 128:
            raise ValueError("native_site must name an existing native settlement")
        if {"blocks", "stations", "supplies", "encounters"} & fixture.keys():
            raise ValueError("Natural settlement fixtures do not author terrain, supplies or encounters")
        occupied = set()
    else:
        platform = fields(fixture["platform"], {"origin", "size", "block"}, "platform")
        origin = vector(platform["origin"], "platform.origin", integer=True)
        size = platform["size"]
        if (not isinstance(size, list) or len(size) != 2
                or any(type(n) is not int or not 2 <= n <= 1024 for n in size)
                or math.prod(size) > MAX_VOXELS):
            raise ValueError(f"platform.size must be in [2, 1024] with at most {MAX_VOXELS} cells")
        if platform["block"] != "Rock":
            raise ValueError("The current native fixture author supports Rock platforms only")
        if not all(origin[i] < point[i] < origin[i] + size[i] for i in range(2)):
            raise ValueError("Player must start on the declared platform")
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
    encounters = fixture.get("encounters", [])
    if not isinstance(encounters, list) or len(encounters) > 4:
        raise ValueError("encounters must contain at most four designated native enemies")
    if "contract" in fixture:
        if "platform" not in fixture or encounters or "merchant" in fixture or "companion" in fixture:
            raise ValueError("Native Slay contracts require a separate authored scene without injected encounters")
        contract = fixture["contract"]
        if not isinstance(contract, dict):
            raise ValueError("contract must be a mapping")
        fields({key: value for key, value in contract.items() if key != "giver_funding"},
               {"source_site", "giver_position", "target_position"}, "contract")
        funding = contract.get("giver_funding", 1000)
        if type(funding) is not int or not 1000 <= funding <= 10000:
            raise ValueError("contract.giver_funding must be an integer in [1000, 10000]")
        if (not isinstance(contract["source_site"], str) or not contract["source_site"].strip()
                or len(contract["source_site"]) > 128):
            raise ValueError("Contract source_site must name an existing native settlement")
        for key in ("giver_position", "target_position"):
            spawn = vector(contract[key], f"contract.{key}")
            require_standing_point(spawn, occupied, f"Contract {key}")
            lower, upper = (2, 5) if key == "giver_position" else (16, 24)
            if not lower <= math.dist(spawn, point) <= upper:
                raise ValueError(f"Contract {key} must be {lower}-{upper} metres from the player")
    roles, positions = set(), set()
    for encounter in encounters:
        fields({key: value for key, value in encounter.items() if key != "initial_health"},
               {"role", "asset", "position"}, "encounter")
        if "initial_health" in encounter and (
            type(encounter["initial_health"]) not in (int, float)
            or not math.isfinite(encounter["initial_health"])
            or not 0 < encounter["initial_health"] <= 100
        ):
            raise ValueError("Encounter initial_health must be finite and in (0, 100]")
        role, asset = encounter["role"], encounter["asset"]
        if (not isinstance(role, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", role)
                or role in roles or asset not in (
                    "common.entity.benchmark.male_green_legoom", "common.entity.benchmark.male_wolf",
                    "common.entity.dungeon.haniwa.archer",
                )):
            raise ValueError("Encounter requires a unique role and a supported exact-body enemy asset")
        spawn = vector(encounter["position"], "encounter.position")
        require_standing_point(spawn, occupied, "Encounter")
        if not 10 <= math.dist(spawn, point) <= 96 or tuple(spawn) in positions:
            raise ValueError("Enemies must have distinct spawn points 10-96 metres from the player")
        roles.add(role)
        positions.add(tuple(spawn))
    if "companion" in fixture:
        companion = fields(fixture["companion"], {"species", "position"}, "companion")
        if companion["species"] != "sheep" or not encounters:
            raise ValueError("Companion fixtures require a native sheep and a designated encounter")
        spawn = vector(companion["position"], "companion.position")
        require_standing_point(spawn, occupied, "Companion")
        if not 2 <= math.dist(spawn, point) <= 4:
            raise ValueError("Companion must start 2-4 metres from its owner")
    for supply in fixture.get("supplies", []):
        if not isinstance(supply, dict):
            raise ValueError("Supply must be a mapping")
        fields({key: value for key, value in supply.items() if key != "pre_age_seconds"},
               {"position", "item", "amount"}, "supply")
        age = supply.get("pre_age_seconds", 0)
        if type(age) is not int or not 0 <= age <= 240:
            raise ValueError("Supply pre_age_seconds must be an integer in [0, 240]")
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
    if "merchant" in fixture:
        required_merchant = {
            "position", "stock_item", "stock_amount", "payment_item", "payment_reserve", "coin_reserve",
        }
        merchant = fields(fixture["merchant"], required_merchant, "merchant")
        spawn = vector(merchant["position"], "merchant.position")
        if "platform" in fixture:
            require_standing_point(spawn, occupied, "Merchant")
        if not 2 <= math.dist(spawn, point) <= 6:
            raise ValueError("Merchant placement must be 2-6 metres from the player")
        for key in ("stock_item", "payment_item"):
            if not isinstance(merchant[key], str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", merchant[key]):
                raise ValueError("Merchant items must have native item IDs")
        for key in ("stock_amount", "payment_reserve", "coin_reserve"):
            if type(merchant[key]) is not int or not 1 <= merchant[key] <= 99:
                raise ValueError("Merchant stock and reserves must be integers in [1, 99]")
        if inventory.get(merchant["payment_item"], 0) <= merchant["payment_reserve"]:
            raise ValueError("Merchant purchase requires spendable initial goods beyond the reserve")
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
        "thick_leather": "common.items.crafting_ing.leather.thick_leather",
        "leather_strips": "common.items.crafting_ing.leather.leather_strips",
        "leather_chest": "common.items.armor.hide.leather.chest",
        "leather_feet": "common.items.armor.hide.leather.foot",
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
    if "native_site" in fixture and (
        observation["current_site"]["location_name"] != fixture["native_site"]
        or observation["current_site"]["loaded_chunk"] is not True
    ):
        raise FixtureMismatch("Initial native settlement differs from the fixture")
    if math.dist(observation["position"], player["position"]) > .2:
        raise FixtureMismatch(f"Initial player position {observation['position']} differs from {player['position']}")
    if math.dist(observation["look"], player["look"]) > .01:
        raise FixtureMismatch(f"Initial player look {observation['look']} differs from {player['look']}")
    if (abs(observation["survival"]["health"]["current"] - player["health"]) > .01
            or observation["survival"]["buffs"] or observation["on_ground"] is not True
            or math.sqrt(sum(v * v for v in observation["velocity"])) >= .1):
        raise FixtureMismatch(
            f"Initial health {observation['survival']['health']['current']} (expected {player['health']}), "
            f"buffs {observation['survival']['buffs']}, on_ground {observation['on_ground']}, "
            f"velocity {observation['velocity']} differ from the fixture"
        )
    equipped = {slot: item_id(item) for slot, item in observation["inventory"]["equipment"].items() if item is not None}
    if inventory_counts(observation) != player["inventory"] or equipped != player["equipment"]:
        raise FixtureMismatch("Initial inventory or equipment differs from the fixture")
    if fixture.get("recipes"):
        from game.veloren.evaluators.endpoints import known_recipes
        known = known_recipes(observation, required=list(fixture["recipes"]))
        if any((recipe in known) != expected for recipe, expected in fixture["recipes"].items()):
            raise FixtureMismatch("Initial recipe knowledge differs from the fixture")
    if "sword_skill_points" in fixture:
        groups = [row for row in observation["skill_tree"]["groups"] if row["group"] == {"Weapon": "Sword"}]
        if (len(groups) != 1 or groups[0]["accessible"] is not True
                or groups[0]["available_points"] != fixture["sword_skill_points"]
                or groups[0]["earned_points"] != fixture["sword_skill_points"]
                or any(row["learned_level"] not in (None, 0) for row in groups[0]["skills"])):
            raise FixtureMismatch("Initial Sword points, accessibility or unlearned skills differ from the fixture")


async def wait_player(actor, fixture: dict, observation: dict, *, timeout: float = 30) -> dict:
    """Wait for setup effects to reach the client without mutating or relaxing the fixture."""
    mismatch = "player readback unavailable"
    deadline = asyncio.timeout(timeout)
    try:
        async with deadline:
            while True:
                observation = await recipe_observation(actor, fixture, observation)
                try:
                    verify_player(fixture, observation)
                except FixtureMismatch as error:
                    mismatch = str(error)
                else:
                    return observation
                await asyncio.sleep(.1)
                observation = await actor.request("observe", origin="private-validation")
    except TimeoutError as error:
        if not deadline.expired():
            raise
        raise FixtureMismatch(f"Player setup did not synchronize within {timeout}s: {mismatch}") from error


async def initialize_encounter(admin, actor, spec: dict, position: list) -> dict:
    from scripts.rpg_benchmark import setup
    from scripts.rpg_benchmark.combat_support import native_binding

    expected = (
        {"BipedSmall": {"species": "GreenLegoom", "body_type": "Male"}}
        if spec["asset"].endswith("male_green_legoom")
        else {"QuadrupedMedium": {"species": "Wolf", "body_type": "Male"}}
    )
    await setup.goto(admin, admin, position)
    player_observation = await actor.request("observe")
    distant = math.dist(player_observation["position"], position) > 24
    observer = admin if distant else actor
    before = await admin.request("observe") if distant else player_observation
    existing = {row["uid"] for row in before["nearby_entities"]}
    receipt = await setup.command(admin, "make_npc", spec["asset"], 1)

    def candidates(row):
        # Teleported administrators can reach this client's visibility window after the spawn command.
        return [entry for entry in row["nearby_entities"]
                if entry["uid"] not in existing and (
                    entry.get("body_identity", {}).get("BipedSmall", {}).get("species") == "Haniwa"
                    if spec["asset"] == "common.entity.dungeon.haniwa.archer"
                    else entry.get("body_identity") == expected)
                and entry.get("health")]

    after = await setup.wait_observation(
        observer, lambda row: len(candidates(row)) == 1, "unique new exact-body native encounter UID",
    )
    target = candidates(after)[0]
    if spec["asset"] == "common.entity.dungeon.haniwa.archer":
        expected = target["body_identity"]
    if "initial_health" in spec:
        await setup.command(admin, "sudo", f"uid@{target['uid']}", "health", spec["initial_health"])
        after = await setup.wait_observation(
            observer, lambda row: any(
                entry["uid"] == target["uid"] and entry["health"]["current"] == spec["initial_health"]
                for entry in row["nearby_entities"]), "declared finite initial enemy health",
        )
        target = next(entry for entry in after["nearby_entities"] if entry["uid"] == target["uid"])
    binding = await native_binding(actor, target["uid"])
    if (binding["body"] != expected or binding["alignment"] != "Enemy"
            or binding["dead"] or binding["health"] <= 0
            or target["health"]["dead"] or target["health"]["current"] <= 0):
        raise RuntimeError("Encounter target lacks the declared living native body and Enemy alignment")
    return {"role": spec["role"], "asset": spec["asset"], "public": None if distant else target, "binding": binding,
            "setup_observation": target, "setup_observer": "administrator" if distant else "player",
            "spawn_receipt": receipt,
            "stock_loadout": "Unchanged native asset loadout; exact-body benchmark derivative.",
            "native_loadout_observed": True}


def verify_encounter_opening(targets: list[dict], observation: dict, rows: list[dict]) -> None:
    latest = next((row for row in reversed(rows) if row["event"] == "combat_entity_bindings"), None)
    if latest is None:
        raise RuntimeError("Designated targets lack native opening bindings")
    current = {entry["uid"]: entry for entry in observation["nearby_entities"]}
    for target in targets:
        expected = target["binding"]
        bindings = [entry for entry in latest["data"]["bindings"] if entry["uid"] == expected["uid"]]
        if (len(bindings) != 1 or bindings[0]["server_entity"] != expected["server_entity"]
                or bindings[0]["body"] != expected["body"]
                or bindings[0]["alignment"] != expected["alignment"]
                or bindings[0]["dead"] or bindings[0]["health"] <= 0
                or bindings[0]["health"] != expected["health"]):
            raise RuntimeError("Designated target unavailable, replaced, dead or injured before measured play")
        if target["public"] is not None:
            entry = current.get(expected["uid"])
            if (entry is None or entry["health"]["dead"] or entry["health"]["current"] != expected["health"]):
                raise RuntimeError("Nearby designated target unavailable, dead or injured before measured play")


async def observe_remote_supplies(admin, supplies: list[dict]) -> None:
    """Capture setup-only readback without moving the player or expanding public observations."""
    from scripts.rpg_benchmark import setup

    for supply in supplies:
        if supply.get("player_target") is not None:
            continue
        await setup.goto(admin, admin, supply["entity"]["position"])
        observed = await admin.request("observe", origin="private-validation")
        entity = next((row for row in observed["nearby_entities"] if row["uid"] == supply["uid"]), None)
        if (entity is None or item_id(entity.get("pickup") or {}) != supply["item"]
                or entity["pickup"]["amount"] != supply["amount"]):
            raise RuntimeError("Distant expiring supply lacks identity-matched private native readback")
        supply["private_opening"] = {
            "entity": entity, "clock": observed["survival"]["buff_clock"]["now"],
            "observer": "administrator", "scope": "Read immediately before administrator retirement; "
            "not an atomic server snapshot or an Agent observation.",
        }


def verify_aged_supplies(initialized: dict, observation: dict) -> None:
    if not initialized["supplies"]:
        return
    current = {row["uid"]: row for row in observation["nearby_entities"]}
    clock = observation["survival"]["buff_clock"]["now"]
    for supply in initialized["supplies"]:
        private = supply.get("private_opening")
        if supply.get("player_target") is not None:
            entity = current.get(supply["uid"])
            identity_matches = entity is not None and entity["control_target"] == supply["player_target"]
        else:
            entity = private["entity"] if private is not None else None
            identity_matches = (
                entity is not None and entity["uid"] == supply["uid"]
                and private["observer"] == "administrator"
                and private["clock"] <= clock
            )
        if (not identity_matches
                or item_id(entity["pickup"]) != supply["item"] or entity["pickup"]["amount"] != supply["amount"]
                or supply["expiry_game_time_estimate"] - clock < 15):
            raise RuntimeError("Declared expiring supply lacks a live, identity-matched opening with >=15 seconds")
        visible = current.get(supply["uid"])
        if visible is not None and (
            item_id(visible.get("pickup") or {}) != supply["item"]
            or visible["pickup"]["amount"] != supply["amount"]
        ):
            raise RuntimeError("Declared expiring supply differs from current player readback")


async def initialize_companion(admin, actor, fixture: dict) -> dict:
    from scripts.rpg_benchmark import setup
    from scripts.rpg_benchmark.combat_support import native_binding

    before = await actor.request("observe")
    existing = {row["uid"] for row in before["nearby_entities"]}
    receipt = await setup.command(admin, "sudo", actor.name, "spawn", "pet", "sheep", 1, "true")
    spawned = await setup.wait_observation(actor, lambda row: len([
        entry for entry in row["nearby_entities"]
        if entry["uid"] not in existing and entry["companion"]["owned_by_actor"]
    ]) == 1, "one newly owned native sheep")
    pet = next(row for row in spawned["nearby_entities"]
               if row["uid"] not in existing and row["companion"]["owned_by_actor"])
    target = fixture["companion"]["position"]
    await setup.command(admin, "sudo", f"uid@{pet['uid']}", "goto", *target)
    settled = await setup.wait_observation(actor, lambda row: any(
        entry["uid"] == pet["uid"] and math.dist(entry["position"], target) < 2
        and abs(entry["position"][2] - target[2]) < .1 and entry["same_native_group"] is True
        for entry in row["nearby_entities"]
    ), "owned native sheep settled at its declared start")
    pet = next(row for row in settled["nearby_entities"] if row["uid"] == pet["uid"])
    binding = await native_binding(actor, pet["uid"])
    if (pet["body_identity"].get("QuadrupedSmall", {}).get("species") != "Sheep"
            or binding["alignment"] != {"Owned": before["self_identity"]["uid"]}
            or binding["health"] != binding["maximum_health"] or binding["health"] <= 0 or binding["dead"]):
        raise RuntimeError("Companion lacks native sheep identity, ownership or full ordinary health")
    return {"binding": binding, "player_target": pet["control_target"], "spawn_receipt": receipt,
            "initial_public": pet, "native_ai": True, "tethered": False}


async def initialize_equipment(admin, actor, equipment: dict[str, str]) -> None:
    from scripts.rpg_benchmark import setup

    observation = await actor.request("observe")
    current = {slot: item_id(item) for slot, item in observation["inventory"]["equipment"].items()
               if item is not None}
    if current.keys() - equipment.keys():
        raise FixtureMismatch("Removing undeclared starting equipment is not supported")
    for slot, name in equipment.items():
        if current.get(slot) == name:
            continue
        observation = await setup.gift(admin, actor, name, 1)
        stack = next(row for row in observation["inventory"]["items"] if item_id(row["item"]) == name)
        await setup.action(actor, "equip", equip_slot=slot, **setup.slot(stack))
        await setup.wait_observation(
            actor,
            lambda row: row["inventory"]["equipment"].get(slot) is not None
            and item_id(row["inventory"]["equipment"][slot]) == name,
            f"declared starting equipment in {slot}",
        )


async def initialize_fixture(admin, actor, fixture: dict, *, shared_world: bool = False) -> dict:
    """Author absolute geometry, set player/time fields and verify native readback."""
    from scripts.rpg_benchmark import setup

    fixture = validate_fixture(fixture)
    await setup.ready_observation(actor)
    if shared_world:
        construction = {"constructed": False, "shared_world": True}
    elif "native_site" in fixture:
        construction = {"constructed": False, "native_site": fixture["native_site"],
                        "ambient_npcs_removed": False, "safezone_created": False}
    else:
        platform = fixture["platform"]
        construction = await setup.site(
            admin, actor, "flat", {"flat_origin": platform["origin"]}, size=tuple(platform["size"]),
        )
    base = solid_voxels({**fixture, "blocks": []})
    additional = set() if shared_world else solid_voxels(fixture) - base
    blocks = await setup.author_voxels(admin, [list(point) for point in sorted(additional)]) if additional else []
    stations = []
    for station in (() if shared_world else fixture.get("stations", [])):
        stations.append(await setup.station(admin, station["position"], station["sprite"], "flat"))
    for group in fixture.get("recipe_groups", []):
        await setup.learn(admin, actor, group)
    await initialize_equipment(admin, actor, fixture["player_state"]["equipment"])
    if inventory_counts(await actor.request("observe")) != fixture["player_state"]["inventory"]:
        await setup.clean_inventory(admin, actor)
        for name, amount in fixture["player_state"]["inventory"].items():
            await setup.gift(admin, actor, name, amount)
    if "sword_skill_points" in fixture:
        identity = (await actor.request("observe"))["self_identity"]["uid"]
        await setup.command(admin, "skill_point", "general", 1, f"uid@{identity}")
        await setup.wait_observation(actor, lambda row: any(
            {"UnlockGroup": {"Weapon": "Sword"}} in group["unlockable_now"]
            for group in row["skill_tree"]["groups"]
        ), "lawful Sword group unlock")
        await setup.action(actor, "unlock_skill", skill={"UnlockGroup": {"Weapon": "Sword"}})
        await setup.command(admin, "skill_point", "sword", fixture["sword_skill_points"], f"uid@{identity}")
        await setup.wait_observation(actor, lambda row: any(
            group["group"] == {"Weapon": "Sword"} and group["accessible"]
            and group["available_points"] == fixture["sword_skill_points"]
            for group in row["skill_tree"]["groups"]
        ), "declared unspent native Sword points")
    supplies = []
    for supply in (() if shared_world else fixture.get("supplies", [])):
        if inventory_counts(await admin.request("observe")).get(supply["item"], 0):
            origin = (await setup.ready_observation(admin))["position"]
            await setup.goto(admin, admin, [value + 100 for value in origin], settle=False)
            while inventory_counts(observed := await admin.request("observe")).get(supply["item"], 0):
                stack = next(row for row in observed["inventory"]["items"]
                             if item_id(row["item"]) == supply["item"])
                await setup.action(admin, "drop", **setup.slot(stack))
                if inventory_counts(await admin.request("observe")).get(supply["item"], 0) >= (
                    inventory_counts(observed)[supply["item"]]
                ):
                    raise RuntimeError("Administrator supply cleanup did not remove the native stack")
            await setup.goto(admin, admin, origin)
        supplies.append(await setup.drop_supply(
            admin, supply["position"], supply["item"], supply["amount"], "flat",
        ))
        if supply.get("pre_age_seconds"):
            await asyncio.sleep(supply["pre_age_seconds"])
    merchant = None
    if "merchant" in fixture and not shared_world:
        from game.veloren.settlement import initialize_merchant
        merchant = await initialize_merchant(admin, actor, fixture)
    contract = None
    if "native_site" in fixture:
        point = fixture["player_state"]["position"]
        await setup.goto(admin, admin, [point[0] + 12, point[1], point[2]], settle=False)
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    companion = None
    if "companion" in fixture and not shared_world:
        companion = await initialize_companion(admin, actor, fixture)
        await setup.goto(admin, actor, fixture["player_state"]["position"])
    await setup.command(admin, "time", fixture["time_of_day"])
    await setup.command(admin, "sudo", actor.name, "health", fixture["player_state"]["health"])
    opening = await wait_player(actor, fixture, await setup.ready_observation(actor))
    waypoint = None
    if fixture.get("respawn_at_start", False):
        waypoint = await setup.command(admin, "sudo", actor.name, "set_waypoint")
    if not shared_world and supplies:
        current = {row["uid"]: row for row in opening["nearby_entities"]}
        for supply in supplies:
            entity = current.get(supply["uid"])
            if entity is not None and (
                item_id(entity.get("pickup") or {}) != supply["item"]
                or entity["pickup"]["amount"] != supply["amount"]
            ):
                raise RuntimeError("Expiring supply cannot be bound in the player's native client")
            supply["player_target"] = entity["control_target"] if entity is not None else None
    if merchant is not None:
        from game.veloren.settlement import bind_merchant
        merchant = bind_merchant(opening, merchant)
    if "contract" in fixture and not shared_world:
        from game.veloren.contracts import initialize_contract
        contract = await initialize_contract(admin, actor, fixture)
    encounters = []
    source = None
    if not shared_world and (fixture.get("encounters") or contract is not None):
        from scripts.rpg_benchmark.combat_support import native_binding
        if contract is not None:
            encounters.append({
                "role": "contract_target", "asset": "existing native RTSim Ogre",
                "binding": contract["target"]["binding"], "public": contract["target"]["public"],
            })
        for enemy in fixture.get("encounters", []):
            target = await initialize_encounter(admin, actor, enemy, enemy["position"])
            encounters.append(target)
        opening = await actor.request("observe", origin="private-validation")
        verify_player(fixture, opening)
        source = await native_binding(actor, opening["self_identity"]["uid"])
        if source["health"] <= 0 or source["dead"]:
            raise RuntimeError("Encounter player is not alive at initialization")
    return {"fixture": fixture, "construction": construction, "blocks": blocks,
            "stations": stations, "supplies": supplies, "opening": opening,
            "encounters": encounters, "source_binding": source, "merchant": merchant,
            "companion": companion, "contract": contract, "initial_waypoint_receipt": waypoint}
