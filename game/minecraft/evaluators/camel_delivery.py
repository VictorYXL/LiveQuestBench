"""Read-only native cargo and original-camel endpoint checks; no action restrictions."""
import gzip
from io import BytesIO
import math
from pathlib import Path
import zlib

import nbtlib

from game.minecraft.evaluators.cargo import cargo_count
from game.minecraft.evaluators.world import read_block_entity, read_blocks
from game.minecraft.fixtures.camel_delivery import CARGO, DESTINATIONS, SOURCE, on_pad


def verify_initial_materials(world):
    allowed = {"minecraft:" + name for name in (
        "air", "water", "bedrock", "yellow_concrete", "furnace", "gold_block", "emerald_block",
    )}
    blocks = read_blocks(Path(world), (-44, 65, -8), (40, 85, 33), "minecraft:overworld")
    unexpected = {block for block in blocks.values() if block not in allowed}
    if unexpected:
        raise ValueError(f"Unintended initial arena materials: {sorted(unexpected)}")


def entities(world):
    result = {}

    def add(entity):
        if "UUID" in entity:
            identity = tuple(map(int, entity["UUID"]))
            if identity in result:
                raise ValueError("Duplicate native entity identity")
            result[identity] = entity
        for passenger in entity.get("Passengers", []):
            add(passenger)

    for path in sorted((Path(world) / "entities").glob("r.*.*.mca")):
        raw = path.read_bytes()
        if not raw:
            continue
        if len(raw) < 8192:
            raise ValueError("Incomplete native entity region")
        for index in range(1024):
            location = raw[index * 4:index * 4 + 4]
            offset = int.from_bytes(location[:3], "big") * 4096
            if not offset:
                continue
            length = int.from_bytes(raw[offset:offset + 4], "big")
            if offset < 8192 or length < 1 or offset + 4 + length > len(raw):
                raise ValueError("Invalid native entity chunk")
            codec = raw[offset + 4]
            payload = raw[offset + 5:offset + 4 + length]
            if codec not in (1, 2, 3):
                raise ValueError("Unsupported native entity chunk compression")
            data = gzip.decompress(payload) if codec == 1 else zlib.decompress(payload) if codec == 2 else payload
            chunk = nbtlib.File.parse(BytesIO(data))
            if int(chunk["DataVersion"]) != 3700:
                raise ValueError("Native entity evidence requires Minecraft 1.20.4")
            for entity in chunk["Entities"]:
                add(entity)
    for path in sorted((Path(world) / "playerdata").glob("*.dat")):
        player = nbtlib.load(path)
        vehicle = player.get("RootVehicle", {}).get("Entity")
        if vehicle is not None:
            add(vehicle)
    return result


def original_camel(world):
    rows = [(identity, entity) for identity, entity in entities(world).items()
            if str(entity.get("id")) == "minecraft:camel"
            and "lq_camel_response" in list(map(str, entity.get("Tags", [])))]
    if len(rows) != 1:
        raise ValueError("Expected exactly one original courier camel")
    return rows[0]


def endpoint_checks(initial_identity, camel, player, deliveries):
    identity_matches = camel is not None and tuple(map(int, camel["UUID"])) == initial_identity
    position = dict(zip(("x", "y", "z"), map(float, camel["Pos"]))) if camel is not None else None
    settled = (camel is not None and bool(camel["OnGround"])
               and all(math.isfinite(float(v)) for v in camel["Motion"])
               and math.sqrt(sum(float(v) ** 2 for v in camel["Motion"])) <= .1)
    checks = [
        {"kind": "original_camel", "passed": identity_matches},
        {"kind": "camel_alive", "passed": camel is not None and float(camel["Health"]) > 0},
        {"kind": "camel_settled_on_pad_b", "passed": bool(settled and on_pad(position, 1)),
         "position": position},
        {"kind": "player_alive", "passed": float(player["Health"]) > 0},
    ]
    checks.extend({"kind": "original_cargo_delivered", "id": identifier,
                   "count": count, "passed": count == 1}
                  for identifier, count in zip(CARGO, deliveries))
    return {"success": all(row["passed"] for row in checks), "checks": checks}


def evaluate(before, after, player_uuid, *, destinations=DESTINATIONS):
    before, after = Path(before), Path(after)
    verify_initial_materials(before)
    identity, _ = original_camel(before)
    depot = read_block_entity(before, SOURCE)
    if str(depot["id"]) != "minecraft:furnace":
        raise ValueError("Original cargo depot is missing")
    deliveries = []
    if len(destinations) != len(CARGO):
        raise ValueError("Each original parcel requires one destination")
    for identifier, point in zip(CARGO, destinations):
        row = {"id": identifier, "item": "minecraft:clay_ball"}
        if cargo_count(depot.get("Items", []), row) != 1:
            raise ValueError("Original native cargo is missing or duplicated")
        initial_destination = read_block_entity(before, point)
        if (str(initial_destination["id"]) != "minecraft:furnace"
                or initial_destination.get("Items", [])):
            raise ValueError("Delivery furnace must initially be empty")
        if read_blocks(after, point, point, "minecraft:overworld")[point] != "minecraft:furnace":
            deliveries.append(0)
            continue
        destination = read_block_entity(after, point)
        inputs = [item for item in destination.get("Items", []) if int(item["Slot"]) == 0]
        deliveries.append(cargo_count(inputs, row))
    camel = entities(after).get(identity)
    player = nbtlib.load(after / "playerdata" / f"{player_uuid}.dat")
    result = endpoint_checks(identity, camel, player, deliveries)
    result["semantics"] = (
        "Two original tagged parcels in matching native furnace inputs and the same living "
        "camel grounded and stopped on pad B; living player. All legal actions and recovery allowed."
    )
    return result
