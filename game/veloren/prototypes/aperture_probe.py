"""Bounded model-free public-ST engineering operator; never reads the private map."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from benchmark.config import load_task
from benchmark.factory import make_game


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=240)
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument("--cold-sweep", action="store_true")
    policy.add_argument("--retained-sweep", action="store_true")
    policy.add_argument("--navigation-only", action="store_true",
                        help="Separately labelled motor diagnostic; no combat or learning claim")
    args = parser.parse_args()
    task = load_task(args.task)
    if task.task_type != "structured_tool":
        raise ValueError("This operator only admits public structured tools")
    args.output.mkdir(parents=True, exist_ok=False)
    commands = args.output / "commands"
    public = args.output / "public"
    commands.mkdir()
    public.mkdir()
    shutil.copy2(__file__, args.output / "driver.py")
    shutil.copy2(args.task, args.output / "task.yaml")
    runtime = Path(os.environ["LIVEQUEST_VELOREN_RUNTIME"])
    shutil.copy2(runtime, args.output / "runtime.json")
    result = {
        "status": "initializing", "formal": False, "uses_model": False,
        "task_sha256": task.source.sha256,
        "runtime_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "kind": ("public_ST_navigation_diagnostic" if args.navigation_only
                 else "public_ST_within_episode_feedback_sweep" if args.retained_sweep
                 else "public_ST_finite_cold_counterpolicy" if args.cold_sweep
                 else "public_ST_operator_feasibility_and_counterpolicy"),
        "limit_seconds": args.limit,
        "scope": "Only public observations and tool responses inform actions. Private fixture "
                 "and snapshots are authoring/scoring only. No model, reset, refill or teleport.",
    }
    binding = make_game(task, args.output / "game", headless=True,
                        recording=True, recording_fps=5)

    def save():
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    save()
    try:
        async with asyncio.timeout(1500):
            await binding.game.start()
            before = await binding.game.save_snapshot(args.output / "before")
            binding.verify_initial(before)
        controls, _ = binding.controls()
        await binding.game.begin()
        begin = time.monotonic()
        result.update(status="running", begin_monotonic=begin)
        save()
        (public / "instructions.txt").write_text(task.task)
        index = 0

        async def capture(response=None):
            raw = await controls.observe()
            observation = json.loads(raw) if isinstance(raw, str) else raw
            (public / f"{index:04d}.json").write_text(json.dumps({
                "elapsed": time.monotonic() - begin, "observation": observation,
                "response": response,
            }, indent=2) + "\n")
            (public / "latest.json").write_text(json.dumps({"index": index}) + "\n")
            return observation

        await capture()
        try:
            async with asyncio.timeout(min(args.limit, task.time_limit_seconds)):
                if args.cold_sweep or args.retained_sweep or args.navigation_only:
                    from game.veloren.prototypes.aperture_counterpolicy import (
                        cold_sweep, settled_navigation, PolicyStop,
                    )

                    async def request(tool=None, **arguments):
                        nonlocal index
                        index += 1
                        value = {"observe": True} if tool is None else {"tool": tool, "arguments": arguments}
                        (commands / f"{index:04d}.json").write_text(json.dumps(value) + "\n")
                        raw = None if tool is None else await controls.execute(tool, arguments)
                        response = json.loads(raw) if isinstance(raw, str) else raw
                        observation = await capture(response)
                        save()
                        return observation

                    try:
                        if args.navigation_only:
                            result["navigation_pulses"] = []
                            result["diagnostic_scope"] = (
                                "Unchanged versioned v7 geometry, original health and public controls. "
                                "Only public floor arrival is tested, not combat feasibility or learning."
                            )
                            row = await settled_navigation(
                                request, request, [18712.5, 10806],
                                pulse_log=result["navigation_pulses"],
                            )
                            result["diagnostic_arrival"] = {
                                key: row[key] for key in ("position", "velocity", "on_ground")
                            }
                        else:
                            await cold_sweep(request, request, result,
                                             retain_feedback=args.retained_sweep)
                    except PolicyStop as error:
                        result["policy_stop"] = str(error)
                    save()
                while not (args.cold_sweep or args.retained_sweep or args.navigation_only):
                    path = commands / f"{index + 1:04d}.json"
                    while not path.exists():
                        await asyncio.sleep(.05)
                    request = json.loads(path.read_text())
                    index += 1
                    if request == {"finish": True}:
                        break
                    if request == {"observe": True}:
                        response = None
                    else:
                        if set(request) != {"tool", "arguments"}:
                            raise ValueError("Expected one ordinary public tool request")
                        raw = await controls.execute(request["tool"], request["arguments"])
                        response = json.loads(raw) if isinstance(raw, str) else raw
                    await capture(response)
        except TimeoutError:
            result["deadline_reached"] = True
        await controls.execute("StopTool", {})
        await binding.game.end()
        after = await binding.game.save_snapshot(args.output / "after")
        result.update(status="completed", measurement="valid",
                      active_wall_seconds=time.monotonic() - begin, public_requests=index,
                      evaluation=binding.evaluate(before, after),
                      metrics=binding.metrics(before, after))
    except Exception as error:
        result.update(status="error", measurement="unavailable", error=repr(error))
    finally:
        save()
        try:
            await binding.game.close()
        except Exception as error:
            result.update(status="error", measurement="unavailable", cleanup_error=repr(error))
        save()


if __name__ == "__main__":
    asyncio.run(main())
