"""Assistant-guided reference: Alpha operator and a frozen, pixel-only Beta policy.

The Beta policy never receives Alpha's frames, requests, native state or evaluator.
Its exact role choreography is reference guidance, not an autonomous baseline.
"""

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
import re
from pathlib import Path
import subprocess
import time
import zlib

from PIL import Image, ImageChops

from agent_framework.agents.base_agent import AgentContext
from agent_framework.agents.public_operator import PublicOperator
from benchmark.config import load_task
from benchmark.factory import make_game


# Masks are from Beta's historical public trade screenshot, not native state.
TITLES = {
    "trade": ((459, 157, 502, 169),
              "eJxjYKApYAQBohWTYC7xehmRZBmJVMoIQowMcCaRSrH7FdUBeD2JUAo2CmIe8QFIJgAAJjsAKw=="),
    "review": ((398, 187, 565, 208),
               "eJztloEOgyAMRHv//9OLE+y1paCJ3ZbMxigcUJ4VqCKP3WnYLIiL+sRdPgwXXa0Z"
               "fhZzD2mL61bpAlzbUSIV/dqf6J2aqJ6OUSJCGnXTJv+mOJ4gSR0QRBgJMZdKrQjrhDDMxNSGK"
               "AXMvkxHmLqE6W1mmBR2i9lpLCY40HPMU9EUGrnA1PsJTDcmx2TJqMm6H8jI2/28qWMGSWb+s"
               "K0wH7tgxcFcLcoSu2uGYtJkO13eZcXbEuNDB/aE4krIH+2AruEzDOGkdhyjLOgwSykDJv3ZGUx"
               "NpT2vfhPTNcF2k8lHL6UMmGZRhjIoK8v7j48x/zqDvABLmAE5"),
    "inventory": ((800, 157, 910, 169),
                  "eJzlk0EOwCAIBN3/f7omKAvFqk3VSzmgkIVRjCn9w5DNRN1do/ot7SE6QkPMb6fZ4WaFh"
                  "LBqNM+EEb+8G6h1XYVmPJv6skkaoYFWvaOp8AuNC27ZeLcwh3la+QF8G6ZqY+1LpaFpQkq7"
                  "tNV2lhbtAh4YAIU="),
}


def title_visible(png, name):
    box, encoded = TITLES[name]
    with Image.open(io.BytesIO(png)) as image:
        if image.size != (960, 540):
            raise ValueError("Frozen public GUI reference requires 960x540 native frames")
        observed = bytes(value > 215 for value in image.convert("L").crop(box).tobytes())
    expected = zlib.decompress(base64.b64decode(encoded))
    # Check foreground and background separately: a blank or all-white crop fails.
    return all(
        sum(a == b for a, b in zip(observed, expected) if b == foreground)
        / max(1, expected.count(foreground)) >= .90
        for foreground in (0, 1)
    )


def command(name, **arguments):
    return {"name": name, "arguments": arguments}


def wait(milliseconds):
    return command("wait", milliseconds=milliseconds)


def key(name, duration=100):
    return [command("key_down", key=name), wait(duration),
            command("key_up", key=name), wait(150)]


def click(x, y, button="left"):
    return [command("mouse_move_to", x=x, y=y),
            command("mouse_down", button=button), wait(100),
            command("mouse_up", button=button), wait(250)]


def settle_trade_controls(png):
    commands = key("i") if title_visible(png, "inventory") else []
    commands += key("comma")
    for button in ("left", "right"):
        commands += [command("mouse_down", button=button), wait(80),
                     command("mouse_up", button=button)]
    return commands + [command("release_all"), wait(700)] + key("r") + [wait(700)]


def bind_recovery():
    return key("i") + [wait(400),
        command("mouse_move_to", x=779, y=402),
        command("mouse_down", button="left"), wait(200),
        command("mouse_move_to", x=362, y=525), wait(200),
        command("mouse_up", button="left"), wait(400)] + key("i") + [wait(400)]


def chat_batches(text):
    if not text or any(character not in "abcdefghijklmnopqrstuvwxyz " for character in text):
        raise ValueError("Only ordinary lowercase reference chat is supported")
    yield key("enter") + [wait(300)]
    # Native menu text can lose rapid keystrokes; each letter is spaced and bounded.
    for offset in range(0, len(text), 10):
        yield [entry for character in text[offset:offset + 10]
               for entry in key("space" if character == " " else character, 80)]
    yield key("enter") + [wait(300)]


def validate_batch(commands):
    if len(commands) > 60 or sum(
        entry["arguments"].get("milliseconds", 0) for entry in commands
        if entry["name"] == "wait"
    ) > 10000:
        raise ValueError("Reference batch exceeds the unchanged public motor limit")


def group_health_pixels(png):
    with Image.open(io.BytesIO(png)) as image:
        image = image.convert("RGB")
        return sum(
            any(g > 70 and r < g * .8 and b < 60
                for r, g, b in (image.getpixel((x, y)) for y in range(27, 37)))
            for x in range(7, 80)
        )


