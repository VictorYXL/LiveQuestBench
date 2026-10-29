"""Bounded observed VM witness using only public images and motor commands."""

import json
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.request import Request, urlopen


OUT = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development/experiments/"
           "VE-S05-observed-ranged-reference-vm")


def command(name, **arguments):
    return {"name": name, "arguments": arguments}


def translate(steps, previous):
    shots = dict(previous)
    commands = []
    for operation, *args in steps:
        if operation == "shot":
            yard = args[0]
            if yard not in {"north", "south"} or shots.get(yard, 0) >= 45:
                raise ValueError("Bounded witness permits at most45 shots per yard")
            shots[yard] = shots.get(yard, 0) + 1
            commands += [command("mouse_down", button="left"),
                         command("wait", milliseconds=1000),
                         command("mouse_up", button="left"),
                         command("wait", milliseconds=600)]
        elif operation in {"key", "hold"}:
            key = args[0]
            if key not in {"w", "a", "s", "d", "space", "r", "i"}:
                raise ValueError("Unsupported witness key")
            duration = args[1] if operation == "hold" else 100
            commands += [command("key_down", key=key),
                         command("wait", milliseconds=duration),
                         command("key_up", key=key),
                         command("wait", milliseconds=300)]
        elif operation == "move":
            commands.append(command("mouse_move_relative", dx=args[0], dy=args[1]))
        elif operation == "scroll":
            commands.append(command("mouse_scroll", steps=args[0]))
        elif operation == "wait":
            commands.append(command("wait", milliseconds=args[0]))
        elif operation == "release":
            commands.append(command("release_all"))
        else:
            raise ValueError("Unknown public motor operation")
    waits = [row["arguments"]["milliseconds"] for row in commands if row["name"] == "wait"]
    if len(commands) > 60 or any(value < 0 for value in waits) or sum(waits) > 9500:
        raise ValueError("Public motor batch exceeds its existing bound")
    return commands, shots


def await_finish(finished, *, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + 540
    while clock() < deadline:
        if finished():
            return
        sleep(.5)
    raise TimeoutError("Observed ranged reference exceeded540s")


def control(arguments):
    url = json.loads((OUT / "control.json").read_text())["url"]
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+", url):
        raise ValueError("Only this local public reference endpoint is allowed")
    ledger = OUT / "operator-shots.json"
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    finishing = arguments == ["finish"]
    steps = ([["release"], ["wait", 1000]] if finishing
             else json.loads(arguments[0]) if arguments else [])
    commands, shots = translate(steps, previous)
    payload = {"commands": commands} if commands else None
    # Reserve attempted shots before dispatch: an ambiguous response cannot
    # silently permit another shot beyond the finite public witness budget.
    if commands:
        ledger.write_text(json.dumps(shots) + "\n")
    request = Request(url + ("/act" if commands else "/observe"),
                      data=json.dumps(payload).encode() if payload else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(result["error"])
    observation = result["observation"] if commands else result
    image = OUT / f"operator-{len(list(OUT.glob('operator-*.png'))):03}.png"
    shutil.copyfile(observation["image"], image)
    with (OUT / "operator-batches.jsonl").open("a") as stream:
        stream.write(json.dumps({"commands": commands, "image": str(image), "shots": shots}) + "\n")
    if finishing:
        (OUT / "operator-finished").write_text("Native evaluation decides success.\n")
    print(image)


def main(arguments):
    if arguments and arguments[0] == "control":
        control(arguments[1:])
    elif arguments == ["VE-S05", "observed-ranged-reference"]:
        await_finish((OUT / "operator-finished").exists)
    else:
        raise ValueError("This observer is only for the bounded S05 VM witness")


if __name__ == "__main__":
    main(sys.argv[1:])
