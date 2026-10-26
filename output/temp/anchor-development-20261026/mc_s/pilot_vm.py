"""Bounded reference session driven only by recorded, admitted public actions."""

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import time

from benchmark.config import load_task
from benchmark.factory import make_game
from game.backends.x11.interface import MotorInterface


async def run(output: Path, task_path: Path):
    task = load_task(task_path)
    output.mkdir(parents=True, exist_ok=False)
    (output / "commands").mkdir()
    (output / "reference.json").write_text(json.dumps({
        "task": task.task,
        "task_sha256": task.source.sha256,
        "track": task.task_type,
        "role": "authored_route_feasibility_reference_not_model_calibration",
        "controller_knowledge": "Authored static layout and prior public motor observations.",
        "runtime_observation": ("Screenshots only; no live native state used for control."
                                if task.task_type == "visual_motor" else
                                "Admitted public structured observations only; no private live state."),
    }, indent=2) + "\n")
    binding = make_game(task, output / "game", headless=True, recording=True, recording_fps=5)
    game = binding.game
    try:
        await game.start()
        before = await game.save_snapshot(output / "before")
        binding.verify_initial(before)
        interface = game.get_agent_interface()
        motor = isinstance(interface, MotorInterface)
        await game.begin()
        started = time.monotonic()

        async def observe(label: str) -> dict:
            observation = await interface.observe()
            if motor:
                observation.image.save(output / f"{label}.png")
                return {"frame_id": observation.frame_id, "captured_at_ns": observation.captured_at_ns}
            (output / f"{label}.json").write_text(json.dumps(observation, indent=2) + "\n")
            return {"position": observation["position"], "tick": observation["tick"]}

        await observe("opening")
        print(f"Public {task.task_type} reference ready at {output}", flush=True)
        index = 0
        while time.monotonic() - started < 1800:
            request = output / "commands" / f"{index:03d}.json"
            if not request.exists():
                await asyncio.sleep(0.1)
                continue
            data = json.loads(request.read_text())
            if data == {"finish": True}:
                break
            if motor:
                if set(data) != {"commands"}:
                    raise ValueError("Motor references require public motor commands")
                results = [asdict(row) for row in await interface.act(data["commands"])]
            else:
                if set(data) != {"actions"} or not isinstance(data["actions"], list):
                    raise ValueError("Structured references require an actions list")
                if not 1 <= len(data["actions"]) <= 64:
                    raise ValueError("Reference batches require 1-64 admitted actions")
                results = []
                for action in data["actions"]:
                    if set(action) != {"name", "arguments"} or action["name"] not in task.tools:
                        raise ValueError("Reference action is outside the task allowlist")
                    results.append(await interface.call_tool(action["name"], action["arguments"]))
            observation = await observe(f"frame-{index:03d}")
            (output / f"response-{index:03d}.json").write_text(json.dumps({
                "elapsed_seconds": time.monotonic() - started,
                **observation, "results": results,
            }, indent=2) + "\n")
            print(f"Reference public batch {index:03d} completed", flush=True)
            index += 1
        if motor:
            await interface.act([{"name": "release_all", "arguments": {}}])
        else:
            await interface.call_tool("StopTool", {})
        await game.end()
        after = await game.save_snapshot(output / "after")
        result = {
            "kind": "public_legal_action_reference", "track": task.task_type,
            "evaluation": binding.evaluate(before, after),
            "metrics": binding.metrics(before, after), "elapsed_seconds": time.monotonic() - started,
            "inputs": "Public task, known authored geometry and admitted observations only; no private live state.",
            "commands": index,
        }
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        await game.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--task", type=Path, default=Path(
        "config/minecraft/tasks/visual_motor/abandoned_mine_cargo.yaml"))
    args = parser.parse_args()
    asyncio.run(run(args.output, args.task))
