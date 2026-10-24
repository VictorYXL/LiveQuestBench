"""Counterexamples for native preparation/kill evidence and a same-life return."""

import json
from pathlib import Path
from uuid import UUID

import nbtlib
import pytest

from game.minecraft.evaluators.expedition import evaluate_expedition, verify_initial
from game.minecraft.fixtures.forge_hunt import OUTPOST_SCHEMA, SCHEMA, TARGET, pack_files, pack_hashes, route_gates, targets_for, uuid_parts
from game.minecraft.fixtures import lost_expedition, trade_hunt
from game.minecraft.structured_tools.interface import BASE_TOOLS, EXPEDITION_TOOLS, validate_tool


PLAYER = UUID("00000000-0000-0000-0000-000000000001")


def test_lost_expedition_is_paired_goal_level_and_preserves_native_dependencies():
    from benchmark.config import load_task
    from game.minecraft.evaluators.world import read_blocks

    root = Path(__file__).resolve().parents[3]
    st, vm = [load_task(root / f"config/minecraft/tasks/{track}/lost_expedition.yaml")
              for track in ("structured_tools", "visual_motor")]
    assert st.task == vm.task and st.fixture == vm.fixture
    assert st.time_limit_seconds == vm.time_limit_seconds == 3600
    assert st.fixture["player_state"]["inventory"] == [{"slot": 0, "item": "bread", "count": 2}]
    assert "GoToPositionTool" not in st.tools
    assert {"InspectMerchantTool", "TradeTool", "PlaceTool", "DigTool"} <= set(st.tools)
    assert "X76" not in st.task and "X-60" not in st.task and "diamond_pickaxe" not in st.task
    blocks = read_blocks(Path(st.fixture["world_path"]), (72, 69, -64), (80, 77, -56),
                         "minecraft:overworld")
    for (x, y, z), block in blocks.items():
        inside = 75 <= x <= 77 and 72 <= y <= 74 and -61 <= z <= -59
        assert inside or block == "minecraft:obsidian"
    assert blocks[(76, 72, -60)] == "minecraft:chest"
    setup = lost_expedition.commands()
    assert "gamerule doMobSpawning true" in setup and "gamerule doDaylightCycle true" in setup
    assert all(any(f'livequest_folio: "{folio}"' in line for line in setup) for folio in lost_expedition.FOLIOS)


def write_evidence(world, kills, schema=SCHEMA, purchases=None):
    record = nbtlib.Compound({
        "state": nbtlib.Compound({"schema": nbtlib.String(schema), "target": nbtlib.String(str(TARGET))}),
        "kills": nbtlib.List[nbtlib.Compound](kills),
    })
    if purchases is not None:
        record["purchases"] = nbtlib.List[nbtlib.Compound](purchases)
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
    assert "StrikeTool" not in BASE_TOOLS
    validate_tool("StrikeTool", {"x": 1, "y": 72, "z": 0})
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


@pytest.fixture
def outpost_pair(pair):
    before, after = pair
    for world in pair:
        for name, value in pack_files(2).items():
            file = world / "datapacks/livequest_forge" / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(value if isinstance(value, str) else json.dumps(value))
        path = world / "livequest-expedition.json"
        value = json.loads(path.read_text())
        value.update(schema=OUTPOST_SCHEMA, targets=targets_for(2), cargo="outpost_records",
                     pack_sha256=pack_hashes(world, 2))
        path.write_text(json.dumps(value))
        path = world / "livequest-opening.json"
        value = json.loads(path.read_text())
        value["targets"] = targets_for(2)
        path.write_text(json.dumps(value))
        write_evidence(world, [], OUTPOST_SCHEMA)
    (before / "playerdata").mkdir()
    nbtlib.File({"Inventory": nbtlib.List[nbtlib.Compound]([])}, gzipped=True).save(
        before / "playerdata" / f"{PLAYER}.dat")
    player_file = after / "playerdata" / f"{PLAYER}.dat"
    player = nbtlib.load(player_file)
    player["Inventory"] = nbtlib.List[nbtlib.Compound]([])
    player.save(player_file)
    return pair


