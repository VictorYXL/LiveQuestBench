"""Focused native-evidence checks for the stage-one additions."""

import json
from uuid import uuid4

import nbtlib
import pytest

from game.minecraft.evaluators.raid import HERO, evaluate_raid
from game.minecraft.evaluators.workshop import evaluate_workshop
from game.minecraft.fixtures.workshop_orders import SCHEMA, expected_hashes, order_pack
from game.minecraft.init_player_state import PlayerState


def test_initial_effects_roundtrip_and_reject_missing_native_effect():
    player = uuid4()
    state = PlayerState(position=(0, 72, 0), effects=[
        {"id": "minecraft:bad_omen", "amplifier": 0, "duration": -1},
    ])
    native = state.nbt(player)
    state.verify(native, player)
    native["active_effects"] = nbtlib.List[nbtlib.Compound]([])
    with pytest.raises(RuntimeError, match="active_effects"):
        state.verify(native, player)
    with pytest.raises(ValueError, match="bounded"):
        PlayerState(position=(0, 72, 0), effects=[
            {"id": "minecraft:bad_omen", "amplifier": 0, "duration": True},
        ])


def test_raid_requires_fresh_advancement_and_native_win(tmp_path):
    player = uuid4()
    before, after = tmp_path / "before", tmp_path / "after"
    for path in (before, after):
        path.mkdir()
        PlayerState(position=(0, 72, 0)).write(path, player)
    assert not evaluate_raid(before, after, player, min_food=0)["success"]
    (after / "advancements").mkdir()
    advance = after / "advancements" / f"{player}.json"
    data = {"DataVersion": 3700, HERO: {
        "done": True, "criteria": {"hero_of_the_village": "2026-10-27 00:00:00 +0000"}}}
    advance.write_text(json.dumps(data))
    assert not evaluate_raid(before, after, player, min_food=0)["success"]
    (after / "stats").mkdir()
    (after / "stats" / f"{player}.json").write_text(json.dumps({
        "DataVersion": 3700, "stats": {"minecraft:custom": {"minecraft:raid_win": 1}}}))
    assert evaluate_raid(before, after, player, min_food=0)["success"]
    (before / "advancements").mkdir()
    (before / "advancements" / f"{player}.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="earlier raid"):
        evaluate_raid(before, after, player, min_food=0)


def test_workshop_milestones_bind_player_and_preserve_unordered_production(tmp_path):
    player = uuid4()
    parts = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    for label, tick, orders in (("before", 100, []), ("after", 200, [2, 1, 4, 3])):
        world = tmp_path / label
        world.mkdir()
        PlayerState(position=(0, 72, 0)).write(world, player)
        nbtlib.File({"Data": nbtlib.Compound({"Time": nbtlib.Long(tick)})},
                    gzipped=True).save(world / "level.dat")
        for name, value in order_pack().items():
            path = world / "datapacks/livequest_workshop" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + "\n")
        (world / "livequest-workshop-evidence.json").write_text(json.dumps({
            "schema": SCHEMA, "pack_sha256": expected_hashes()}))
        (world / "data").mkdir()
        storage = nbtlib.File({
            "DataVersion": nbtlib.Int(3700), "data": nbtlib.Compound({
                "contents": nbtlib.Compound({"workshop": nbtlib.Compound({
                    "schema": nbtlib.String(SCHEMA),
                    "events": nbtlib.List[nbtlib.Compound]([
                        nbtlib.Compound({"order": nbtlib.Int(order), "tick": nbtlib.Long(150),
                                         "player": nbtlib.IntArray(parts)})
                        for order in orders]),
                })}),
            }),
        }, gzipped=True)
        storage.save(world / "data/command_storage_livequest.dat")
    assert evaluate_workshop(tmp_path / "before", tmp_path / "after", player, min_food=0)["success"]
    with pytest.raises(ValueError, match="identity"):
        evaluate_workshop(tmp_path / "before", tmp_path / "after", uuid4(), min_food=0)
