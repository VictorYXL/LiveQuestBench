"""One bounded public-ST check of the versioned initialization-only native protocol."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from benchmark.config import load_task
from benchmark.factory import make_game
import game.veloren


async def public_check(interface, result, output, *, opening_only=False):
    async def observe():
        row = json.loads(await interface.observe())
        with (output / "public.jsonl").open("a") as stream:
            stream.write(json.dumps({"observation": row}) + "\n")
        return row

    async def act(name, **arguments):
        response = json.loads(await interface.execute(name, arguments))
        with (output / "public.jsonl").open("a") as stream:
            stream.write(json.dumps({"tool": name, "arguments": arguments, "response": response}) + "\n")
        result["public_actions"] += 1
        if response.get("status") != "completed":
            raise RuntimeError(f"Native public operation did not complete: {name}: {response}")
        return response

    def fields(dialogue):
        return {key: dialogue[key] for key in ("sender_uid", "dialogue_id", "tag")}

    def coins(row):
        return sum(entry["item"]["amount"] for entry in row["inventory"]["items"]
                   if entry["item"]["id"] == {"Simple": "common.items.utility.coins"})

    async def acknowledge(dialogue):
        await asyncio.sleep(1.7)
        await act("DialogueAckTool", **fields(dialogue))

    async def waypoint(point):
        stalls = 0
        for _ in range(45):
            row = await observe()
            distance = sum((point[i] - row["position"][i]) ** 2 for i in (0, 1)) ** .5
            if distance <= 1.2:
                return
            await act("LookTool", x=point[0], y=point[1], z=point[2] + 1.2)
            response = await act("MoveTool", direction="forward",
                                 duration_ticks=max(1, min(18, round(distance * 2))))
            stalls = stalls + 1 if response.get("detail", {}).get("code") == "stalled" else 0
            if stalls >= 2:
                raise RuntimeError("Transferred public navigation prefix is blocked")
        raise RuntimeError("Bounded public waypoint did not complete")

    opening = await observe()
    offer = opening.get("dialogue")
    if not offer or not offer.get("responses"):
        raise RuntimeError("No ordinary unanswered opening offer")
    yes = [choice for choice in offer["responses"]
           if choice["text"].lower().strip().startswith("yes")]
    if len(yes) != 1 or not offer.get("text"):
        raise RuntimeError("Opening offer has no unique public affirmative choice")
    result["public_opening_offer"] = offer
    initial_coins = coins(opening)
    await act("DialogueResponseTool", **fields(offer), response_id=yes[0]["response_id"])
    result["ordinary_yes_submitted"] = True
    seen = set()
    for _ in range(40):
        row = await observe()
        dialogue = row.get("dialogue")
        if dialogue and not dialogue.get("responses"):
            signature = (dialogue["dialogue_id"], dialogue.get("tag"))
            if signature not in seen:
                seen.add(signature)
                await acknowledge(dialogue)
                if len(seen) == 3:
                    break
        await asyncio.sleep(.2)

    if opening_only:
        if len(seen) != 3:
            raise RuntimeError("Ordinary acceptance did not reach all three native source statements")
        result["opening_only_source_statements"] = len(seen)
        return

    # These are the archived public-ST trajectory's corridor points, not a private NPC feed.
    await waypoint([18729, 10813, 501])
    await waypoint([18745, 10813, 501])
    recipient = None
    for _ in range(60):
        row = await observe()
        matches = [entity for entity in row["nearby_entities"]
                   if entity.get("control_target") and entity["uid"] != offer["sender_uid"]
                   and entity.get("name_text")
                   and re.search(r"(?<!\w)" + re.escape(entity["name_text"].rsplit(" (", 1)[0])
                                 + r"(?!\w)", offer["text"], flags=re.IGNORECASE)]
        if len(matches) != 1:
            raise RuntimeError("Public offer does not uniquely identify an observed recipient")
        recipient = matches[0]
        if recipient["distance"] <= 2.8:
            await act("TalkTool", **recipient["control_target"])
            result["public_recipient"] = {
                key: recipient[key] for key in ("uid", "control_target", "name_text")}
            break
        point = recipient["position"]
        await act("LookTool", x=point[0], y=point[1], z=point[2] + 1.2)
        await act("MoveTool", direction="forward",
                  duration_ticks=max(1, min(12, round(recipient["distance"] * 2))))
    else:
        raise RuntimeError("Bounded ordinary recipient approach did not complete")

    seen = set()
    for _ in range(60):
        row = await observe()
        if coins(row) > initial_coins:
            result["public_reward_delta"] = coins(row) - initial_coins
            return
        dialogue = row.get("dialogue")
        if dialogue and dialogue["sender_uid"] == recipient["uid"]:
            signature = (dialogue["dialogue_id"], dialogue.get("tag"))
            if signature not in seen:
                seen.add(signature)
                if not dialogue.get("responses"):
                    await acknowledge(dialogue)
                else:
                    choices = [choice for choice in dialogue["responses"]
                               if any(word in choice["text"].lower() for word in
                                      ("message", "deliver", "yes", "reward", "something for you"))]
                    if len(choices) != 1:
                        raise RuntimeError("No unambiguous ordinary delivery response")
                    await act("DialogueResponseTool", **fields(dialogue),
                              response_id=choices[0]["response_id"])
        await asyncio.sleep(.2)
    else:
        raise RuntimeError("No public reward arrived in the bounded native dialogue")

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--opening-only", action="store_true",
                        help="Stop after ordinary acceptance/source statements;30-second public bound.")
    args = parser.parse_args()
    task = load_task(args.task)
    if task.task_type != "structured_tool" or task.id not in (
            "native_message_courier_initial_v2", "native_message_courier_initial_v3"):
        raise ValueError("Only separately versioned native Message ST fixtures are supported")
    root = Path(game.veloren.__file__).resolve().parents[2]
    subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--",
         "game/veloren", "scripts/veloren_initial_message_check.py",
         str(args.task.resolve())], check=True)
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.task, args.output / "task.yaml")
    shutil.copy2(__file__, args.output / "driver.py")
    hashes = {}
    for path in (root / "game/veloren").rglob("*.py"):
        name = path.relative_to(root)
        destination = args.output / "python-source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        hashes[str(name)] = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output / "source-manifest.json").write_text(json.dumps({
        "head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "sha256": hashes,
        "driver_sha256": hashlib.sha256((args.output / "driver.py").read_bytes()).hexdigest(),
        "task_sha256": hashlib.sha256((args.output / "task.yaml").read_bytes()).hexdigest(),
        "scope": "Exact versioned adapter/controller/task archive before initialization.",
    }, indent=2) + "\n")
    binding = make_game(task, args.output / "game", headless=True, recording=True, recording_fps=5)
    result = {"status": "initializing", "formal": False, "public_actions": 0,
              "public_budget_seconds": 30 if args.opening_only else 180,
              "scope": "One bounded public-ST mechanism check, not a model benchmark or admission. "
                       "Fixed corridor waypoints transfer from VE-I03-native-ack-reference-st's "
                       "archived public controller; recipient decisions use current public input only. "
                       "Stop at native reward or the first concrete public-flow blocker; no extra default-offer probe."}
    if args.opening_only:
        result["scope"] = ("One30-second public-ST opening/ordinary acceptance check. No navigation, "
                           "delivery/payment attempt, model benchmark or whole-goal success requirement.")
    path = args.output / "result.json"
    started = False

    def save():
        path.write_text(json.dumps(result, indent=2) + "\n")

    try:
        save()
        await binding.game.start()
        before = await binding.game.save_snapshot(args.output / "before")
        binding.verify_initial(before)
        await binding.game.begin()
        started = True
        begin = time.monotonic()
        result["status"] = "running"
        save()
        interface, _ = binding.controls()
        try:
            async with asyncio.timeout(min(result["public_budget_seconds"], task.time_limit_seconds)):
                await public_check(interface, result, args.output, opening_only=args.opening_only)
        except Exception as error:
            result["public_check_error"] = repr(error)
        await binding.game.end()
        after = await binding.game.save_snapshot(args.output / "after")
        result.update(status="completed", measurement="valid",
                      active_wall_seconds=time.monotonic() - begin,
                      evaluation=binding.evaluate(before, after))
    except Exception as error:
        result.update(status="error", measurement="unavailable", error=repr(error))
        if started:
            await binding.game.end()
    finally:
        try:
            await binding.game.close()
        except Exception as error:
            result.update(status="error", cleanup_error=repr(error))
        save()


if __name__ == "__main__":
    asyncio.run(main())
