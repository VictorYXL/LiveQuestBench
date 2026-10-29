import importlib.util
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
import pytest


fixtures = Path(__file__).parents[2] / "fixtures/veloren"
spec = importlib.util.spec_from_file_location(
    "automatic_ranged_motor_reference", fixtures / "automatic_ranged_motor_reference.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def public_crop(name, origin):
    image = Image.new("RGB", (960, 540), (80, 60, 50))
    image.paste(Image.open(fixtures / "automatic_public_pixels" / name), origin)
    return image


def test_undamaged_public_label_and_actual_final_riser_are_not_rejected_as_arrival():
    image = public_crop("wolf-undamaged.png", (580, 280))
    assert reference.wolf_labels(image) == [(626, 299)]
    assert reference.health_width(image, (626, 299)) is None
    assert not reference.platform_arrived(public_crop("last-riser.png", (670, 280)))
    assert reference.platform_arrived(public_crop("platform.png", (670, 280)))
    assert 355 <= reference.ledge_row(public_crop("ledge.png", (650, 300))) <= 362


def test_public_camera_calibration_requires_observed_correct_direction():
    image = Image.new("RGB", (960, 540), "black")
    draw = ImageDraw.Draw(image)
    draw.polygon([(330, 110), (580, 120), (610, 190), (400, 180)], fill="white")
    shifted = ImageChops.offset(image, -20, 0)
    assert reference.image_shift(image, shifted, "yaw")["pixels_per_unit"] == 4
    with pytest.raises(reference.ControlBlocked, match="Unsupported"):
        reference.image_shift(image, image, "yaw")
    with pytest.raises(reference.ControlBlocked, match="Unsupported"):
        reference.image_shift(image, ImageChops.offset(image, 20, 0), "yaw")


def test_actual_neutral_glyph_on_bright_platform_remains_visible_without_floor_false_positive():
    image = public_crop("wolf-bright-platform.png", (510, 405))
    assert reference.wolf_labels(image) == [(533, 421)]
    assert reference.wolf_labels(Image.new("RGB", (960, 540), (255, 254, 250))) == []


def test_face_selection_preserves_the_existing_public_target_before_downward_scan():
    motor = reference.Motor.__new__(reference.Motor)
    motor.image = public_crop("wolf-bright-platform.png", (510, 405))
    motor.yaw, motor.pitch = 90, 0

    def no_camera_turn(*args):
        pytest.fail("A visible target must not be discarded by turning down toward the floor")

    motor.look = no_camera_turn
    assert motor.find_face() == 90


def test_public_bearing_selects_north_instead_of_stale_east_and_guards_muzzle():
    bearing, pitch = reference.target_ray((480, 320), 0, 75)
    assert reference.face_for_bearing(bearing) == 0
    assert 80 < pitch < 89
    assert 80 < reference.firing_pitch(6, pitch) < 89
    assert reference.shot_allowed(.25, 0, bearing, True)
    assert not reference.shot_allowed(.8, 0, bearing, True)
    assert not reference.shot_allowed(.25, 90, bearing, True)
    assert not reference.shot_allowed(.25, 0, bearing, False)


class PublicMotor(reference.Motor):
    def __init__(self):
        self.shots = self.frame = 0
        self.events = []
        self.image = None

    def look(self, yaw, pitch):
        self.yaw, self.pitch = yaw, pitch

    def find_face(self):
        return 0

    def approach(self, face):
        return .25

    def acquire(self):
        return (480, 320) if self.shots < 3 else None

    def batch(self, commands, reason):
        self.shots += sum(c["name"] == "mouse_down" for c in commands)


def test_legal_visible_label_and_ledge_can_fire_without_impossible_body_box(monkeypatch):
    motor = PublicMotor()
    monkeypatch.setattr(reference, "health_width", lambda image, label: 70 - motor.shots * 10)
    motor.combat(6)
    assert motor.shots == 3
    assert motor.events[-1]["candidate_target_disappearance"]
    assert motor.events[-1]["native_scorer_only"]


def test_unverified_damage_cannot_drive_blind_repeated_floor_shots(monkeypatch):
    motor = PublicMotor()
    motor.acquire = lambda: (480, 320)
    monkeypatch.setattr(reference, "health_width", lambda image, label: None)
    with pytest.raises(reference.ControlBlocked, match="health-bar progress"):
        motor.combat(6)
    assert motor.shots == 3
    motor = PublicMotor()
    motor.approach = lambda face: .8
    with pytest.raises(reference.ControlBlocked, match="outboard"):
        motor.combat(6)
    assert motor.shots == 0
