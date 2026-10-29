import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import nbtlib

from game.minecraft.evaluators.cargo import cargo_count
from game.minecraft.evaluators import camel_delivery as scorer
from game.minecraft.evaluators.camel_delivery import endpoint_checks, verify_initial_materials
from game.minecraft.fixtures.camel_delivery import commands, policy
from game.minecraft.fixtures import camel_delivery_flush_v4 as flush_v4
from scripts import prove_camel_delivery as runner
from scripts.prove_camel_delivery import aim_furnace


def test_native_variants_differ_only_in_original_movement_attribute():
    first, second = commands(0), commands(1)
    differences = [(a, b) for a, b in zip(first, second) if a != b]
    assert len(differences) == 1
    assert differences[0][0].startswith("summon camel ")
    assert "minecraft:generic.movement_speed" in differences[0][0]


def test_native_depot_contains_distinct_original_parcels_without_a_harvestable_chest():
    recipe = commands(0)
    command = next(c for c in recipe if c.startswith("setblock -42 72 3 "))
    depot = nbtlib.parse_nbt(command[command.index("{"):])
    for identifier in ("camel_pad_a", "camel_pad_b"):
        assert cargo_count(depot["Items"], {"id": identifier, "item": "minecraft:clay_ball"}) == 1
    assert not any(" chest" in c for c in recipe)


def test_initial_material_admission_rejects_inherited_bridge_resources(monkeypatch):
    monkeypatch.setattr(scorer, "read_blocks", lambda *args: {(0, 71, 0): "minecraft:grass_block"})
    with pytest.raises(ValueError, match="Unintended initial arena materials"):
        verify_initial_materials(".")


def test_side_strip_cleanup_preserves_live_player_support():
    for command in commands(0):
        words = command.split()
        if words[0] == "fill" and words[-1] == "air":
            x1, y1, z1, x2, y2, z2 = map(int, words[1:7])
            assert not (x1 <= -43 <= x2 and y1 <= 71 <= y2 and z1 <= 1 <= z2)


def test_policy_requires_a_measured_charge_instead_of_a_precalibrated_answer():
    assert policy([{"charge": .5, "distance": 22.613622}]) is None
    result = policy([{"charge": .5, "distance": 22.613622},
                     {"charge": .05, "distance": 7.511373}])
    assert result["charge"] == .05
    assert result["launch_x"] == pytest.approx((-1.511373, 5.488627))
    assert result["predicted_landing_x"] == pytest.approx((6, 13))
    assert policy([]) is None


def test_policy_fits_new_responses_and_respects_the_public_launch_support():
    result = policy([{"charge": .4, "distance": 6.2}])
    assert result["charge"] == .4
    assert result["launch_x"] == pytest.approx((-.2, 6.8))
    result = policy([{"charge": .5, "distance": 4.113953}])
    assert result["launch_x"] == (.5, 7.5)
    assert policy([{"charge": .05, "distance": 1.87497}]) is None


