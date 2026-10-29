"""Bounded public-pixel reference; never reads an observer or live world state."""

import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageStat


LABEL = "parallel-automatic-ranged-20261029"
OUT = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development/experiments") / (
    f"VE-S05-{LABEL}-vm")
WOLF = (
    "#...#...#........#...#.",
    "#...#...#........#..#..",
    "#...#...#..###...#..#..",
    "#...#...#........#..#..",
    "#...#...#.#...#..#..##.",
    "#...#...#.#...#..#..#..",
    "#...#...#.#...#..#..#..",
    ".................#..#.",
    ".##..##.....##...#.....",
)


class ControlBlocked(RuntimeError):
    pass


def command(name, **arguments):
    return {"name": name, "arguments": arguments}


def wolf_labels(image):
    """Own retained public Wolf glyph, including undamaged targets without a bar."""
    image = image.convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())
    masks = (
        [min(p) > 205 and max(p) - min(p) < 30 and p[2] >= p[0] - 5 for p in pixels],
        [min(p) > 205 and max(p) - min(p) < 3 for p in pixels],
    )
    on = [(x, y) for y, row in enumerate(WOLF) for x, bit in enumerate(row) if bit == "#"]
    off = [(x, y) for y, row in enumerate(WOLF) for x, bit in enumerate(row) if bit == "."]
    found = []
    # Unioning the masks would retain bright terrain as glyph foreground.
    for white in masks:
        for y in range(35, min(height - 12, 490)):
            for x in range(40, min(width - 24, 810)):
                base = y * width + x
                if not (white[base] and white[base + 4] and white[base + 8]):
                    continue
                hits = sum(white[base + dy * width + dx] for dx, dy in on)
                if hits < len(on) * .80:
                    continue
                misses = sum(not white[base + dy * width + dx] for dx, dy in off)
                if misses < len(off) * .68:
                    continue
                point = (x + 11, y + 4)
                if any(math.dist(point, old) < 12 for old in found):
                    continue
                found.append(point)
    return found


def image_shift(before, after, axis):
    box = (300, 100, 650, 200)
    reference = before.convert("L").crop(box)
    candidates = []
    for displacement in range(-35, 36):
        dx, dy = (displacement, 0) if axis == "yaw" else (0, displacement)
        patch = after.convert("L").crop(tuple(
            value + (dx if index % 2 == 0 else dy) for index, value in enumerate(box)))
        error = ImageStat.Stat(ImageChops.difference(reference, patch)).mean[0]
        candidates.append((error, displacement))
    error, displacement = min(candidates)
    if not -30 <= displacement <= -3:
        raise ControlBlocked(f"Unsupported public {axis} response: {displacement}px")
    return {"pixels_per_unit": -displacement / 5, "matching_error": error}


def ledge_row(image):
    """A cross-column light floor/dark outside boundary, not a private position."""
    grey = image.convert("L")
    pixels = grey.load()
    candidates = []
    for y in range(45, 470):
        changes = []
        for x in (660, 690, 720, 750, 780):
            above = sum(pixels[x + dx, y - 5] for dx in (-2, 0, 2)) / 3
            below = sum(pixels[x + dx, y + 5] for dx in (-2, 0, 2)) / 3
            changes.append(below - above)
        changes.sort()
        if changes[1] > 16:
            candidates.append((changes[2], y))
    return max(candidates)[1] if candidates else None


def platform_arrived(image):
    image = image.convert("RGB")
    top = max((ImageStat.Stat(image.crop((680, y, 790, y + 15))).mean
               for y in range(285, 390, 15)), key=sum)
    bottom = ImageStat.Stat(image.crop((680, 410, 790, 445))).mean
    return (min(sum(top), sum(bottom)) > 90 and
            max(abs(a / sum(top) - b / sum(bottom)) for a, b in zip(top, bottom)) < .025)


def health_width(image, label):
    pixels = image.convert("RGB").load()
    widths = []
    for y in range(max(0, label[1] + 6), min(image.height, label[1] + 20)):
        run = longest = 0
        for x in range(max(0, label[0] - 40), min(image.width, label[0] + 40)):
            red, green, blue = pixels[x, y]
            run = run + 1 if red > 100 and red > 1.6 * green and blue < 190 else 0
            longest = max(longest, run)
        widths.append(longest)
    widths.sort(reverse=True)
    return widths[2] if len(widths) >= 3 and 4 <= widths[2] < 78 else None


def edge_distance(row, pitch):
    """Historical fixed-eye heuristic, not calibrated native camera geometry."""
    angle = math.radians(pitch) + math.atan((row - 270) / 400)
    if not math.radians(10) < angle < math.radians(89):
        raise ControlBlocked("Public ledge projection is outside the calibrated range")
    return 1.7 / math.tan(angle)


def target_ray(point, yaw, pitch):
    """Image-plane heuristic; an overhead glyph is not a physical target point."""
    sx, sy = (point[0] - 480) / 400, (point[1] - 270) / 400
    p = math.radians(pitch)
    forward = math.cos(p) - sy * math.sin(p)
    down = math.sin(p) + sy * math.cos(p)
    return ((yaw + math.degrees(math.atan2(sx, forward))) % 360,
            math.degrees(math.atan2(down, math.hypot(sx, forward))))


