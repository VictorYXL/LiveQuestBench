"""Bounded public native reference; never a model Baseline.

AttackTool completion releases its input, not the pending charged projectile.
Keep aim fixed until that state ends, refresh moving targets after repositioning,
and observe the last allowed shot before declaring budget exhaustion. Always
attempt the ordinary return route, including after a bounded combat failure.
The evaluator, not target disappearance or this controller, establishes success.
Targets can run around the platform to its north/south face. Use that perimeter
instead of shooting down through the platform floor from its interior.
"""

import json
import math
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen


DEV = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development")


def target_in(row, uid):
    return next((entity for entity in row["nearby_entities"] if entity["uid"] == uid), None)


def release_and_observe(observe, sleep=time.sleep):
    for _ in range(60):
        row = observe()
        if row["survival"]["health"]["dead"]:
            raise RuntimeError("Player died during bow release")
        if row["survival"]["character_state"] != "ChargedRanged":
            sleep(.2)
            return observe()
        sleep(.05)
    raise RuntimeError("Charged bow did not leave its released state within the bound")


def platform_bounds(y):
    return (18713, 18724), {10808: (10804, 10812), 10824: (10821, 10829)}[y]


def needs_new_face(position, target, y):
    return not any(
        target[axis] < lower and position[axis] - lower <= .6
        or target[axis] >= upper and upper - position[axis] <= .6
        for axis, (lower, upper) in enumerate(platform_bounds(y)))


def firing_position(point, y, height):
    (xmin, xmax), (ymin, ymax) = platform_bounds(y)
    x = min(xmax - .25, max(xmin + .25, point[0]))
    target_y = min(ymax - .25, max(ymin + .25, point[1]))
    exterior = False
    for axis, lower, upper in ((0, xmin, xmax), (1, ymin, ymax)):
        if point[axis] < lower or point[axis] >= upper:
            edge = lower + .25 if point[axis] < lower else upper - .25
            if axis == 0:
                x = edge
            else:
                target_y = edge
            exterior = True
    if not exterior:
        raise RuntimeError("No exterior firing line to the lower target")
    return [x, target_y, height]


def move_to(observe, act, point, *, tolerance=1.2, sleep=time.sleep):
    precise = tolerance <= .12
    stalls = 0
    if precise:
        act("StopTool")
        sleep(.4)
    for _ in range(45):
        row = observe()
        if row["survival"]["health"]["dead"]:
            raise RuntimeError("Player died during the route witness")
        if precise and (not row["on_ground"] or abs(row["position"][2] - point[2]) > .25):
            raise RuntimeError("Lost native footing during precise perimeter movement")
        distance = math.dist(row["position"][:2], point[:2])
        if distance <= tolerance and abs(row["position"][2] - point[2]) < 1.1:
            return
        backstep = precise and distance < .7
        if backstep:
            # Native wielded reverse movement is slower; one forward tick can
            # coast about0.4m and oscillate across this narrow ledge waypoint.
            act("LookTool", x=row["position"][0] - 3 * (point[0] - row["position"][0]) / distance,
                y=row["position"][1] - 3 * (point[1] - row["position"][1]) / distance,
                z=row["position"][2] + 1.2)
            sleep(.2)
        else:
            act("LookTool", x=point[0], y=point[1], z=point[2] + 1.2)
        if not precise and point[2] > row["position"][2] + .5 and distance < 7:
            act("JumpTool")
        ticks = (max(1, min(6, int((distance - .7) * 2))) if precise
                 else max(1, min(18, round(distance * 2))))
        result = act("MoveTool", direction="backward" if backstep else "forward",
                     duration_ticks=ticks)["result"]
        if precise:
            act("StopTool")
            sleep(.4)
        stalled = result.get("detail", {}).get("code") == "stalled"
        if precise and stalled:
            # A short native action can report stalled before its coasting ends.
            settled = observe()
            remaining = math.dist(settled["position"][:2], point[:2])
            stalled = remaining > tolerance and distance - remaining < .02
        stalls = stalls + 1 if stalled else 0
        if stalls >= 2:
            raise RuntimeError("Public movement is blocked")
    raise RuntimeError("Bounded movement did not reach its waypoint")


