"""Bounded public-feedback bow policy; never reads the hidden comparator setting."""
import argparse
import asyncio
import json
import math
from pathlib import Path

import nbtlib

from game.minecraft.fixtures.archery_evidence import evaluate_events
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.fixture / "livequest-lock-public.json").read_text())
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
        game = MinecraftGame(
            track="structured_tool", output_dir=args.output / "game", world_path=args.fixture,
            player_state=PlayerState(position=(.5, 72, .5), inventory=[
                {"slot": 0, "item": "bow", "count": 1}, {"slot": 1, "item": "arrow", "count": 12}]),
            headless=True, recording=True, recording_fps=5,
        )
    calls = []
    result = {"kind": "native_hidden_target_lock_prototype", "implementation_error": None,
              "model_calls": 0, "learning_claim": False, "native_objective_success": False,
              "feedback_trials": [], "limits": ["ST/application-only; no VM or causal model comparison."]}
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
            (args.output / "public-calls.json").write_text(json.dumps(calls, indent=2) + "\n")
            if not value["success"]:
                raise RuntimeError(f"{name}: {value}")
            return value

        async def counter(pos, *, take=False):
            await call("GoToPositionTool", x=14, y=72, z=pos[2])
            await call("LookAtPositionTool", x=pos[0]+.5, y=pos[1]+.5, z=pos[2]+.5)
            inspected = await call("InspectContainerTool")
            items = inspected["payload"]["items"]
            count = sum(item["count"] for item in items if item["name"] == "paper")
            if count and take:
                await call("TakeContainerItemTool", slot=next(item["slot"] for item in items if item["name"] == "paper"))
            return count

        offset, launches = 0.0, 0
        for index, target in enumerate(manifest["targets"], 1):
            chests = target["feedback_chests"]
            previous = {name: await counter(pos) for name, pos in chests.items()}
            if previous["accepted"]:
                result["refuting_shortcut"] = "Original token already released before any shot at this target."
                break
            for attempt in range(min(6, 12-launches)):
                await call("GoToPositionTool", x=0, y=72, z=0)
                await call("SelectTool", slot=1)
                x, y, z = target["nominal_aim"]
                await call("LookAtPositionTool", x=x, y=y, z=z+offset)
                await call("UseHeldItemTool", duration=1.1)
                launches += 1
                await asyncio.sleep(7)
                current = {name: await counter(pos, take=name == "accepted") for name, pos in chests.items()}
                result["feedback_trials"].append({"target": index, "aim_offset": offset,
                                                  "native_public_counts": current, "previous": previous})
                if current["accepted"] > previous["accepted"]:
                    break
                if current["high"] > previous["high"]:
                    offset = min(.44, offset+.12)
                elif current["low"] > previous["low"]:
                    offset = max(0, offset-.06)
                else:
                    # A miss is not evidence about the hidden rule.
                    result["feedback_trials"][-1]["no_informative_counter_change"] = True
                previous = current
        await call("GoToPositionTool", x=0, y=72, z=0)
        await call("StopTool")
        await game.end()
        after = await game.save_snapshot(args.output / "after")
        native = nbtlib.load(after / "playerdata" / f"{game.player_uuid}.dat")
        tokens = {str(item.get("tag", {}).get("livequest_token", "")) for item in native["Inventory"]}
        p = list(map(float, native["Pos"]))
        alive_return = float(native["Health"]) > 0 and math.hypot(p[0]-.5, p[2]-.5) < 3
        storage = nbtlib.load(after / "data/command_storage_livequest.dat")["data"]["contents"]
        raw_events = storage.get("archery", {}).get("events", [])
        events = raw_events.unpack() if hasattr(raw_events, "unpack") else list(raw_events)
        identity = [int.from_bytes(game.player_uuid.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
        start = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
        end = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
        evidence = evaluate_events(events, identity, start_tick=start, end_tick=end)
        result.update({"owned_evidence": evidence, "native_events": events, "tokens": sorted(tokens-{""}),
                       "living_return": alive_return, "elapsed_native_ticks": end-start})
        result["native_objective_success"] = ({"target_1", "target_2"} <= tokens and alive_return
                                             and evidence["application_diagnostic_success"]
                                             and not result.get("refuting_shortcut"))
        if binding:
            result["task_sha256"] = task.source.sha256
            result["full_task_evaluation"] = await asyncio.to_thread(binding.evaluate, before, after)
    except Exception as exc:
        result["implementation_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await game.close()
        (args.output / "result.json").write_text(json.dumps(result, indent=2, default=lambda x: x.tolist()) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k != "native_events"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
