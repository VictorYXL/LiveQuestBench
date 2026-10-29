"""One continuous model-free discovery/build episode; no private rule lookup."""
import argparse
import asyncio
import json
from pathlib import Path

import nbtlib

from game.minecraft.fixtures.function_replication import score, count_removals
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.runtime.observed_server import ObservedServer
import game.minecraft.runtime.session as session


def public_block(observation, pos):
    cube = observation["nearby_blocks"]
    x, y, z = (int(value - cube["minp"][axis]) for value, axis in zip(pos, ("x", "y", "z")))
    dims = cube["dims"]
    if not (0 <= x < dims["x"] and 0 <= y < dims["y"] and 0 <= z < dims["z"]):
        raise ValueError("Indicator is outside ordinary public observation")
    return cube["palette"][cube["data"][x + dims["x"] * (y + dims["y"] * z)]]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    public = json.loads((args.fixture / "livequest-function-public.json").read_text())
    session.MinecraftServer = ObservedServer
    game = MinecraftGame(
        track="structured_tool", output_dir=args.output / "game", world_path=args.fixture,
        player_state=PlayerState(position=(-2.5, 72, -2.5), inventory=[
            {"slot": 0, "item": "cobblestone", "count": 12},
            {"slot": 1, "item": "stone_pickaxe", "count": 1}]),
        headless=True, recording=True, recording_fps=5,
    )
    calls = []
    result = {"kind": "native_hidden_function_discovery_prototype", "implementation_error": None,
              "learning_claim": False, "model_calls": 0, "native_function_match": False,
              "native_objective_success": False,
              "limits": ["ST diagnostic only; no VM or model causal comparison.", "AND/OR feasibility subset."]}
    try:
        await game.start()
        before = await game.save_snapshot(args.output / "before")
        await game.begin()
        interface = game.get_agent_interface()

        async def call(name, **arguments):
            value = await interface.call_tool(name, arguments)
            calls.append({"name": name, "arguments": arguments, "result": value})
            (args.output / "public-calls.json").write_text(json.dumps(calls, indent=2) + "\n")
            if not value["success"]:
                raise RuntimeError(f"{name}: {value}")
            return value

        async def approach(pos):
            await call("GoToPositionTool", x=pos[0] - 2, y=72, z=pos[2])

        async def toggle(pos):
            await call("SelectTool", slot=9)
            await call("LookAtPositionTool", x=pos[0] + .5, y=pos[1] + .1, z=pos[2] + .5)
            await call("UseHeldItemTool", duration=.1)

        async def read_indicator(station):
            observation = await interface.observe()
            block = public_block(observation, station["indicator"])
            calls.append({"public_indicator": station["indicator"], "block": block})
            return block["name"] == "piston_head"

        reference = public["reference"]
        await call("GoToPositionTool", x=-2, y=72, z=3)
        await toggle(reference["inputs"][0])
        await asyncio.sleep(4)
        discovered = "OR" if await read_indicator(reference) else "AND"
        result["discovered_from_public_10_probe"] = discovered

        # Optional sensor diagnostic; not a required learning trial or scripted failure.
        await approach((-3, 72, -2))
        await call("SelectTool", slot=1)
        await call("PlaceTool", x=-3, y=71, z=-2, face="top")
        await call("SelectTool", slot=2)
        await call("DigTool", x=-3, y=72, z=-2)
        final_connections = []
        observed = []
        for index, station in enumerate([reference, *public["panels"]]):
            if index:
                pos = station["sockets"][discovered]
                await approach(pos)
                await call("SelectTool", slot=1)
                await call("PlaceTool", x=pos[0], y=pos[1]-1, z=pos[2], face="top")
                final_connections.append([pos])
            stand = station["inputs"][0]
            await call("GoToPositionTool", x=stand[0]-1, y=72, z=stand[2]+2)
            state = [1,0] if index == 0 else [0,0]
            for pair in ((0, 0), (1, 0), (1, 1), (0, 1)):
                for bit in range(2):
                    if state[bit] != pair[bit]:
                        await toggle(station["inputs"][bit])
                        state[bit] = pair[bit]
                await asyncio.sleep(5)
                observed.append({"station": index, "inputs": pair, "output": await read_indicator(station)})
        result["public_four_case_observations"] = observed
        await call("StopTool")
        await game.end()
        after = await game.save_snapshot(args.output / "after")
        start = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
        end = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
        events = nbtlib.load(after / "data/command_storage_livequest.dat")["data"]["contents"]["function"]["events"].unpack()
        result["native_events"] = events
        result.update(score(events, start_tick=start, final_connections=final_connections))
        path = args.output / "game/successful-breaks.jsonl"
        breaks = [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []
        result["break_events"] = breaks
        result["removals"] = count_removals(breaks, game.player_uuid, start_tick=start, end_tick=end)
        result["observer_native_validated"] = any(
            event.get("x") == -3 and event.get("y") == 72 and event.get("z") == -2 for event in breaks)
        result["public_and_private_outputs_agree"] = all(
            (result["reference"] if row["station"] == 0 else result["panels"][row["station"]-1])
            .get("".join(map(str,row["inputs"]))) == row["output"] for row in observed)
        player = nbtlib.load(after / "playerdata" / f"{game.player_uuid}.dat")
        result["alive"] = float(player["Health"]) > 0
        result["native_objective_success"] = bool(
            result["native_function_match"] and result["public_and_private_outputs_agree"]
            and result["removals"]["within_six_removal_budget"] and result["alive"])
    except Exception as exc:
        result["implementation_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await game.close()
        (args.output / "public-calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        (args.output / "result.json").write_text(json.dumps(result, indent=2, default=lambda x: x.tolist()) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k not in ("native_events", "break_events")}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