def fire(observe, act, go, uid, y, height, *, sleep=time.sleep, limit=45):
    previous_health, stagnant = None, 0
    row = observe()
    for count in range(limit):
        target = target_in(row, uid)
        if target is None:
            return {"shots": count, "public_dead": False, "target_missing": True}
        if target["health"]["dead"]:
            return {"shots": count, "public_dead": True, "target_missing": False}
        if row["survival"]["health"]["dead"]:
            raise RuntimeError("Player died during bounded bow fire")
        if not row["on_ground"] or abs(row["position"][2] - height) > .25:
            raise RuntimeError("Native footing did not support the firing perimeter")
        health = target["health"]["current"]
        stagnant = stagnant + 1 if previous_health is not None and health >= previous_health else 0
        previous_health = health
        if (count == 0 or needs_new_face(row["position"], target["position"], y)
                or stagnant and stagnant % 8 == 0) and target["position"][2] < height - .5:
            go(firing_position(target["position"], y, height), tolerance=.12)
            row = observe()
            if not row["on_ground"] or abs(row["position"][2] - height) > .25:
                raise RuntimeError("Native footing did not support the firing perimeter")
            target = target_in(row, uid)
            if target is None or target["health"]["dead"]:
                return {"shots": count, "public_dead": bool(target and target["health"]["dead"]),
                        "target_missing": target is None}
        point = target["position"]
        distance = math.dist(row["position"][:2], point[:2])
        difference = row["position"][2] - point[2]
        offset = -(difference * .45 + .5 * distance) / max(distance - .45, .35) + distance * .03
        offset += (0, -.4, .4)[(stagnant // 4) % 3]
        act("LookTool", x=point[0], y=point[1], z=point[2] + offset)
        act("AttackTool", channel="primary", duration_ticks=30)
        row = release_and_observe(observe, sleep)
    target = target_in(row, uid)
    return {"shots": limit, "public_dead": bool(target and target["health"]["dead"]),
            "target_missing": target is None}


def main(key, label):
    if key != "VE-S05":
        raise ValueError("Wrong task for this diagnostic")
    out = DEV / "experiments" / f"{key}-{label}-st"
    url = json.loads((out / "control.json").read_text())["url"]

    def request(path, payload=None):
        req = Request(url + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=180) as response:
            return json.load(response)

    def observe():
        return request("/observe")

    def act(name, **arguments):
        return request("/act", {"name": name, "arguments": arguments})

    def go(point, *, tolerance=1.2):
        return move_to(observe, act, point, tolerance=tolerance)

    opening = observe()
    start = opening["position"]
    wolves = sorted((entity for entity in opening["nearby_entities"]
                     if "wolf" in (entity.get("name_text") or "").lower()),
                    key=lambda entity: entity["position"][1])
    if len(wolves) != 2:
        raise RuntimeError("Two native wolves are not publicly observable")
    report = {"classification": "public_reference_not_formal", "yards": [],
              "returned_to_start": False}
    try:
        act("WieldTool", wield=True)
        for (y, heights), wolf in zip(
            ((10808, [502, 503, 504, 505, 506]),
             (10824, [502, 503, 504, 505, 506, 507])), wolves,
        ):
            go([18703.5, y, 501])
            x0 = 18705.5 if y == 10808 else 18703.5
            for index, z in enumerate(heights):
                go([x0 + 2 * index, y, z], tolerance=.5)
            go([18723.5, y, heights[-1]], tolerance=.25)
            try:
                result = fire(observe, act, go, wolf["uid"], y, heights[-1])
                report["yards"].append({"uid": wolf["uid"], **result})
            finally:
                go([18703.5, y, 501])
    finally:
        try:
            go(start, tolerance=2)
            act("StopTool")
            time.sleep(2)
            report["returned_to_start"] = True
        finally:
            (out / "controller-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    if not all(row["public_dead"] or row["target_missing"] for row in report["yards"]):
        raise RuntimeError("Bounded bow budget exhausted; return route still attempted")


if __name__ == "__main__":
    main(*sys.argv[1:])
