"""Legal public-warning or constant-switch policy in a single native episode."""
import argparse
import asyncio
import json
import math
from pathlib import Path
import time

import nbtlib

from game.minecraft.fixtures.timed_routing import timing
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from scripts.prove_two_cart import entities


def public_block(observation, pos):
    cube = observation["nearby_blocks"]
    x, y, z = (int(value - cube["minp"][axis]) for value, axis in zip(pos, ("x", "y", "z")))
    dims = cube["dims"]
    if not (0 <= x < dims["x"] and 0 <= y < dims["y"] and 0 <= z < dims["z"]):
        raise ValueError("Warning outside public native observation")
    return cube["palette"][cube["data"][x + dims["x"]*(y + dims["y"]*z)]]


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


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--policy", choices=("public-warning", "preset-east"), required=True)
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.fixture / "livequest-routing-public.json").read_text())
    binding = None
    if args.task:
        from benchmark.config import load_task
        from benchmark.factory import make_game
        task = load_task(args.task)
        if task.task_type != "structured_tool" or Path(task.fixture["world_path"]).resolve() != args.fixture.resolve():
            raise ValueError("Reference must use the declared ST task fixture")
        binding = make_game(task, args.output/"game", headless=True, recording=True, recording_fps=5)
        game = binding.game
    else:
        game = MinecraftGame(track="structured_tool", output_dir=args.output / "game", world_path=args.fixture,
                             player_state=PlayerState(position=(2.5,72,-10.5)), headless=True,
                             recording=True, recording_fps=5)
    calls = []
    result = {"kind": "native_timed_routing_prototype", "policy": args.policy,
              "implementation_error": None, "model_calls": 0, "qualification_claim": False}
    try:
        await game.start()
        before = await game.save_snapshot(args.output / "before")
        if binding:
            binding.verify_initial(before)
            controls, _ = binding.controls()
        await game.begin()
        public = game.get_agent_interface()

        async def call(name, **arguments):
            value = (json.loads(await controls.execute(name, arguments)) if binding
                     else await public.call_tool(name, arguments))
            calls.append({"name": name, "arguments": arguments, "result": value})
            (args.output / "public-calls.json").write_text(json.dumps(calls, indent=2)+"\n")
            if not value["success"]:
                raise RuntimeError(f"{name}: {value}")
            return value

        began = time.monotonic()
        previous, west_warning = None, None
        while time.monotonic()-began < 180:
            observation = await public.observe()
            warnings = {name: public_block(observation, pos)["name"] == "piston_head"
                        for name,pos in manifest["warning_indicators"].items()}
            if warnings != previous:
                calls.append({"public_warnings": warnings, "elapsed_wall": time.monotonic()-began,
                              "nearby_entities": observation["nearby_entities"]})
                previous = warnings
            if warnings["west"] and west_warning is None:
                west_warning = time.monotonic()
                if args.policy == "public-warning":
                    x,y,z = manifest["control"]
                    await call("LookAtPositionTool", x=x+.5, y=y+.1, z=z+.5)
                    await call("UseHeldItemTool", duration=.1)
            if west_warning is not None and time.monotonic()-west_warning > 30:
                break
            await asyncio.sleep(.5)
        result["public_west_warning_seen"] = west_warning is not None
        for side in (1,-1):
            await call("GoToPositionTool", x=25*side, y=72, z=-1)
            await call("LookAtPositionTool", x=24*side+.5, y=71.75, z=.5)
            inspected = await call("InspectContainerTool")
            for item in inspected["payload"]["items"]:
                if item["name"] == "paper":
                    await call("TakeContainerItemTool", slot=item["slot"])
        await call("GoToPositionTool", x=0, y=72, z=-10)
        await call("StopTool")
        await game.end()
        after = await game.save_snapshot(args.output / "after")
        result["score"] = score(before, after, game.player_uuid)
        if binding:
            result["task_sha256"] = task.source.sha256
            result["full_task_evaluation"] = await asyncio.to_thread(binding.evaluate, before, after)
        start = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
        end = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
        samples = nbtlib.load(after / "data/command_storage_livequest.dat")["data"]["contents"]["routing"]["samples"].unpack()
        result["actual_native_timing"] = timing(samples, start)
        result["elapsed_native_ticks"] = end-start
        result["samples"] = samples
        result["limits"] = ["ST only; VM parity unclaimed.", "Phase-shift robustness and recovery attempts remain separate gates.",
                            "A successful fixed policy is retained as a construct counterexample, not excluded."]
    except Exception as exc:
        result["implementation_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await game.close()
        (args.output / "public-calls.json").write_text(json.dumps(calls,indent=2)+"\n")
        (args.output / "result.json").write_text(json.dumps(result,indent=2,default=lambda x:x.tolist())+"\n")
        print(json.dumps({k:v for k,v in result.items() if k != "samples"}),flush=True)


if __name__ == "__main__":
    asyncio.run(main())