def test_two_outposts_require_both_native_kills_and_authored_cargo(outpost_pair):
    before, after = outpost_pair
    player_file = after / "playerdata" / f"{PLAYER}.dat"
    player = nbtlib.load(player_file)
    kills = [kill(), kill(role=nbtlib.String("spider"))]
    write_evidence(after, kills, OUTPOST_SCHEMA)
    result = evaluate_expedition(before, after, PLAYER)
    assert result["checks"][0]["passed"] and not result["success"]
    paper = nbtlib.Compound({"id": nbtlib.String("minecraft:paper"), "Count": nbtlib.Byte(1)})
    player["Inventory"].append(paper)
    player.save(player_file)
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    paper["tag"] = nbtlib.Compound({"livequest_cargo": nbtlib.String("outpost_records")})
    player.save(player_file)
    assert evaluate_expedition(before, after, PLAYER)["success"]
    write_evidence(after, kills[:1], OUTPOST_SCHEMA)
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    write_evidence(after, [kill(), kill()], OUTPOST_SCHEMA)
    with pytest.raises(ValueError):
        evaluate_expedition(before, after, PLAYER)


def test_reconnaissance_requires_matching_native_opening(outpost_pair):
    before, after = outpost_pair
    for world in (before, after):
        path = world / "livequest-expedition.json"
        value = json.loads(path.read_text())
        value.update(route_condition=0, route_gates=route_gates(0))
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="passage validation"):
        verify_initial(before, PLAYER)
    path = before / "livequest-opening.json"
    value = json.loads(path.read_text())
    value["route_gates"] = route_gates(0)
    path.write_text(json.dumps(value))
    verify_initial(before, PLAYER)
    value["route_gates"] = route_gates(1)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="passage validation"):
        verify_initial(before, PLAYER)
    for invalid in (True, 2, -1, "0"):
        with pytest.raises(ValueError):
            route_gates(invalid)


def test_trade_tools_are_opt_in_and_require_an_observed_quote():
    from game.minecraft.structured_tools.interface import TRADING_TOOLS

    assert "TradeTool" not in BASE_TOOLS and "TradeTool" not in EXPEDITION_TOOLS
    assert "TradeTool" in TRADING_TOOLS
    assert all("FurnaceClickTool" not in defaults and "InspectFurnaceTool" not in defaults
               for defaults in (BASE_TOOLS, EXPEDITION_TOOLS, TRADING_TOOLS))
    click = {"slot": 0, "button": "right", "operation": "pickup"}
    validate_tool("FurnaceClickTool", click)
    for changes in ({"slot": 39}, {"slot": True}, {"button": "middle"}, {"operation": "clone"}):
        with pytest.raises(ValueError):
            validate_tool("FurnaceClickTool", click | changes)
    validate_tool("InspectMerchantTool", {})
    validate_tool("TradeTool", {"offer_index": 0, "quote": "observed-quote", "slot": 3})
    for changes in ({"slot": 10}, {"slot": True}, {"quote": ""}, {"offer_index": -1}, {"count": 2}):
        with pytest.raises(ValueError):
            validate_tool("TradeTool", {"offer_index": 0, "quote": "observed-quote", "slot": 3} | changes)


