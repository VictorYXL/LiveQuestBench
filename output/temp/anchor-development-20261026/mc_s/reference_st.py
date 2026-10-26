"""Bounded legal-action feasibility reference, not a scored model baseline."""

import argparse
import asyncio
import json
import math
from pathlib import Path
import time

from benchmark.config import load_task
from benchmark.factory import make_game
from game.minecraft.structured_tools.interface import StructuredInterface


async def run(output: Path, task_path: Path) -> None:
    task = load_task(task_path)
    output.mkdir(parents=True, exist_ok=False)
    binding = make_game(task, output / "game", headless=True, recording=True, recording_fps=5)
    game = binding.game
    started = time.monotonic()
    with (output / "actions.jsonl").open("x") as log:
        try:
            await game.start()
            interface = game.get_agent_interface()
            assert isinstance(interface, StructuredInterface)
            before = await game.save_snapshot(output / "before")
            binding.verify_initial(before)
            assert not binding.evaluate(before, before)["success"]
            await game.begin()

            async def call(name: str, **arguments):
                if time.monotonic() - started > 600:
                    raise TimeoutError("Reference exceeded its ten-minute development budget")
                assert task.tools is not None and name in task.tools
                result = await interface.call_tool(name, arguments)
                observation = await interface.observe()
                log.write(json.dumps({
                    "elapsed": time.monotonic() - started, "tool": name, "arguments": arguments,
                    "result": result, "position": observation["position"], "health": observation["health"],
                }) + "\n")
                log.flush()
                if result.get("success") is not True:
                    raise RuntimeError(f"Reference action refused: {name}: {result}")
                if observation["health"] <= 0:
                    raise RuntimeError("Reference died; native failure preserved")
                return result

            async def walk(x: float, z: float):
                for _ in range(70):
                    position = (await interface.observe())["position"]
                    distance = math.hypot(position["x"] - x, position["z"] - z)
                    if distance < 0.16:
                        return
                    await call("LookAtPositionTool", x=x, y=position["y"] + 1.62, z=z)
                    await call("MoveTool", direction="forward", duration=max(0.05, min(0.65, distance / 5)))
                raise RuntimeError(f"Reference could not reach public waypoint {(x, z)}")

            async def take(x: int, y: int, z: int):
                await call("LookAtPositionTool", x=x + 0.5, y=y + 0.5, z=z + 0.5)
                await call("InspectContainerTool")
                await call("TakeContainerItemTool", slot=0)

            async def edge(axis: str, boundary: int):
                for _ in range(24):
                    position = (await interface.observe())["position"]
                    offset = position[axis] - boundary
                    if 0.01 <= offset < 0.299 and abs(position["y"] - 80) < 0.01:
                        return
                    if offset >= 0.299 or abs(position["y"] - 80) > 0.01:
                        raise RuntimeError(f"Unsafe reference edge stance: {position}")
                    target = {**position, "y": position["y"] + 1.62}
                    target[axis] += 5
                    await call("LookAtPositionTool", **target)
                    await call("MoveTool", direction="forward", duration=0.025)
                    await asyncio.sleep(0.3)
                raise RuntimeError("Reference did not establish a visible support-face stance")

            async def south_ladder(wall_z: int, bottom: int, top: int):
                await call("SelectTool", slot=3)
                for y in range(bottom, top + 1):
                    await call("PlaceTool", x=0, y=y, z=wall_z, face="south")
                await walk(0.5, wall_z + 0.5)

            async def west_ladder(wall_x: int, bottom: int, top: int):
                await call("SelectTool", slot=3)
                for y in range(bottom, top + 1):
                    await call("PlaceTool", x=wall_x, y=y, z=27, face="west")
                await walk(wall_x + 0.5, 27.5)

            await walk(23.5, 0.5)
            await call("SelectTool", slot=2)
            for x in range(24, 32):
                await edge("x", x)
                await call("PlaceTool", x=x - 1, y=79, z=0, face="east")
                await walk(x + 0.5, 0.5)
            for z in range(1, 5):
                await edge("z", z)
                await call("PlaceTool", x=31, y=79, z=z - 1, face="south")
                await walk(31.5, z + 0.5)
            await walk(31.5, 7.5)
            await walk(50.5, 7.5)
            await take(52, 80, 7)
            await walk(31.5, 7.5)
            await walk(31.5, 0.5)
            await walk(0.5, 0.5)
            await walk(0.5, 36.5)
            await take(0, 57, 38)
            await walk(0.5, 34.5)
            await south_ladder(32, 57, 59)
            await walk(0.5, 29.5)
            await south_ladder(27, 60, 62)
            await walk(0.5, 24.5)
            await south_ladder(22, 63, 65)
            await walk(0.5, 20.5)
            await walk(23.5, 20.5)
            await walk(23.5, 27.5)
            await west_ladder(25, 66, 67)
            await walk(27.5, 27.5)
            await west_ladder(29, 68, 69)
            await walk(30.5, 27.5)
            await call("SelectTool", slot=1)
            await call("DigTool", x=32, y=71, z=27)
            await take(32, 70, 27)
            await walk(23.5, 27.5)
            await walk(23.5, 20.5)
            await walk(0.5, 20.5)
            await walk(0.5, 19.5)
            await south_ladder(17, 66, 68)
            await walk(0.5, 14.5)
            await south_ladder(12, 69, 71)
            await walk(0.5, 0.5)
            await call("StopTool")
            await asyncio.sleep(0.5)
            await game.end()
            after = await game.save_snapshot(output / "after")
            result = {"kind": "legal_public_ST_reference", "evaluation": binding.evaluate(before, after),
                      "metrics": binding.metrics(before, after), "elapsed_seconds": time.monotonic() - started,
                      "task_sha256": task.source.sha256,
                      "timing_scope": "Environment startup through terminal snapshot",
                      "note": "Uses authored static layout and public ST observations/tools only. "
                              "No private live state or task-time administration. Not a model difficulty result."}
            (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result), flush=True)
            assert result["evaluation"]["success"], "Reference did not complete the native goal"
        finally:
            await game.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--task", type=Path, default=Path(
        "config/minecraft/tasks/structured_tools/abandoned_mine_cargo.yaml"))
    arguments = parser.parse_args()
    asyncio.run(run(arguments.output, arguments.task))