def own_health_pixels(png):
    with Image.open(io.BytesIO(png)) as image:
        image = image.convert("RGB")
        return sum(
            any(g > 70 and r < g * .8 and b < 60
                for r, g, b in (image.getpixel((x, y)) for y in range(499, 504)))
            for x in range(361, 599)
        )


def enemy_bar(png):
    """Find the native red combat bar, excluding menus and the player's HUD."""
    with Image.open(io.BytesIO(png)) as image:
        red, green, blue = image.convert("RGB").split()
        mask = ImageChops.multiply(
            ImageChops.multiply(red.point(lambda v: 255 if v > 130 else 0),
                                green.point(lambda v: 255 if v < 45 else 0)),
            blue.point(lambda v: 255 if 35 < v < 105 else 0),
        ).crop((40, 100, 820, 440))
        data = mask.tobytes()
    candidates = []
    for y in range(340):
        for match in re.finditer(rb"\xff{12,150}", data[y * 780:(y + 1) * 780]):
            candidates.append((match.end() - match.start(),
                               40 + (match.start() + match.end()) // 2, 100 + y))
    for width, x, y in sorted(candidates, reverse=True):
        if sum(abs(cx - x) < 12 and abs(cy - y) < 8 for _, cx, cy in candidates) >= 3:
            return x, y + 32
    return None


class WorkshopPeer:
    """Own-image state machine; all cooperation goes through actual native trade."""

    def __init__(self):
        self.transfer = 0
        self.offered = False
        self.reviewed = False
        self.in_trade = False

    def decide(self, png):
        if title_visible(png, "trade"):
            entering = not self.in_trade
            self.in_trade = True
            self.reviewed |= title_visible(png, "review")
            cursor = key("comma") if entering else []
            if self.transfer == 0 and not self.offered:
                self.offered = True
                return ("offer", cursor + [
                    command("mouse_move_to", x=779, y=402),
                    command("mouse_down", button="left"), wait(200),
                    command("mouse_move_to", x=500, y=252), wait(200),
                    command("mouse_up", button="left"), wait(600),
                ])
            return ("consent", cursor + click(524, 342) + key("y") + [wait(400)])
        if self.in_trade and self.reviewed:
            self.transfer += 1
            self.in_trade = self.reviewed = self.offered = False
            if self.transfer == 2:
                return ("equip", settle_trade_controls(png) + key("i")
                        + [wait(400)] + click(779, 402, "right")
                        + key("i") + [command("release_all"), wait(500)])
            return ("sent_hides", settle_trade_controls(png))
        if self.in_trade:
            # A declined invitation is not a completed transfer.
            self.in_trade = self.offered = False
            return ("wait_invitation", settle_trade_controls(png))
        return ("wait_invitation", key("y") + [wait(600)])


async def beta_peer(controls, output, task_id):
    output.mkdir(parents=True, exist_ok=False)
    index = 0
    log = (output / "public.jsonl").open("x")

    async def act(commands):
        validate_batch(commands)
        response = await controls.execute("action", {"commands": commands})
        log.write(json.dumps({"index": index, "commands": commands, "response": response}) + "\n")
        log.flush()

    async def observe():
        nonlocal index
        values = await controls.observe()
        if not isinstance(values, list):
            raise TypeError("Beta only accepts public native pixels")
        images = [entry for entry in values if entry["type"] == "image"]
        if len(images) != 1 or images[0]["mime_type"] != "image/png":
            raise ValueError("Expected one public PNG")
        png = images[0]["data"]
        (output / f"{index:04d}.png").write_bytes(png)
        index += 1
        return png

    async def say(text):
        for batch in chat_batches(text):
            await act(batch)

    try:
        opening = await observe()
        if task_id == "shared_workshop_exchange":
            # Authored reference-only route: west along the open floor to the arch.
            await act([command("mouse_move_relative", dx=-157, dy=0)] + key("w", 900)
                      + [command("release_all"), wait(500)])
            await say("at arch trade hides then bring boots")
            policy = WorkshopPeer()
            # Only the runner's shared native episode deadline retires an unfinished peer.
            while True:
                event, commands = policy.decide(await observe())
                if commands:
                    await act(commands)
                if event == "sent_hides":
                    await say("hides sent waiting boots at arch")
                if event == "equip":
                    await say("boots equip requested waiting at arch")
                    await observe()
                    return {"status": "policy_finished", "transfers": policy.transfer}
        if task_id != "sceptre_and_sword_team":
            raise ValueError("Unknown frozen peer policy")
        await act(bind_recovery())
        await observe()
        await say("lure wolf to me i wait for your damage")
        await act(key("r") + [command("mouse_move_relative", dx=0, dy=18)])
        baseline = group_health_pixels(opening)
        triggered = None
        yaw, pitch, misses, potions, last_potion = 0, 18, 0, 0, -10
        while True:
            png = await observe()
            if triggered is None:
                health = group_health_pixels(png)
                if health < baseline - 5:
                    triggered = time.monotonic()
                else:
                    baseline = max(baseline, health)
                    await act([wait(250)])
                    continue
            elapsed = time.monotonic() - triggered
            if elapsed >= 120:
                break
            target = enemy_bar(png)
            if target:
                dx = max(-80, min(80, round((target[0] - 480) * .22)))
                dy = max(-50, min(50, round((target[1] - 270) * .22)))
                misses = 0
            else:
                misses += 1
                dx, dy = (45, 0) if misses % 3 == 0 else (0, 0)
            yaw += dx
            pitch += dy
            commands = [command("mouse_move_relative", dx=dx, dy=dy)]
            if potions < 2 and 0 < own_health_pixels(png) < 160 and elapsed - last_potion > 8:
                commands += key("1") + [wait(1500)]
                potions += 1
                last_potion = elapsed
            await act(commands + [
                command("mouse_down", button="left"), wait(750),
                command("mouse_up", button="left"),
                command("mouse_down", button="right"), wait(750),
                command("mouse_up", button="right"), wait(150),
            ])
        correction = (-157 - yaw + 314) % 628 - 314
        await act(key("r") + [command("mouse_move_relative", dx=correction, dy=-pitch)]
                  + key("w", 700) + [command("release_all"), wait(500)])
        await say("returning arch use recovery now")
        await act(key("1") + [wait(1500)])
        await observe()
        return {"status": "policy_finished", "trigger": "own_public_group_health_drop",
                "support_seconds": 120}
    finally:
        log.close()


async def run(task_path, output, limit, startup_limit):
    task = load_task(task_path)
    if task.task_type != "visual_motor" or {p.id for p in task.participants} != {"Alpha", "Beta"}:
        raise ValueError("Exactly two native visual-motor participants are required")
    output.mkdir(parents=True, exist_ok=False)
    (output / "driver.py").write_bytes(Path(__file__).read_bytes())
    (output / "task.json").write_text(json.dumps(task.resolved(), indent=2) + "\n")
    result = {
        "kind": "assistantguidedreference", "formal": False, "uses_model": False,
        "status": "initializing", "task_sha256": task.source.sha256,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_boundary": "Alpha-only image operator; frozen independent Beta uses only its own "
                           "public images and controls. Native evaluator is read only after end.",
        "active_limit_seconds": min(limit, task.time_limit_seconds),
    }
    runtime_path = Path(os.environ["LIVEQUEST_VELOREN_RUNTIME"])
    runtime_bytes = runtime_path.read_bytes()
    result["runtime_manifest"] = str(runtime_path.resolve())
    result["runtime_sha256"] = hashlib.sha256(runtime_bytes).hexdigest()
    (output / "runtime.json").write_bytes(runtime_bytes)

    def save():
        pending = output / "result.pending"
        pending.write_text(json.dumps(result, indent=2) + "\n")
        pending.replace(output / "result.json")

    binding = make_game(task, output / "game", headless=True, recording=True, recording_fps=5)
    operator = PublicOperator(output / "Alpha")
    running = []
    try:
        save()
        async with asyncio.timeout(startup_limit):
            result["stage"] = "native_start"
            await binding.game.start()
            result["stage"] = "strict_opening"
            before = await binding.game.save_snapshot(output / "before")
            binding.verify_initial(before)
        await binding.game.begin()
        begin = time.monotonic_ns()
        deadline = begin + int(result["active_limit_seconds"] * 1e9)
        result.update(status="running", stage="public_policies", begin_monotonic_ns=begin)
        save()
        context = AgentContext(
            task.id + ".Alpha", task.task, binding.game.controls("Alpha")[0],
            begin, deadline, binding.game.instructions("Alpha"),
        )
        running = [
            asyncio.create_task(operator.run(context)),
            asyncio.create_task(beta_peer(binding.game.controls("Beta")[0],
                                          output / "Beta", task.id)),
        ]
        try:
            async with asyncio.timeout(result["active_limit_seconds"]):
                outcomes = await asyncio.gather(*running)
                result["Beta"] = outcomes[1]
        except TimeoutError:
            result["deadline_reached"] = True
        await binding.game.end()
        result["active_wall_seconds"] = (time.monotonic_ns() - begin) / 1e9
        result["stage"] = "private_terminal_scoring"
        after = await binding.game.save_snapshot(output / "after")
        evaluation = binding.evaluate(before, after)
        result["evaluation"] = evaluation
        result["stage"] = "native_route_metrics"
        result["metrics"] = binding.metrics(before, after) if binding.metrics else {}
        result.update(status="completed", measurement="valid", evaluation=evaluation,
                      task_outcome="success" if evaluation["success"] else "failure",
                      stage="finished")
    except Exception as error:
        result.update(status="error", measurement="unavailable", error=repr(error))
    finally:
        await operator.close()
        for pending in running:
            if not pending.done():
                pending.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        try:
            if binding.game.phase == "running":
                await binding.game.end()
            async with asyncio.timeout(120):
                await binding.game.close()
        except Exception as error:
            result.update(status="error", measurement="unavailable", cleanup_error=repr(error))
        save()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--startup-limit", type=int, default=1500)
    arguments = parser.parse_args()
    if arguments.limit <= 0 or arguments.startup_limit <= 0:
        parser.error("Both bounds must be positive")
    asyncio.run(run(arguments.task, arguments.output, arguments.limit, arguments.startup_limit))
