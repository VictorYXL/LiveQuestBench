"""Model-free legal preset-route counterpolicy, with offline original-identity scoring."""
import argparse
import asyncio
from io import BytesIO
import json
import math
from pathlib import Path
import zlib

import nbtlib

from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState


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
    for name in ("east", "west"):
        original = [e for e in entities(before) if f"original_cart_{name}" in e.get("Tags", [])]
        if len(original) != 1:
            raise ValueError("Missing or duplicate original cart")
        found = [e for e in entities(after) if list(e["UUID"]) == list(original[0]["UUID"])]
        if len(found) != 1:
            checks[name] = {"original_alive": False, "correct_dock_and_stopped": False}
            continue
        x, _, z = map(float, found[0]["Pos"])
        speed = math.hypot(float(found[0]["Motion"][0]), float(found[0]["Motion"][2]))
        inside = (20 <= x <= 24 and -1 <= z <= 1) if name == "east" else (-1 <= x <= 1 and 8 <= z <= 13)
        checks[name] = {"original_alive": True, "position": [x, z], "speed": speed,
                        "correct_dock_and_stopped": inside and speed < .02}
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    cargo = {str(item.get("tag", {}).get("livequest_cargo", "")) for item in native["Inventory"]}
    x, y, z = map(float, native["Pos"])
    returned = math.hypot(x - 2.5, z + 2.5) <= 3 and abs(y - 72) <= .5 and float(native["Health"]) >= 1
    success = (all(c["correct_dock_and_stopped"] for c in checks.values()) and returned
               and {"east_consignment", "west_consignment"} <= cargo)
    return {"carts": checks, "original_consignments": sorted(cargo - {""}),
            "living_hand_in": returned, "native_objective_success": success}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    game = MinecraftGame(
        track="structured_tool",
        output_dir=args.output / "game", world_path=args.fixture,
        player_state=PlayerState(position=(10.5, 72, -2.5), yaw=0, pitch=38),
        headless=True, recording=True, recording_fps=5,
    )
    calls, error = [], None
    try:
        await game.start()
        before = await game.save_snapshot(args.output / "before")
        await game.begin()
        public = game.get_agent_interface()

        async def call(name, **arguments):
            result = await public.call_tool(name, arguments)
            calls.append({"name": name, "arguments": arguments, "result": result})
            (args.output / "public-calls.json").write_text(json.dumps(calls, indent=2) + "\n")
            if not result["success"]:
                raise RuntimeError(f"{name}: {result}")
            return result

        async def walk(x, z):
            for _ in range(30):
                p = (await public.observe())["position"]
                distance = math.hypot(x - p["x"], z - p["z"])
                if distance < .25:
                    return
                await call("LookAtPositionTool", x=x, y=p["y"] + 1.62, z=z)
                await call("MoveTool", direction="forward", duration=min(.65, max(.05, distance / 4.3)))
            raise RuntimeError("Bounded dock approach failed")

        try:
            await call("LookAtPositionTool", x=10.5, y=72.1, z=-.5)
            await call("UseHeldItemTool", duration=.1)
            await asyncio.sleep(5)
            for name, stand in (("east", (22, -1.5)), ("west", (-1.5, 10.5))):
                await walk(*stand)
                observation = await public.observe()
                carts = [e for e in observation["nearby_entities"] if e["name"] == "chest_minecart"]
                candidates = [e for e in carts if (e["position"]["x"] > 15) == (name == "east")]
                if len(candidates) != 1:
                    raise RuntimeError(f"Public {name} cart is not uniquely visible")
                p = candidates[0]["position"]
                await call("LookAtPositionTool", x=p["x"], y=p["y"] + .35, z=p["z"])
                await call("UseHeldItemTool", duration=.1)
                inspected = await call("InspectContainerTool")
                items = inspected["payload"]["items"]
                slot = next(item["slot"] for item in items if item["name"] == "paper")
                await call("TakeContainerItemTool", slot=slot)
            await walk(2.5, -2.5)
            await call("StopTool")
        except Exception as exc:
            error = str(exc)
        await game.end()
        after = await game.save_snapshot(args.output / "after")
        result = {"kind": "native_two_original_cart_preset_route_counterpolicy",
                  "track": "st", "implementation_error": error, "score": score(before, after, game.player_uuid),
                  "policy": "Preset the east route once; let ordinary west dock brake park its moving cart, then collect each original and return.",
                  "realtime_refuted_on_this_fixture": False,
                  "limits": ["No model run, calibrated difficulty or qualification.",
                             "Recovery-release and alternative parked-cart sorting are separate unproven controls.",
                             "VM witness is not implemented or claimed by this ST diagnostic."]}
        result["realtime_refuted_on_this_fixture"] = result["score"]["native_objective_success"]
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        await game.close()


if __name__ == "__main__":
    asyncio.run(main())
