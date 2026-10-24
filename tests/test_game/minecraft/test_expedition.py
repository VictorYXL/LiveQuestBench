"""Counterexamples for native preparation/kill evidence and a same-life return."""

import json
from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators.expedition import evaluate_expedition, verify_initial
from game.minecraft.fixtures.forge_hunt import SCHEMA, TARGET, pack_files, pack_hashes, uuid_parts
from game.minecraft.structured_tools.interface import BASE_TOOLS, validate_tool


PLAYER = UUID("00000000-0000-0000-0000-000000000001")


def write_evidence(world, kills):
    record = nbtlib.Compound({
        "state": nbtlib.Compound({"schema": nbtlib.String(SCHEMA), "target": nbtlib.String(str(TARGET))}),
        "kills": nbtlib.List[nbtlib.Compound](kills),
    })
    (world / "data").mkdir(exist_ok=True)
    nbtlib.File({
        "DataVersion": nbtlib.Int(3700),
        "data": nbtlib.Compound({"contents": nbtlib.Compound({"expedition": record})}),
    }, gzipped=True).save(world / "data/command_storage_livequest.dat")


@pytest.fixture
def pair(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    for world in (before, after):
        world.mkdir()
        for name, value in pack_files().items():
            file = world / "datapacks/livequest_forge" / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(value if isinstance(value, str) else json.dumps(value))
        (world / "livequest-expedition.json").write_text(json.dumps({
            "schema": SCHEMA, "target_uuid": str(TARGET), "target_type": "minecraft:husk",
            "target_position": [28.5, 72, .5], "return_position": [.5, 72, .5],
            "pack_sha256": pack_hashes(world),
        }))
        (world / "livequest-opening.json").write_text(json.dumps({
            "target_uuid": str(TARGET), "health": 20, "player_uuid": str(PLAYER),
        }))
        write_evidence(world, [])
    (after / "playerdata").mkdir()
    nbtlib.File({
        "DataVersion": nbtlib.Int(3700), "UUID": nbtlib.IntArray(uuid_parts(PLAYER)),
        "Pos": nbtlib.List[nbtlib.Double]([.5, 72, .5]),
        "Motion": nbtlib.List[nbtlib.Double]([0, 0, 0]), "Health": nbtlib.Float(20),
        "OnGround": nbtlib.Byte(1), "Dimension": nbtlib.String("minecraft:overworld"),
    }, gzipped=True).save(after / "playerdata" / f"{PLAYER}.dat")
    return before, after


def kill(**changes):
    values = {
        "role": nbtlib.String("sentinel"), "player": nbtlib.IntArray(uuid_parts(PLAYER)),
        "tick": nbtlib.Long(123), "stone": nbtlib.Int(1), "iron": nbtlib.Int(0),
        "hand": nbtlib.String("minecraft:stone_sword"),
    }
    return nbtlib.Compound(values | changes)


def test_crafted_type_and_held_weapon_are_both_required(pair):
    before, after = pair
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    write_evidence(after, [kill()])
    assert evaluate_expedition(before, after, PLAYER)["success"]
    for event in (kill(stone=nbtlib.Int(0)), kill(hand=nbtlib.String("minecraft:iron_sword"))):
        write_evidence(after, [event])
        assert not evaluate_expedition(before, after, PLAYER)["success"]
    write_evidence(after, [kill(hand=nbtlib.String("minecraft:iron_sword"), iron=nbtlib.Int(1))])
    assert evaluate_expedition(before, after, PLAYER)["success"]


@pytest.mark.parametrize("events", [
    [kill(), kill()], [kill(player=nbtlib.IntArray([0, 0, 0, 2]))],
    [kill(role=nbtlib.String("other"))], [kill(stone=nbtlib.Int(-1))],
])
def test_bad_identity_duplicate_and_invalid_counts_are_not_game_failures(pair, events):
    before, after = pair
    write_evidence(after, events)
    with pytest.raises(ValueError):
        evaluate_expedition(before, after, PLAYER)


@pytest.mark.parametrize("field,value", [
    ("Health", nbtlib.Float(0)), ("OnGround", nbtlib.Byte(0)),
    ("Dimension", nbtlib.String("minecraft:the_nether")),
    ("Pos", nbtlib.List[nbtlib.Double]([3, 72, .5])),
    ("Pos", nbtlib.List[nbtlib.Double]([.5, 73, .5])),
    ("Motion", nbtlib.List[nbtlib.Double]([.11, 0, 0])),
])
def test_combat_cannot_override_living_settled_return(pair, field, value):
    before, after = pair
    write_evidence(after, [kill()])
    file = after / "playerdata" / f"{PLAYER}.dat"
    native = nbtlib.load(file)
    native[field] = value
    native.save(file)
    assert not evaluate_expedition(before, after, PLAYER)["success"]


def test_respawn_is_not_a_successful_return(pair):
    before, after = pair
    write_evidence(after, [kill()])
    (after / "stats").mkdir()
    (after / "stats" / f"{PLAYER}.json").write_text(json.dumps({
        "DataVersion": 3700, "stats": {"minecraft:custom": {"minecraft:deaths": 1}},
    }))
    assert not evaluate_expedition(before, after, PLAYER)["success"]


def test_fresh_target_and_unchanged_datapack_are_mandatory(pair):
    before, after = pair
    write_evidence(before, [kill()])
    with pytest.raises(ValueError):
        verify_initial(before, PLAYER)
    write_evidence(before, [])
    opening = before / "livequest-opening.json"
    saved = opening.read_text()
    opening.write_text(saved.replace('"health": 20', '"health": 0'))
    with pytest.raises(ValueError):
        verify_initial(before, PLAYER)
    opening.write_text(saved)
    pack = after / "datapacks/livequest_forge/pack.mcmeta"
    pack.write_text("{}")
    with pytest.raises(ValueError):
        evaluate_expedition(before, after, PLAYER)


def test_new_combat_tools_are_bounded_and_legacy_defaults_unchanged():
    assert "AttackTool" not in BASE_TOOLS and "UseHeldItemTool" not in BASE_TOOLS
    validate_tool("AttackTool", {})
    validate_tool("UseHeldItemTool", {"duration": 5})
    for name, arguments in (
        ("AttackTool", {"target_uuid": str(TARGET)}),
        ("UseHeldItemTool", {"duration": 5.1}), ("UseHeldItemTool", {"duration": True}),
    ):
        with pytest.raises(ValueError):
            validate_tool(name, arguments)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_invalid_opening_health_is_an_evidence_error(pair, value):
    before, _ = pair
    opening = before / "livequest-opening.json"
    record = json.loads(opening.read_text())
    record["health"] = value
    opening.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verify_initial(before, PLAYER)