def test_lost_expedition_requires_distinct_folios_but_not_a_prescribed_weapon(pair):
    before, after = pair
    for world in pair:
        path = world / "livequest-expedition.json"
        value = json.loads(path.read_text())
        value.update(schema=lost_expedition.SCHEMA, targets=lost_expedition.TARGETS,
                     merchants=lost_expedition.MERCHANTS, folios=list(lost_expedition.FOLIOS))
        path.write_text(json.dumps(value))
        path = world / "livequest-opening.json"
        value = json.loads(path.read_text())
        value.update(targets=lost_expedition.TARGETS, merchants=lost_expedition.MERCHANTS)
        path.write_text(json.dumps(value))
        write_evidence(world, [], lost_expedition.SCHEMA)
    (before / "playerdata").mkdir()
    nbtlib.File({"Inventory": nbtlib.List[nbtlib.Compound]([])}, gzipped=True).save(
        before / "playerdata" / f"{PLAYER}.dat")
    path = after / "playerdata" / f"{PLAYER}.dat"
    player = nbtlib.load(path)
    player["Inventory"] = nbtlib.List[nbtlib.Compound]([])
    player.save(path)
    write_evidence(after, [kill(hand=nbtlib.String("minecraft:iron_axe"), stone=nbtlib.Int(0))],
                   lost_expedition.SCHEMA)
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    for folio in lost_expedition.FOLIOS:
        player["Inventory"].append(nbtlib.Compound({
            "id": nbtlib.String("minecraft:paper"), "Count": nbtlib.Byte(1),
            "tag": nbtlib.Compound({"livequest_folio": nbtlib.String(folio)}),
        }))
    player.save(path)
    assert evaluate_expedition(before, after, PLAYER)["success"]
    player["Inventory"][2]["tag"]["livequest_folio"] = nbtlib.String(lost_expedition.FOLIOS[0])
    player["Inventory"][0]["Count"] = nbtlib.Byte(3)
    player.save(path)
    assert not evaluate_expedition(before, after, PLAYER)["success"]


def test_native_purchase_identity_and_order_gate_the_combat_chain(outpost_pair):
    before, after = outpost_pair
    for world in outpost_pair:
        for name, value in trade_hunt.pack_files().items():
            path = world / "datapacks/livequest_forge" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value))
        path = world / "livequest-expedition.json"
        value = json.loads(path.read_text())
        value.update(schema=trade_hunt.SCHEMA, merchants=trade_hunt.MERCHANTS,
                     pack_sha256=trade_hunt.pack_hashes(world))
        path.write_text(json.dumps(value))
        path = world / "livequest-opening.json"
        value = json.loads(path.read_text())
        value["merchants"] = trade_hunt.MERCHANTS
        path.write_text(json.dumps(value))
        write_evidence(world, [], trade_hunt.SCHEMA, [])
    path = after / "playerdata" / f"{PLAYER}.dat"
    player = nbtlib.load(path)
    player["Inventory"].append(nbtlib.Compound({
        "id": nbtlib.String("minecraft:paper"), "Count": nbtlib.Byte(1),
        "tag": nbtlib.Compound({"livequest_cargo": nbtlib.String("outpost_records")}),
    }))
    player.save(path)
    purchase = nbtlib.Compound({
        "item": nbtlib.String("minecraft:iron_axe"), "merchant": nbtlib.String(trade_hunt.SMITH),
        "player": nbtlib.IntArray(uuid_parts(PLAYER)), "tick": nbtlib.Long(100), "sequence": nbtlib.Int(1),
    })
    kills = [kill(hand=nbtlib.String("minecraft:iron_axe"), sequence=nbtlib.Int(2)),
             kill(role=nbtlib.String("spider"), hand=nbtlib.String("minecraft:iron_axe"), sequence=nbtlib.Int(3))]
    write_evidence(after, kills, trade_hunt.SCHEMA, [purchase])
    assert evaluate_expedition(before, after, PLAYER)["success"]
    write_evidence(after, kills, trade_hunt.SCHEMA, [])
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    purchase["sequence"] = nbtlib.Int(4)
    write_evidence(after, kills, trade_hunt.SCHEMA, [purchase])
    assert not evaluate_expedition(before, after, PLAYER)["success"]
    purchase["sequence"] = nbtlib.Int(1)
    purchase["merchant"] = nbtlib.String(trade_hunt.FARMER)
    write_evidence(after, kills, trade_hunt.SCHEMA, [purchase])
    with pytest.raises(ValueError):
        evaluate_expedition(before, after, PLAYER)
    purchase["merchant"] = nbtlib.String(trade_hunt.SMITH)
    kills[1]["sequence"] = kills[0]["sequence"]
    write_evidence(after, kills, trade_hunt.SCHEMA, [purchase])
    with pytest.raises(ValueError):
        evaluate_expedition(before, after, PLAYER)
