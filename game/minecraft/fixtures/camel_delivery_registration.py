"""Private instance admission for the explicitly versioned native flush courier."""
import hashlib
import json
from pathlib import Path
import secrets

import nbtlib

from game.minecraft.evaluators.camel_delivery import original_camel, verify_initial_materials
from game.minecraft.evaluators.cargo import cargo_count
from game.minecraft.evaluators.world import read_block_entity, read_blocks
from game.minecraft.fixtures import camel_delivery_flush_v4 as condition
from game.minecraft.fixtures.camel_delivery import SOURCE, CARGO
from game.minecraft.runtime.session import validate_world


MANIFEST = "native-camel-variants.json"
SPEEDS = (.05, .20)


def verify_initial(world, player_uuid=None):
    world = Path(world)
    verify_initial_materials(world)
    _, camel = original_camel(world)
    attributes = {str(row["Name"]): float(row["Base"]) for row in camel["Attributes"]}
    speed = attributes.get("minecraft:generic.movement_speed")
    if (speed not in SPEEDS or attributes.get("minecraft:horse.jump_strength") != .42
            or list(map(float, camel["Pos"])) != [-40.5, 72.0, 1.5]
            or float(camel["Health"]) != 32
            or any(float(value) != 0 for value in camel["Motion"])):
        raise ValueError("Expected the original healthy courier at the reviewed depot start")
    depot = read_block_entity(world, SOURCE)
    if str(depot["id"]) != "minecraft:furnace":
        raise ValueError("Original native cargo depot is missing")
    if len(depot.get("Items", [])) != 2 or any(
        cargo_count(depot.get("Items", []), {"id": identifier, "item": "minecraft:clay_ball"}) != 1
        for identifier in CARGO
    ):
        raise ValueError("Both original parcels must start in the depot")
    for point in condition.DESTINATIONS:
        destination = read_block_entity(world, point)
        above = (point[0], point[1] + 1, point[2])
        if (str(destination["id"]) != "minecraft:furnace" or destination.get("Items", [])
                or read_blocks(world, point, point, "minecraft:overworld")[point] != "minecraft:furnace"
                or read_blocks(world, above, above, "minecraft:overworld")[above] != "minecraft:air"):
            raise ValueError("Both empty destination furnaces must have exposed flush tops")
    if player_uuid is not None:
        player = nbtlib.load(world / "playerdata" / f"{player_uuid}.dat")
        if (list(map(float, player["Pos"])) != [-42.5, 72.0, 1.5]
                or player.get("Inventory") or player.get("RootVehicle")):
            raise ValueError("The task must not start from the simplified mounted-A diagnostic")
    return speed


def select_world(root):
    root = Path(root).resolve()
    manifest_path = root / MANIFEST
    data = json.loads(manifest_path.read_text())
    if (data.get("schema") != "livequest-native-camel-variants/4"
            or data.get("condition") != condition.VERSION
            or data.get("selection") != "uniform_once_before_episode"
            or len(data.get("worlds", [])) != 2):
        raise ValueError("Explicit flush-v4 two-instance native distribution required")
    worlds = []
    for index, row in enumerate(data["worlds"]):
        if row.get("path") != f"instance_{index}" or row.get("movement_speed") != SPEEDS[index]:
            raise ValueError("Both reviewed native response instances are required")
        world = root / row["path"]
        validate_world(world)
        files = {str(path.relative_to(world)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(world.rglob("*")) if path.is_file()}
        recipe = hashlib.sha256(json.dumps(
            condition.commands(index), separators=(",", ":"), ensure_ascii=True,
        ).encode()).hexdigest()
        if files != row.get("files") or row.get("recipe_sha256") != recipe:
            raise ValueError("Frozen native courier asset or versioned recipe changed")
        if verify_initial(world) != SPEEDS[index]:
            raise ValueError("Stored native response disagrees with its private instance")
        worlds.append(world)
    index = secrets.randbelow(2)
    return worlds[index], {
        "condition": condition.VERSION,
        "selection": data["selection"], "instance_index": index,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "selected_fixture_sha256": hashlib.sha256(json.dumps(
            data["worlds"][index]["files"], sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "recipe_sha256": data["worlds"][index]["recipe_sha256"],
        "resampling_after_outcome": False,
        "private_authoring_provenance_not_agent_observation": True,
    }
