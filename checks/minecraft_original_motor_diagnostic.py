"""Bounded public-motor diagnostic; disclosed routes are not unhinted task scores."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from benchmark.config import load_task
from benchmark.factory import make_game
from game.backends.x11.actions import ActionError
from game.backends.x11.interface import validate_actions


async def run(args):
    task = load_task(args.task)
    assert task.task_type == "visual_motor"
    assert 0 < args.diagnostic_budget <= task.time_limit_seconds
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "commands").mkdir()
    (output / "controller-harness.py").write_bytes(Path(__file__).read_bytes())
    (output / "source.json").write_text(json.dumps({
        "task": task.resolved(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "kind": "route_disclosed_public_motor_diagnostic_not_model_measurement",
        "intervention": args.intervention, "validity_question": args.question,
        "final_task_fixture_and_resources_modified": False,
        "diagnostic_budget_seconds": args.diagnostic_budget,
        "runtime_controller_inputs": "Authored route/plan and public screenshots only.",
        "claim_limit": "Access/control/resource composition only; not unhinted discovery, learning benefit or calibrated difficulty.",
    }, indent=2) + "\n")
    binding = make_game(task, output / "game", headless=True, recording=True, recording_fps=5)
    game = binding.game
    try:
        await game.start()
        before = await game.save_snapshot(output / "before")
        binding.verify_initial(before)
        members = game.members if task.participants else {"Player": binding}
        public = {role: member.game.get_agent_interface() for role, member in members.items()}
        index = 0

        async def capture(label):
            images = {}
            for role, interface in public.items():
                frame = await interface.observe()
                path = output / f"frame-{label}-{role}.png"
                frame.image.save(path)
                images[role] = {"path": str(path), "frame_id": frame.frame_id,
                                "captured_at_ns": frame.captured_at_ns}
            return images

        await game.begin()
        started = time.monotonic()
        images = await capture("ready")
        (output / "ready.json").write_text(json.dumps({"images": images, "roles": list(public)}))
        print("PUBLIC_VM_READY", output, flush=True)
        stopped = False
        while time.monotonic() - started < args.diagnostic_budget:
            path = output / "commands" / f"{index:03d}.json"
            if not path.exists():
                await asyncio.sleep(.05)
                continue
            request = json.loads(path.read_text())
            if request == {"finish": True}:
                stopped = True
                break
            try:
                role = request.get("role", "Player")
                if role not in public or set(request) - {"role", "commands", "observe"}:
                    raise ValueError("Only ordinary public VM requests are admitted")
                batch = request.get("commands", [])
                if batch:
                    validate_actions(batch)
                results = await asyncio.wait_for(public[role].act(batch), timeout=max(
                    .1, args.diagnostic_budget - (time.monotonic() - started))) if batch else []
                response = {"success": True, "results": [asdict(r) for r in results]}
            except asyncio.TimeoutError:
                break
            except (ValueError, TypeError, ActionError) as error:
                response = {"success": False, "error": str(error), "executed_commands": 0}
            images = await capture(f"{index:03d}")
            (output / f"response-{index:03d}.json").write_text(json.dumps({
                **response, "images": images, "elapsed_seconds": time.monotonic() - started,
            }, indent=2) + "\n")
            print("PUBLIC_BATCH", index, flush=True)
            index += 1
        for interface in public.values():
            await interface.act([{"name": "release_all", "arguments": {}}])
        await game.end()
        after = await game.save_snapshot(output / "after")
        result = {
            "kind": "route_disclosed_public_motor_diagnostic_not_model_measurement",
            "task_sha256": task.source.sha256, "task_type": task.task_type,
            "time_limit_seconds": task.time_limit_seconds,
            "diagnostic_budget_seconds": args.diagnostic_budget,
            "elapsed_seconds": time.monotonic() - started,
            "controller_finished": stopped, "public_batches": index,
            "evaluation": binding.evaluate(before, after), "metrics": binding.metrics(before, after),
        }
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        await game.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-budget", type=float, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--intervention", required=True)
    asyncio.run(run(parser.parse_args()))
