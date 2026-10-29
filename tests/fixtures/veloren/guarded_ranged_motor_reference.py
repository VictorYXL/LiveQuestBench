"""Short public-image-reviewed motor segments; annotations never decide score."""

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.request import Request, urlopen


LABEL = "guarded-ranged-reference"
OUT = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development/experiments") / (
    f"VE-S05-{LABEL}-vm")


class UnsupportedControl(RuntimeError):
    pass


def command(name, **arguments):
    return {"name": name, "arguments": arguments}


def settled(commands):
    return commands + [command("release_all"), command("wait", milliseconds=700)]


def plan(previous, packet):
    state = copy.deepcopy(previous)
    if packet["frame"] != state["frame"] or state.get("review_consumed"):
        raise ValueError("A fresh public frame review is required")
    view = packet["visible"]
    operation, *args = packet["do"]
    if operation == "finish":
        return settled([]), state
    if "probe" in state:
        probe = state.pop("probe")
        if view.get("landmark_id") != probe["landmark_id"]:
            raise UnsupportedControl("Camera probe lost its public landmark")
        axis = 0 if probe["axis"] == "yaw" else 1
        point = view["landmark_pixel"]
        displacement = point[axis] - probe["point"][axis]
        cross = abs(point[1 - axis] - probe["point"][1 - axis])
        if not 2 <= abs(displacement) <= 150 or cross > abs(displacement) * .75 + 3:
            raise UnsupportedControl("Public frames do not establish camera response")
        state.setdefault("camera", {})[probe["axis"]] = -displacement / 5
    if operation == "respawn":
        if view.get("mode") != "dead" or state.get("respawns", 0) >= 2:
            raise ValueError("Respawn requires the visible death screen and remaining bound")
        state.update(camera={}, needs_arch=True, respawns=state.get("respawns", 0) + 1)
        state.pop("arrival_frame", None)
        return settled([command("key_down", key="space"),
                        command("wait", milliseconds=100),
                        command("key_up", key="space")]), state
    if view.get("mode") != "play":
        raise ValueError("Gameplay camera/input state is not publicly established")
    if operation == "probe":
        axis = args[0]
        if axis not in {"yaw", "pitch"} or not view.get("footing"):
            raise ValueError("Camera probe needs settled footing")
        state["probe"] = {"axis": axis, "point": view["landmark_pixel"],
                          "landmark_id": view["landmark_id"], "frame": state["frame"]}
        return settled([command("mouse_move_relative", dx=5 if axis == "yaw" else 0,
                                dy=5 if axis == "pitch" else 0)]), state
    if operation == "look":
        dx, dy = args
        if abs(dx) > 157 or abs(dy) > 45:
            raise ValueError("Reorientation exceeds one bounded public pan")
        return settled([command("mouse_move_relative", dx=dx, dy=dy)]), state
    if operation == "view":
        if args[0] not in {-4, 12}:
            raise ValueError("Use the existing bounded camera zoom")
        return settled([command("mouse_scroll", steps=args[0])]), state
    if operation == "wield":
        return settled([command("key_down", key="r"), command("wait", milliseconds=100),
                        command("key_up", key="r")]), state
    if set(state.get("camera", {})) != {"yaw", "pitch"}:
        raise ValueError("Verify both camera signs from public frames before moving or firing")
    if state.get("needs_arch"):
        if view.get("landmark") != "arch" or not view.get("footing"):
            raise ValueError("Reorient at the visible arch after each respawn")
        state["needs_arch"] = False
    if not view.get("footing"):
        raise ValueError("Wait for visibly settled footing")
    if operation == "step" and view.get("landmark") == "platform":
        state["arrival_frame"] = state["frame"]
        return settled([]), state
    if operation in {"step", "reposition"}:
        key, milliseconds, jump = args
        if key not in {"w", "a", "s", "d"} or not view.get("path_clear"):
            raise ValueError("Movement needs a visible clear route")
        on_platform = view.get("landmark") == "platform"
        if on_platform != (operation == "reposition"):
            raise ValueError("Platform movement requires explicit repositioning")
        near_edge = view.get("edge") != "safe"
        limit = (40 if near_edge else 80) if on_platform else 180
        if (type(milliseconds) is not int or not 1 <= milliseconds <= limit
                or near_edge and key == "w"
                or jump and (on_platform or view.get("landmark") != "stairs")):
            raise ValueError("Unsafe edge movement or oversized stair segment")
        commands = [command("key_down", key=key)]
        if jump:
            commands.append(command("key_down", key="space"))
        return settled(commands + [command("wait", milliseconds=milliseconds)]), state
    if operation in {"aim", "shot"}:
        if (view.get("landmark") != "platform" or not view.get("bow")
                or not view.get("clear_line") or view.get("edge") not in {"safe", "near"}):
            raise ValueError("Firing needs a visible target line, bow and supported platform")
        x1, y1, x2, y2 = view["target_box"]
        if not 0 <= x1 < x2 <= 960 or not 0 <= y1 < y2 <= 540:
            raise ValueError("Target must be a visible body box in the public frame")
        if operation == "aim":
            dx = ((x1 + x2) / 2 - 480) / state["camera"]["yaw"]
            dy = ((y1 + y2) / 2 - 270) / state["camera"]["pitch"]
            return settled([command("mouse_move_relative",
                                    dx=round(max(-15, min(15, dx))),
                                    dy=round(max(-15, min(15, dy))))]), state
        if not x1 <= 480 <= x2 or not y1 <= 270 <= y2:
            raise ValueError("Reticle is not on the visible target; refuse floor-directed shot")
        yard, count = args
        if yard not in {"north", "south"} or count not in {1, 2}:
            raise ValueError("One reviewed shot, or two after confirmed public damage")
        if count == 2 and not view.get("damage_confirmed"):
            raise ValueError("Do not repeat shots without observed damage")
        shots = state.setdefault("shots", {})
        if shots.get(yard, 0) + count > 45:
            raise ValueError("Unchanged45-shot per-yard bound")
        shots[yard] = shots.get(yard, 0) + count
        commands = []
        for _ in range(count):
            commands += [command("mouse_down", button="left"),
                         command("wait", milliseconds=1000),
                         command("mouse_up", button="left"),
                         command("wait", milliseconds=600)]
        return settled(commands), state
    if operation == "wait":
        return settled([]), state
    raise ValueError("Unsupported reviewed operation")


