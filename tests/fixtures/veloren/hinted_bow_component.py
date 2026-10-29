"""Separately labelled public-image bow plumbing diagnostic, not task acceptance."""

import json
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from game.backends.x11.interface import validate_actions

sys.path.insert(0, str(Path.cwd() / "tests/fixtures/veloren"))
import automatic_ranged_motor_reference as automatic
from ranged_motor_reference import translate

LABEL = "hinted-bow-component-20261029"
OUT = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development/experiments") / (
    f"VE-S05-{LABEL}-vm")
LIMIT_SECONDS = 300
SHOT_LIMIT = 12


def bounded_commands(steps, previous):
    commands, shots = translate(steps, previous)
    if sum(shots.values()) > SHOT_LIMIT:
        raise ValueError("Component diagnostic permits at most12 attempted shots")
    commands += [automatic.command("release_all"), automatic.command("wait", milliseconds=250)]
    validate_actions(commands)
    return commands, shots


def control(arguments):
    ready = json.loads((OUT / "component-ready.json").read_text())
    finishing = arguments == ["finish"]
    if time.monotonic() > ready["deadline"] and not finishing:
        raise TimeoutError("Component diagnostic deadline reached")
    url = json.loads((OUT / "control.json").read_text())["url"]
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+", url):
        raise ValueError("Only this episode's public endpoint is allowed")
    ledger = OUT / "component-shots.json"
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    steps = [["release"], ["wait", 1000]] if finishing else json.loads(arguments[0])
    commands, shots = bounded_commands(steps, previous)
    ledger.write_text(json.dumps(shots) + "\n")
    request = Request(url + "/act", data=json.dumps({"commands": commands}).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=90) as response:
            result = json.load(response)
    except HTTPError as error:
        with (OUT / "component-errors.jsonl").open("a") as stream:
            stream.write(json.dumps({
                "commands": commands, "status": error.code,
                "response": error.read().decode("utf-8", errors="replace"),
                "elapsed": time.monotonic() - ready["start"],
                "shot_attempts_remain_reserved": shots,
            }) + "\n")
        raise
    image = OUT / f"component-{len(list(OUT.glob('component-*.png'))):03}.png"
    shutil.copyfile(result["observation"]["image"], image)
    with (OUT / "component-controls.jsonl").open("a") as stream:
        stream.write(json.dumps({"commands": commands, "image": str(image), "shots": shots,
                                 "elapsed": time.monotonic() - ready["start"]}) + "\n")
    if finishing:
        (OUT / "component-finished").write_text("Only terminal native evidence decides damage.\n")
    print(image)


class ComponentFinished(Exception):
    pass


class Component(automatic.Motor):
    def combat(self, height):
        (OUT / "component-ready.json").write_text(json.dumps({
            "start": self.start, "deadline": self.start + LIMIT_SECONDS,
            "public_yaw": self.yaw, "public_pitch": self.pitch,
            "authored_platform_height": height,
            "classification": "hinted_component_not_original_acquisition_or_difficulty",
            "hint": "Authored upper platform x18713..18724/y10821..10829/z507; bow muzzle must clear the edge. Original south wolf spawn x18729.5/y10824.5/z501 is a fixed design hint, not a live location.",
        }, indent=2) + "\n")
        while time.monotonic() < self.start + LIMIT_SECONDS:
            if (OUT / "component-finished").exists():
                raise ComponentFinished("Bounded component finished")
            time.sleep(.2)
        raise TimeoutError("Component300s deadline reached")


def main(arguments):
    if arguments and arguments[0] == "control":
        control(arguments[1:])
        return
    if arguments != ["VE-S05", LABEL]:
        raise ValueError("Wrong diagnostic invocation")
    automatic.OUT = OUT
    motor = Component()
    result = {"classification": "hinted_component_not_original_acquisition_or_difficulty",
              "model_calls": 0, "live_private_feedback": False, "shot_limit": SHOT_LIMIT}
    try:
        motor.run()
    except ComponentFinished as error:
        result["status"] = str(error)
    except Exception as error:
        result.update(status="blocked", error=f"{type(error).__name__}: {error}")
    finally:
        motor.batch([], "release component inputs; terminal native evaluator decides")
        result["elapsed_seconds"] = time.monotonic() - motor.start
        (OUT / "component-result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
