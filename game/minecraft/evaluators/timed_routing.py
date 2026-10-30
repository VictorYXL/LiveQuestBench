"""Original native cart identities and physical delivery, never collection alone."""
from io import BytesIO
import math
from pathlib import Path
import zlib

import nbtlib


def entities(world):
    rows = []
    for path in (world / "entities").glob("*.mca"):
        raw = path.read_bytes()
        for offset in range(1024):
            sector = int.from_bytes(raw[4 * offset:4 * offset + 3], "big")
            if not sector:
                continue
            start = sector * 4096
            length = int.from_bytes(raw[start:start + 4], "big")
            if raw[start + 4] != 2:
                raise ValueError("Unsupported native entity compression")
            chunk = nbtlib.File.parse(BytesIO(zlib.decompress(raw[start + 5:start + 4 + length])))
            rows.extend(chunk["Entities"])
    return rows


def score(before, after, player):
    checks = {}
    first, last = entities(before), entities(after)
    for name in ("east", "west"):
        originals = [row for row in first if f"original_cart_{name}" in row.get("Tags", [])]
        if len(originals) != 1:
            raise ValueError("Missing or duplicate original identity")
        found = [row for row in last if list(row["UUID"]) == list(originals[0]["UUID"])]
        if not found:
            checks[name] = {"original_alive": False, "correct_dock": False}
            continue
        x, y, z = map(float, found[0]["Pos"])
        speed = math.sqrt(sum(float(value)**2 for value in found[0]["Motion"]))
        cell = math.floor(x)
        correct = (12 <= cell <= 22 if name == "east" else -22 <= cell <= -12) and 71.8 <= y <= 73 and abs(z-.5) < 1 and speed < .02
        checks[name] = {"original_alive": True, "position": [x,y,z], "speed": speed, "correct_dock": correct}
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    cargo = {str(item.get("tag", {}).get("livequest_cargo", "")) for item in native["Inventory"]}
    x, y, z = map(float, native["Pos"])
    returned = float(native["Health"]) > 0 and math.hypot(x-.5,z+10.5) <= 3 and abs(y-72) < .5
    return {"carts": checks, "cargo": sorted(cargo-{""}), "living_return": returned,
            "native_objective_success": all(row["correct_dock"] for row in checks.values()) and returned
            and {"east_consignment","west_consignment"} <= cargo}


def verify_initial(world: Path):
    rows = entities(world)
    for name in ("east", "west"):
        original = [row for row in rows if f"original_cart_{name}" in row.get("Tags", [])]
        if len(original) != 1:
            raise ValueError("Expected exactly one original cart per consignment")
        if not any(str(item.get("tag", {}).get("livequest_cargo", "")) == name + "_consignment"
                   for item in original[0].get("Items", [])):
            raise ValueError("Original cart lacks its native consignment")


def evaluate_routing(before, after, player):
    verify_initial(before)
    result = score(before, after, player)
    return {"success": bool(result["native_objective_success"]), "checks": result}