def test_policy_rejects_invalid_measurements():
    for distance in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            policy([{"charge": .5, "distance": distance}])
    for charge in (0, -.1, .6, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            policy([{"charge": charge, "distance": 6}])


def test_cargo_alone_or_wrong_mount_or_catch_is_not_completion():
    identity = (1, 2, 3, 4)
    camel = {"UUID": identity, "Pos": [13, 72, 22], "Motion": [0, 0, 0],
             "OnGround": 1, "Health": 32}
    player = {"Health": 20}
    assert endpoint_checks(identity, camel, player, [1, 1])["success"]
    for changed in (None, {**camel, "UUID": (4, 3, 2, 1)},
                    {**camel, "Pos": [13, 65, 22]}, {**camel, "OnGround": 0},
                    {**camel, "Motion": [.2, 0, 0]}):
        assert not endpoint_checks(identity, changed, player, [1, 1])["success"]
    assert not endpoint_checks(identity, camel, player, [1, 0])["success"]
    assert not endpoint_checks(identity, camel, {"Health": 0}, [1, 1])["success"]


def test_furnace_aim_uses_public_feedback_after_mounted_rider_offset_changes():
    class Public:
        observations = iter(({"x": 5, "y": 71, "z": 22}, {"x": 5, "y": 72, "z": 23}))

        async def observe(self):
            return {"aimed_node_coords": next(self.observations)}

    calls = []

    async def call(name, **arguments):
        calls.append(name)
        return {"payload": {"slots": []}}

    assert asyncio.run(aim_furnace(Public(), call, (5, 72, 23))) == {"slots": []}
    assert calls == ["LookAtPositionTool", "LookAtPositionTool", "InspectFurnaceTool"]


def authored_block_at(recipe, point):
    result = None
    for command in recipe:
        words = command.split()
        if words[0] == "fill":
            low, high = tuple(map(int, words[1:4])), tuple(map(int, words[4:7]))
            if all(a <= p <= b for a, p, b in zip(low, point, high)):
                result = words[7]
        elif words[0] == "setblock" and tuple(map(int, words[1:4])) == point:
            result = words[4].split("[")[0].split("{")[0]
    return result


@pytest.mark.parametrize("instance", (0, 1))
def test_flush_variant_only_relocates_destination_blocks_not_the_native_task(instance):
    old, new = commands(instance), flush_v4.commands(instance)
    assert len(new) == len(old)
    differences = [(a, b) for a, b in zip(old, new) if a != b]
    assert len(differences) == 2
    for original, revised in differences:
        a, b = original.split(), revised.split()
        assert a[0] == b[0] == "setblock"
        assert a[1] == b[1] and a[3:] == b[3:]
        assert int(b[2]) == int(a[2]) - 1
    for x, y, z in flush_v4.DESTINATIONS:
        assert authored_block_at(old, (x, y + 1, z)) == "furnace"
        assert authored_block_at(new, (x, y + 1, z)) == "air"
        assert authored_block_at(new, (x, y, z)) == "furnace"


def test_flush_variant_keeps_full_supported_pads_without_raised_landing_obstacles():
    recipe = flush_v4.commands(0)
    for left, right, material in ((4, 8, "gold_block"), (11, 15, "emerald_block")):
        floor = [authored_block_at(recipe, (x, 71, z))
                 for x in range(left, right) for z in range(20, 24)]
        assert floor.count(material) == 15
        assert floor.count("furnace") == 1
        assert all(authored_block_at(recipe, (x, y, z)) == "air"
                   for x in range(left, right) for y in (72, 73, 74)
                   for z in range(20, 24))
    for x in (*range(1, 4), *range(8, 11)):
        assert authored_block_at(recipe, (x, 71, 22)) == "air"
        assert authored_block_at(recipe, (x, 67, 22)) == "water"
        assert authored_block_at(recipe, (x, 64, 22)) == "bedrock"


def test_flush_score_reads_flush_destinations_and_preserves_original_cargo_checks(monkeypatch):
    identity = (1, 2, 3, 4)
    camel = {"UUID": identity, "Pos": [13, 72, 22], "Motion": [0, 0, 0],
             "OnGround": 1, "Health": 32}

    def item(identifier):
        return {"Slot": 0, "id": "minecraft:clay_ball", "Count": 1,
                "tag": {"livequest_cargo": identifier}}

    def block_entity(world, point):
        if point == scorer.SOURCE:
            return {"id": "minecraft:furnace", "Items": [item(c) for c in scorer.CARGO]}
        index = flush_v4.DESTINATIONS.index(point)
        return {"id": "minecraft:furnace",
                "Items": [] if world.name == "before" else [item(scorer.CARGO[index])]}

    monkeypatch.setattr(scorer, "verify_initial_materials", lambda world: None)
    monkeypatch.setattr(scorer, "original_camel", lambda world: (identity, camel))
    monkeypatch.setattr(scorer, "entities", lambda world: {identity: camel})
    monkeypatch.setattr(scorer, "read_block_entity", block_entity)
    monkeypatch.setattr(scorer, "read_blocks",
                        lambda world, low, high, dimension: {low: "minecraft:furnace"})
    monkeypatch.setattr(scorer.nbtlib, "load", lambda path: {"Health": 20})
    assert flush_v4.evaluate("before", "after", "player")["success"]
    monkeypatch.setattr(scorer, "read_blocks",
                        lambda world, low, high, dimension: {low: "minecraft:gold_block"})
    assert not flush_v4.evaluate("before", "after", "player")["success"]


@pytest.mark.parametrize("condition", (None, flush_v4.VERSION))
def test_native_runner_keeps_authoring_control_and_scoring_on_the_selected_condition(
    monkeypatch, condition,
):
    output = MagicMock()
    files = {}
    output.__truediv__.side_effect = lambda name: files.setdefault(name, MagicMock())
    game = MagicMock(phase="ready", player_uuid="player")
    game.start = AsyncMock()
    game.begin = AsyncMock(side_effect=lambda: setattr(game, "phase", "running"))
    game.end = AsyncMock(side_effect=lambda: setattr(game, "phase", "ended"))
    game.close = AsyncMock()
    game.save_snapshot = AsyncMock()
    game._session.server.command = AsyncMock(return_value="OK")
    control = AsyncMock(return_value={"controller": "adaptive"})
    score = MagicMock(return_value={"success": True})
    monkeypatch.setattr(runner, "MinecraftGame", lambda **kwargs: game)
    monkeypatch.setattr(runner, "control", control)
    monkeypatch.setattr(runner, "verify_initial_materials", lambda world: None)
    monkeypatch.setattr(runner, "evaluate", score)
    monkeypatch.setattr(flush_v4, "evaluate_native", score)
    kwargs = {} if condition is None else {"condition": condition}
    asyncio.run(runner.run(output, "unused-base", 0, "adaptive", **kwargs))

    flush = condition is not None
    expected_recipe = flush_v4.commands(0) if flush else commands(0)
    assert [call.args[0] for call in game._session.server.command.await_args_list] == expected_recipe
    expected_destinations = flush_v4.DESTINATIONS if flush else scorer.DESTINATIONS
    assert control.await_args.kwargs == {
        "destinations": expected_destinations, "top_face": flush,
    }
    assert score.call_args.kwargs == ({"destinations": expected_destinations} if flush else {})
    expected_goal = flush_v4.PUBLIC_GOAL if flush else runner.PUBLIC_GOAL
    files["public-goal.txt"].write_text.assert_called_once_with(expected_goal + "\n")
    result = json.loads(files["result.json"].write_text.call_args.args[0])
    assert result["condition"] == (condition or "courier-v3")
    assert result["scientific_qualification"] is False


def test_flush_aim_targets_the_public_top_surface_before_opening_native_ui():
    class Public:
        async def observe(self):
            return {"aimed_node_coords": {"x": 5, "y": 71, "z": 23}}

    calls = []

    async def call(name, **arguments):
        calls.append(name)
        if name == "LookAtPositionTool":
            assert arguments == {"x": 5.5, "y": 71.99, "z": 23.5}
        return {"payload": {"slots": []}}

    assert asyncio.run(aim_furnace(Public(), call, (5, 71, 23), top_face=True)) == {"slots": []}
    assert calls == ["LookAtPositionTool", "InspectFurnaceTool"]