def angle_difference(first, second):
    return (first - second + 180) % 360 - 180


def face_for_bearing(bearing):
    return min((0, 90, 180, 270), key=lambda face: abs(angle_difference(bearing, face)))


def firing_pitch(height, label_pitch):
    if not 10 < label_pitch < 89:
        raise ControlBlocked("No downward public target bearing")
    # Historical heuristic only: native labels also have fixed screen offsets,
    # and the first-person eye is animated. Do not use this as a feasibility proof.
    distance = (height + 1.7 - 2.0) / math.tan(math.radians(label_pitch))
    offset = -(height * .45 + .5 * distance) / max(distance - .45, .35) + distance * .03
    return min(88, math.degrees(math.atan2(height - offset, distance)))


def shot_allowed(distance, face, bearing, visible):
    return (visible and .12 <= distance <= .36
            and .45 * math.cos(math.radians(angle_difference(bearing, face))) > distance + .04)


class Motor:
    def __init__(self):
        self.url = json.loads((OUT / "control.json").read_text())["url"]
        if not re.fullmatch(r"http://127\.0\.0\.1:\d+", self.url):
            raise ValueError("Only this episode's local public endpoint is allowed")
        self.start = time.monotonic()
        self.http_seconds = self.wait_seconds = 0.
        self.frame = 0
        self.yaw = self.pitch = 0.
        self.image = None
        self.events = []

    def batch(self, commands, reason):
        if time.monotonic() - self.start > 530:
            raise ControlBlocked("Unchanged540s controller deadline; reserve cleanup time")
        commands = commands + [command("release_all"), command("wait", milliseconds=250)]
        if len(commands) > 64:
            raise ValueError("Motor batch bound")
        waits = sum(c["arguments"].get("milliseconds", 0) for c in commands if c["name"] == "wait")
        if waits > 10000:
            raise ValueError("Motor wait bound")
        self.wait_seconds += waits / 1000
        started = time.monotonic()
        request = Request(self.url + "/act", data=json.dumps({"commands": commands}).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=min(90, max(1, 540 - (started - self.start)))) as response:
            result = json.load(response)
        duration = time.monotonic() - started
        self.http_seconds += duration
        self.frame += 1
        path = OUT / f"automatic-{self.frame:03}.png"
        shutil.copyfile(result["observation"]["image"], path)
        self.image = Image.open(path).convert("RGB")
        row = {"frame": self.frame, "elapsed": time.monotonic() - self.start,
               "http_seconds": duration, "wait_seconds": waits / 1000,
               "reason": reason, "commands": commands,
               "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        with (OUT / "automatic-batches.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")

    def look(self, yaw, pitch):
        dx = round(angle_difference(yaw, self.yaw) * 157 / 90)
        dy = round((pitch - self.pitch) * 157 / 90)
        self.batch([command("mouse_move_relative", dx=dx, dy=dy)], "public camera reorientation")
        self.yaw = (self.yaw + dx * 90 / 157) % 360
        self.pitch += dy * 90 / 157

    def move(self, milliseconds, key="w", jump=False):
        if not 1 <= milliseconds <= 180:
            raise ValueError("Short released movement only")
        commands = [command("key_down", key=key)]
        if jump:
            commands.append(command("key_down", key="space"))
        self.batch(commands + [command("wait", milliseconds=milliseconds),
                               command("release_all"),
                               command("wait", milliseconds=2200 if jump else 700)],
                   "authored short stair/route segment" if jump else "released route/perimeter segment")

    def acquire(self):
        labels = wolf_labels(self.image)
        return min(labels, key=lambda point: math.dist(point, (480, 270))) if labels else None

    def find_face(self):
        label = self.acquire()
        if label:
            bearing, _ = target_ray(label, self.yaw, self.pitch)
            return face_for_bearing(bearing)
        for face in (0, 90, 180, 270):
            self.look(face, 65)
            label = self.acquire()
            if label:
                bearing, _ = target_ray(label, self.yaw, self.pitch)
                return face_for_bearing(bearing)
        raise ControlBlocked("No Wolf label in four public downward perimeter views")

    def approach(self, face):
        self.look(face, 70)
        previous, stagnant = None, 0
        for _ in range(24):
            row = ledge_row(self.image)
            if row is None:
                raise ControlBlocked("No reliable cross-column public ledge boundary")
            distance = edge_distance(row, self.pitch)
            self.events.append({"frame": self.frame, "ledge_row": row, "estimated_clearance": distance})
            if distance < .12:
                raise ControlBlocked("Unsafe or unsupported ledge clearance; no shot")
            if distance <= .36:
                return distance
            stagnant = stagnant + 1 if previous is not None and previous - distance < .015 else 0
            if stagnant >= 3:
                raise ControlBlocked("Three public ledge observations show no approach progress")
            previous = distance
            if distance > 1:
                self.move(80)
            else:
                self.look(face + 180, 70)
                self.move(40, "s")
                self.look(face, 70)
        raise ControlBlocked("Bounded public edge approach exhausted")

    def combat(self, height):
        shots, missing = 0, 0
        damaged, last_width, stagnant = False, None, 0
        face = self.find_face()
        for face_attempt in range(3):
            distance = self.approach(face)
            self.look(face, 75)
            label = self.acquire()
            if not label:
                raise ControlBlocked("No public target label at the acquired ledge")
            bearing, pitch = target_ray(label, self.yaw, self.pitch)
            corrected = face_for_bearing(bearing)
            if corrected != face:
                face = corrected
                continue
            if not shot_allowed(distance, face, bearing, True):
                raise ControlBlocked("Visible label does not establish an outboard muzzle line")
            break
        else:
            raise ControlBlocked("Public target keeps changing platform face")
        for _ in range(45):
            self.look(face, 75)
            label = self.acquire()
            if not label:
                missing += 1
                if missing >= 3 and damaged:
                    self.events.append({"candidate_target_disappearance": True, "shots": shots,
                                        "native_scorer_only": True})
                    return
                if missing >= 3:
                    raise ControlBlocked("Target disappeared before any public damage evidence")
                continue
            missing = 0
            width = health_width(self.image, label)
            progress = width is not None and (last_width is None or width < last_width - 1)
            damaged = damaged or width is not None
            stagnant = 0 if progress else stagnant + 1
            if (shots >= 3 and not damaged) or (shots and stagnant >= 6):
                raise ControlBlocked("Bounded shot probes show no further public health-bar progress")
            if width is not None:
                last_width = width
            bearing, pitch = target_ray(label, self.yaw, self.pitch)
            if not shot_allowed(distance, face, bearing, True):
                raise ControlBlocked("Target left the proven outboard firing cone")
            aim = firing_pitch(height, pitch) + (0, -.4, .4)[shots % 3]
            self.look(bearing, aim)
            self.batch([command("mouse_down", button="left"), command("wait", milliseconds=1000),
                        command("mouse_up", button="left"), command("wait", milliseconds=600)],
                       "fresh public label plus ledge; ST-derived native bow compensation")
            shots += 1
            self.events.append({"frame": self.frame, "shot": shots, "public_label": label,
                                "face": face, "bearing": bearing, "pitch": aim,
                                "public_health_bar_width_before": width})
        raise ControlBlocked("Unchanged45-shot per-yard bound")

    def wall(self, yaw, count):
        self.look(yaw, 0)
        for _ in range(count):
            self.move(180)

    def run(self):
        self.batch([command("mouse_scroll", steps=12)], "existing close public camera")
        before = self.image.copy()
        self.batch([command("mouse_move_relative", dx=5, dy=0)], "public yaw response probe")
        yaw = image_shift(before, self.image, "yaw")
        before = self.image.copy()
        self.batch([command("mouse_move_relative", dx=0, dy=5)], "public pitch response probe")
        pitch = image_shift(before, self.image, "pitch")
        self.events.append({"public_camera_calibration": {"yaw": yaw, "pitch": pitch}})
        self.batch([command("mouse_move_relative", dx=-5, dy=-5),
                    command("key_down", key="r"), command("wait", milliseconds=100),
                    command("key_up", key="r")], "restore verified arch heading and wield")
        self.move(180)
        self.move(180)
        self.move(180, jump=True)
        self.look(90, 0)
        for _ in range(3):
            self.move(100, jump=True)
        if not platform_arrived(self.image):
            raise ControlBlocked("Public image still shows a riser, not upper platform arrival")
        self.batch([], "authored upper platform arrival: suppress further jumping")
        self.combat(6)
        self.wall(270, 10)
        self.wall(180, 14)
        self.wall(0, 2)
        self.wall(90, 2)
        for _ in range(3):
            self.move(100, jump=True)
        if not platform_arrived(self.image):
            raise ControlBlocked("Public image still shows a riser, not lower platform arrival")
        self.batch([], "authored lower platform arrival: suppress further jumping")
        self.combat(5)
        self.wall(270, 10)
        self.wall(180, 6)
        self.wall(0, 5)
        self.batch([], "authored wall-aligned arch return; native evaluator decides")


def main():
    if sys.argv[1:] != ["VE-S05", LABEL]:
        raise ValueError("Wrong bounded reference invocation")
    motor = Motor()
    result = {"formal": False, "model": False, "operator_wait_seconds": 0}
    try:
        motor.run()
        result["controller_status"] = "route_completed_not_native_success_claim"
    except Exception as error:
        result.update(controller_status="blocked", error=f"{type(error).__name__}: {error}")
    finally:
        elapsed = time.monotonic() - motor.start
        result.update(elapsed_seconds=elapsed, public_http_seconds=motor.http_seconds,
                      commanded_wait_seconds=motor.wait_seconds,
                      local_control_seconds=max(0, elapsed - motor.http_seconds),
                      events=motor.events, frames=motor.frame,
                      no_live_private_feedback=True, no_autonomous_respawn=True)
        (OUT / "automatic-result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
