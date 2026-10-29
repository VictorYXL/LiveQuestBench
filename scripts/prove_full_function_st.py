"""Bounded public native proof; instance pinning occurs only before the episode."""
import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from benchmark.config import load_task
from benchmark.factory import make_game
from game.minecraft.fixtures.function_replication import public_manifest
from scripts.prove_function_replication import public_block


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--task", type=Path, default=Path(
        "config/minecraft/tasks/structured_tools/modular_build_procedure_transfer.yaml"))
    parser.add_argument("--instance-index", type=int, choices=(0, 1))
    parser.add_argument("--policy", choices=("cold-and", "public-probe"), default="cold-and")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    task = load_task(args.task)
    if args.instance_index is None:
        binding = make_game(task, output/"game", headless=True, recording=True, recording_fps=5)
    else:
        with patch("game.minecraft.evaluators.function_replication.secrets.randbelow",
                   return_value=args.instance_index):
            binding = make_game(task, output/"game", headless=True, recording=True, recording_fps=5)
    calls = []
    try:
        await binding.game.start()
        before = await binding.game.save_snapshot(output/"before")
        binding.verify_initial(before)
        controls, _ = binding.controls()
        await binding.game.begin()
        async def call(name, arguments):
            reply = await controls.execute(name, arguments)
            calls.append({"name": name, "arguments": arguments, "result": reply})
            (output/"public-calls.json").write_text(json.dumps(calls, indent=2)+"\n")
            if not json.loads(reply)["success"]:
                raise RuntimeError(f"Public action failed: {reply}")

        chosen = "AND"
        probe = None
        if args.policy == "public-probe":
            await call("GoToPositionTool", {"x": -2, "y": 72, "z": 3})
            await call("SelectTool", {"slot": 9})
            await call("LookAtPositionTool", {"x": .5, "y": 72.1, "z": .5})
            await call("UseHeldItemTool", {"duration": .1})
            await asyncio.sleep(4)
            observation = await binding.game.get_agent_interface().observe()
            indicator = public_block(observation, public_manifest()["reference"]["indicator"])
            chosen = "OR" if indicator["name"] == "piston_head" else "AND"
            probe = {"inputs": [1, 0], "public_indicator": indicator, "chosen_connection": chosen}
            (output/"public-probe.json").write_text(json.dumps(probe, indent=2)+"\n")
        for panel in public_manifest()["panels"]:
            x, y, z = panel["sockets"][chosen]
            for name, arguments in [
                ("GoToPositionTool", {"x": x-2, "y": y, "z": z}),
                ("SelectTool", {"slot": 1}),
                ("PlaceTool", {"x": x, "y": y-1, "z": z, "face": "top"}),
            ]:
                await call(name, arguments)
        await controls.execute("StopTool", {})
        await binding.game.end()
        after = await binding.game.save_snapshot(output/"after")
        result = {"kind": "full_task_native_ST_bounded_instance_proof_not_causal_model_evidence",
                  "policy": args.policy, "public_probe": probe,
                  "author_pinned_instance_before_episode": args.instance_index,
                  "model_calls": 0, "task_sha256": task.source.sha256,
                  "evaluation": await asyncio.to_thread(binding.evaluate, before, after),
                  "metrics": binding.metrics(before, after)}
        (output/"result.json").write_text(json.dumps(result, indent=2)+"\n")
        print(json.dumps(result), flush=True)
    finally:
        await binding.game.close()


if __name__ == "__main__":
    asyncio.run(main())
