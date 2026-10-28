"""Offline player initialization and private server-side verification."""

from dataclasses import dataclass, field
import math
import re
from pathlib import Path
from uuid import UUID

import nbtlib
from nbtlib import Byte, Compound, Double, Float, Int, IntArray, List, Short, String


MODES = {"survival": 0, "creative": 1, "adventure": 2, "spectator": 3}


@dataclass
class PlayerState:
    position: tuple[float, float, float]
    dimension: str = "minecraft:overworld"
    yaw: float = 0
    pitch: float = 0
    gamemode: str = "survival"
    health: float = 20
    food: int = 20
    saturation: float = 5
    experience_level: int = 0
    inventory: list[dict] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.position) != 3 or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in (*self.position, self.yaw, self.pitch, self.health, self.saturation)
        ):
            raise ValueError("Player position and numeric fields must be finite numbers")
        if self.dimension not in ("minecraft:overworld", "minecraft:the_nether", "minecraft:the_end"):
            raise ValueError("Only vanilla dimensions are supported")
        if self.gamemode not in MODES or not -90 <= self.pitch <= 90 or not 0 < self.health <= 20:
            raise ValueError("Invalid game mode, pitch or health")
        if type(self.food) is not int or not 0 <= self.food <= 20 or not 0 <= self.saturation <= self.food:
            raise ValueError("Invalid food or saturation")
        if type(self.experience_level) is not int or self.experience_level < 0:
            raise ValueError("Experience level must be a nonnegative integer")
        slots = set()
        for item in self.inventory:
            if (not isinstance(item, dict) or not {"slot", "item", "count"} <= set(item)
                    or set(item) - {"slot", "item", "count", "damage"}):
                raise ValueError("Inventory entries require slot, item and count, with optional damage")
            slot, count, name = item["slot"], item["count"], item["item"]
            if type(slot) is not int or slot not in (*range(36), 100, 101, 102, 103, -106) or slot in slots:
                raise ValueError("Inventory slots must be valid and unique")
            if type(count) is not int or not 1 <= count <= 64:
                raise ValueError("Inventory count must be in [1, 64]")
            if not isinstance(name, str) or not re.fullmatch(r"(minecraft:)?[a-z0-9_]+", name):
                raise ValueError("Invalid vanilla inventory item ID")
            if "damage" in item and (
                type(item["damage"]) is not int or not 0 <= item["damage"] < 2147483647 or count != 1
            ):
                raise ValueError("Initial item damage requires a nonnegative integer and a single item")
            slots.add(slot)
        effect_ids = set()
        for effect in self.effects:
            if not isinstance(effect, dict) or set(effect) != {"id", "amplifier", "duration"}:
                raise ValueError("Effects require id, amplifier and duration in ticks")
            name = effect["id"]
            if not isinstance(name, str) or not re.fullmatch(r"minecraft:[a-z0-9_]+", name):
                raise ValueError("Effects require a namespaced vanilla identifier")
            if (name in effect_ids or type(effect["amplifier"]) is not int
                    or not 0 <= effect["amplifier"] <= 127
                    or type(effect["duration"]) is not int
                    or not (effect["duration"] == -1 or 1 <= effect["duration"] <= 2147483647)):
                raise ValueError("Effect identities must be unique with bounded amplifier and duration")
            effect_ids.add(name)

    @classmethod
    def from_dict(cls, values: dict) -> "PlayerState":
        values = dict(values)
        values.setdefault("saturation", min(5, values.get("food", 20)))
        return cls(**values)

    def nbt(self, player_uuid: UUID) -> Compound:
        parts = [(player_uuid.int >> shift) & 0xFFFFFFFF for shift in (96, 64, 32, 0)]
        return Compound({
            "DataVersion": Int(3700),
            "UUID": IntArray([part if part < 2**31 else part - 2**32 for part in parts]),
            "Pos": List[Double](self.position),
            "Motion": List[Double]([0, 0, 0]),
            "Rotation": List[Float]([self.yaw, self.pitch]),
            "Dimension": String(self.dimension),
            "Health": Float(self.health),
            "foodLevel": Int(self.food),
            "foodSaturationLevel": Float(self.saturation),
            "foodExhaustionLevel": Float(0),
            "XpLevel": Int(self.experience_level),
            "XpP": Float(0),
            "XpTotal": Int(0),
            "Air": Short(300),
            "Fire": Short(-20),
            "FallDistance": Float(0),
            "SelectedItemSlot": Int(0),
            "playerGameType": Int(MODES[self.gamemode]),
            "Inventory": List[Compound]([
                Compound({
                    "Slot": Byte(item["slot"]),
                    "id": String("minecraft:" + item["item"].removeprefix("minecraft:")),
                    "Count": Byte(item["count"]),
                    **({"tag": Compound({"Damage": Int(item["damage"])})} if "damage" in item else {}),
                })
                for item in self.inventory
            ]),
            "active_effects": List[Compound]([
                Compound({"id": String(effect["id"]), "amplifier": Byte(effect["amplifier"]),
                          "duration": Int(effect["duration"]), "ambient": Byte(0),
                          "show_particles": Byte(1), "show_icon": Byte(1)})
                for effect in self.effects
            ]),
        })

    def write(self, world: Path, player_uuid: UUID, *, replace: bool = False) -> None:
        directory = world / "playerdata"
        directory.mkdir(exist_ok=True)
        target = directory / f"{player_uuid}.dat"
        if target.exists() and not replace:
            raise FileExistsError(f"Player data already exists: {target}")
        nbtlib.File(self.nbt(player_uuid), gzipped=True).save(target)

    def verify(self, actual: Compound, player_uuid: UUID) -> None:
        expected = self.nbt(player_uuid)
        if "UUID" not in actual or list(actual["UUID"]) != list(expected["UUID"]):
            raise RuntimeError("Player initialization verification failed: UUID")
        for key in ("Dimension", "playerGameType", "foodLevel", "XpLevel", "SelectedItemSlot"):
            if actual.get(key) != expected[key]:
                raise RuntimeError(f"Player initialization verification failed: {key}")
        for key in ("Health", "foodSaturationLevel", "foodExhaustionLevel", "XpP"):
            if key not in actual or not math.isclose(float(actual[key]), float(expected[key]), abs_tol=1e-4):
                raise RuntimeError(f"Player initialization verification failed: {key}")
        for key in ("Pos", "Rotation"):
            if key not in actual or len(actual[key]) != len(expected[key]) or any(
                not math.isclose(
                    (float(a) - float(b) + 180) % 360 - 180
                    if key == "Rotation" and index == 0 else float(a) - float(b),
                    0, abs_tol=1e-3, rel_tol=0,
                )
                for index, (a, b) in enumerate(zip(actual[key], expected[key]))
            ):
                raise RuntimeError(
                    f"Player initialization verification failed: {key}; "
                    f"expected {expected[key]}, observed {actual.get(key)}"
                )
        inventory = actual.get("Inventory", [])
        observed = sorted((int(item["Slot"]), str(item["id"]), int(item["Count"])) for item in inventory)
        requested = sorted((int(item["Slot"]), str(item["id"]), int(item["Count"])) for item in expected["Inventory"])
        if observed != requested:
            raise RuntimeError("Player initialization verification failed: Inventory")
        observed_wear = {int(item["Slot"]): int(item.get("tag", {}).get("Damage", 0))
                         for item in inventory}
        requested_wear = {item["slot"]: item.get("damage", 0) for item in self.inventory}
        if observed_wear != requested_wear:
            raise RuntimeError("Player initialization verification failed: Inventory damage")
        observed_effects = sorted(
            (str(row["id"]), int(row.get("amplifier", 0)), int(row["duration"]))
            for row in actual.get("active_effects", [])
        )
        requested_effects = sorted(
            (row["id"], row["amplifier"], row["duration"]) for row in self.effects
        )
        # Native players still tick while the world is frozen for client readiness.
        if (len(observed_effects) != len(requested_effects)
                or any(
                    observed[:2] != requested[:2]
                    or (observed[2] != -1 if requested[2] == -1
                        else not 0 < observed[2] <= requested[2])
                    for observed, requested in zip(observed_effects, requested_effects)
                )):
            raise RuntimeError("Player initialization verification failed: active_effects")