def control(arguments):
    url = json.loads((OUT / "control.json").read_text())["url"]
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+", url):
        raise ValueError("Only this local public endpoint is allowed")
    path = OUT / "operator-state.json"
    state = json.loads(path.read_text()) if path.exists() else {"frame": -1}
    packet = json.loads(arguments[0]) if arguments else None
    try:
        commands, next_state = plan(state, packet) if packet else ([], state)
    except UnsupportedControl as error:
        (OUT / "operator-blocked.json").write_text(json.dumps({
            "error": str(error), "packet": packet, "state": state}) + "\n")
        commands, next_state = settled([]), state
        packet["do"] = ["finish"]
    # Reserve shots before dispatch, including ambiguous transport failures.
    next_state["review_consumed"] = bool(commands)
    path.write_text(json.dumps(next_state) + "\n")
    request = Request(url + ("/act" if commands else "/observe"),
                      data=json.dumps({"commands": commands}).encode() if commands else None,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=90) as response:
        result = json.load(response)
    observation = result["observation"] if commands else result
    next_state["frame"] = state["frame"] + 1
    next_state["review_consumed"] = False
    image = OUT / f"operator-{next_state['frame']:03}.png"
    shutil.copyfile(observation["image"], image)
    next_state["image_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    path.write_text(json.dumps(next_state) + "\n")
    with (OUT / "operator-batches.jsonl").open("a") as stream:
        stream.write(json.dumps({"reviewed_frame_sha256": state.get("image_sha256"),
                                 "packet": packet, "commands": commands,
                                 "image": str(image), "state": next_state}) + "\n")
    if packet and packet["do"] == ["finish"]:
        (OUT / "operator-finished").write_text("Native scoring decides the outcome.\n")
    print(image)


if __name__ == "__main__":
    if sys.argv[1:2] == ["control"]:
        control(sys.argv[2:])
    elif sys.argv[1:] == ["VE-S05", LABEL]:
        deadline = time.monotonic() + 540
        while time.monotonic() < deadline:
            if (OUT / "operator-finished").exists():
                break
            time.sleep(.5)
        else:
            raise TimeoutError("Observed ranged reference exceeded540s")
    else:
        raise ValueError("Wrong bounded witness invocation")
