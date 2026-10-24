"""ST state, ordinary player tools and cancellation without an online account."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

nbtlib = pytest.importorskip("nbtlib", reason="Install the minecraft extra")
pytest.importorskip("Xlib", reason="Install the minecraft extra")
pytest.importorskip("PIL", reason="Install the minecraft extra")

from game.minecraft.evaluators.inventory import evaluate_inventory
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.structured_tools.interface import StructuredInterface, agent_tools


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in ST check")
def test_st_observation_and_tools(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool, minecraft_world_path: Path,
) -> None:
    root = Path(os.environ.get(
        "MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[3] / "output" / "test"),
    )).resolve()
    output = root / f"minecraft-st-{uuid4().hex}"
    print(f"Minecraft ST artifacts: {output}")
    monkeypatch.setenv("MINECRAFT_PRISM_ROOT", str(output / "no-prism-or-accounts"))
    game = MinecraftGame(
        track="structured_tool", output_dir=output,
        recording=recording, recording_fps=10,
        headless=headless,
        world_path=minecraft_world_path,
        player_state=PlayerState(position=(0.5, 72, 0.5), yaw=180,
                                 inventory=[{"slot": 0, "item": "oak_log", "count": 1}]),
    )

    async def run() -> None:
        try:
            await game.start()
            interface = game.get_agent_interface()
            assert isinstance(interface, StructuredInterface)
            with pytest.raises(RuntimeError):
                await interface.observe()
            before = await game.save_snapshot(output / "before")
            await game.begin()
            await asyncio.sleep(1)
            move_tool = next(tool for tool in agent_tools() if tool.name == "MoveTool")
            rejected = json.loads(await move_tool.execute(interface, {"direction": "forward", "duration": 11}))
            assert rejected["error"] == "invalid_tool_arguments" and rejected["executed"] is False
            initial = await interface.observe()
            assert initial["health"] == 20 and initial["position"] is not None
            assert initial["profile"] == "minecraft-1.20.4-st-native-v5"
            assert initial["nearby_blocks"]["dims"] == {"x": 31, "y": 31, "z": 31}
            assert len(initial["nearby_blocks"]["data"]) == 31 ** 3
            assert any(item["name"] == "oak_log" and item["count"] == 1 for item in initial["inventory"])
            recipes = await interface.call_tool("QueryCraftRecipeTool", {"output_item": "oak_planks"})
            assert any(recipe["craftable"] for recipe in recipes["recipes"])
            craft = await interface.call_tool("CraftItemTool", {"output_item": "oak_planks", "count": 1})
            assert craft["success"], craft
            dig = await interface.call_tool("DigTool", {"x": 1, "y": 71, "z": 0})
            assert dig["success"], dig
            assert dig["payload"]["after_name"] == "air"
            move = json.loads(await move_tool.execute(interface, {"direction": "backward", "duration": 0.5}))
            assert move["success"], move
            current = await interface.observe()
            assert current["captured_at_ns"] > initial["captured_at_ns"]
            assert sum((current["position"][axis] - initial["position"][axis]) ** 2 for axis in ("x", "y", "z")) > 0.01
            await asyncio.sleep(1)
            active = asyncio.ensure_future(interface.call_tool("MoveTool", {"direction": "backward", "duration": 10}))
            await asyncio.sleep(0.2)
            assert not active.done()
            await asyncio.wait_for(game.end(), timeout=5)
            assert active.cancelled()
            with pytest.raises(RuntimeError):
                await interface.observe()
            with pytest.raises(RuntimeError):
                await interface.call_tool("SelectTool", {"slot": 2})
            after = await game.save_snapshot(output / "after")
            assert game.player_uuid is not None
            assert {path.stem for path in (after / "playerdata").glob("*.dat")} == {str(game.player_uuid)}
            assert evaluate_inventory(before, after, game.player_uuid, [
                {"item": "oak_planks", "min_count": 4},
            ])["success"]
        finally:
            await game.close()
        await game.close()
        if game.recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )

    asyncio.run(run())


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in furnace UI check")
def test_native_furnace_slots_and_residual_fuel(headless: bool, recording: bool) -> None:
    root = Path(os.environ.get("MINECRAFT_TEST_OUTPUT", "output/test"))
    output = root / f"minecraft-furnace-{uuid4().hex}"
    game = MinecraftGame(
        track="structured_tool", output_dir=output,
        world_path=Path("config/minecraft/fixtures/workshop").resolve(),
        headless=headless, recording=recording,
        player_state=PlayerState(position=(.5, 72, .5), inventory=[
            {"slot": 0, "item": "coal", "count": 2},
            {"slot": 1, "item": "raw_iron", "count": 1},
            {"slot": 2, "item": "beef", "count": 1},
        ]),
    )

    async def run() -> None:
        try:
            await game.start()
            before = await game.save_snapshot(output / "before")
            await game.begin()
            public = game.get_agent_interface()
            assert not (await public.call_tool("FurnaceClickTool", {
                "slot": 0, "button": "left", "operation": "pickup",
            }))["success"]
            await public.call_tool("LookAtPositionTool", {"x": 1.5, "y": 72.5, "z": 2.5})

            async def inspect():
                result = await public.call_tool("InspectFurnaceTool", {})
                assert result["success"], result
                assert len(result["payload"]["slots"]) == 39
                assert 0 <= result["payload"]["cook_progress"] <= 1
                assert 0 <= result["payload"]["fuel_progress"] <= 1
                return result["payload"]

            async def click(slot, button="left", operation="pickup"):
                result = await public.call_tool("FurnaceClickTool", {
                    "slot": slot, "button": button, "operation": operation,
                })
                assert result["success"] and result["payload"]["click_submitted"], result
                return result["payload"]

            async def slot_for(name):
                state = await inspect()
                return next(row["slot"] for row in state["slots"][3:]
                            if row["item"] is not None and row["item"]["name"] == name)

            async def cooked(name):
                for _ in range(150):
                    state = await inspect()
                    item = state["slots"][2]["item"]
                    if item is not None and item["name"] == name:
                        return state
                    await asyncio.sleep(.2)
                raise AssertionError(f"Native furnace did not produce {name}")

            coal = await slot_for("coal")
            await click(coal)
            await click(1, "right")
            state = await click(coal)
            assert state["cursor"] is None and state["slots"][1]["item"]["count"] == 1
            await click(await slot_for("raw_iron"))
            await click(0)
            assert (await cooked("iron_ingot"))["burning"]
            await click(2, operation="quick_move")
            await click(await slot_for("beef"))
            await click(0)
            state = await cooked("cooked_beef")
            assert state["burning"] and state["slots"][1]["item"] is None
            assert 0 < state["fuel_progress"] < 1
            await click(2, operation="quick_move")
            await game.end()
            after = await game.save_snapshot(output / "after")
            assert evaluate_inventory(before, after, game.player_uuid, [
                {"item": "iron_ingot", "min_count": 1},
                {"item": "cooked_beef", "min_count": 1},
                {"item": "coal", "min_count": 1},
            ])["success"]
        finally:
            await game.close()
        if recording:
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(game.recording_path),
                            "-map", "0:v:0", "-f", "null", "-"],
                           check=True, capture_output=True, timeout=60)

    asyncio.run(run())


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in native trading check")
def test_native_trade_refusal_and_cutoff(headless: bool, recording: bool) -> None:
    from benchmark.config import load_task

    repository = Path(__file__).resolve().parents[3]
    task = load_task(repository / "config/minecraft/tasks/structured_tools/trade_outposts_return.yaml")
    root = Path(os.environ.get("MINECRAFT_TEST_OUTPUT", "output/test"))
    game = MinecraftGame(
        track="structured_tool", output_dir=root / f"minecraft-trade-{uuid4().hex}",
        world_path=Path(task.fixture["world_path"]), headless=headless, recording=recording,
        player_state=PlayerState.from_dict(task.fixture["player_state"]),
    )

    async def run() -> None:
        try:
            await game.start()
            await game.begin()
            public = game.get_agent_interface()
            assert (await public.call_tool("GoToPositionTool", {"x": 8, "y": 72, "z": 2}))["success"]
            await public.call_tool("LookAtPositionTool", {"x": 8.5, "y": 73.4, "z": 4.5})
            shop = await public.call_tool("InspectMerchantTool", {})
            assert shop["success"], shop
            axe = next(o for o in shop["payload"]["offers"] if o["sell"]["name"] == "iron_axe")
            refused = await public.call_tool("TradeTool", {
                "offer_index": axe["offer_index"], "quote": axe["quote"], "slot": 6,
            })
            assert not refused["success"]
            shop = await public.call_tool("InspectMerchantTool", {})
            assert shop["payload"]["cursor"] is None
            assert sum(i["count"] for i in shop["payload"]["payment_slots"]
                       if i is not None and i["name"] == "emerald") == 2
            await public.call_tool("StopTool", {})
            observed = await public.observe()
            assert sum(i["count"] for i in observed["inventory"] if i["name"] == "emerald") == 2
            await public.call_tool("LookAtPositionTool", {"x": 8.5, "y": 73.4, "z": 4.5})
            shop = await public.call_tool("InspectMerchantTool", {})
            old_screen = await public.call_tool("TradeTool", {
                "offer_index": axe["offer_index"], "quote": axe["quote"], "slot": 6,
            })
            assert not old_screen["success"]
            sale = next(o for o in shop["payload"]["offers"] if o["buy"]["name"] == "coal")
            active = asyncio.create_task(public.call_tool("TradeTool", {
                "offer_index": sale["offer_index"], "quote": sale["quote"], "slot": 4,
            }))
            await asyncio.sleep(.1)
            assert not active.done()
            await asyncio.wait_for(game.end(), timeout=5)
            assert active.cancelled()
        finally:
            await game.close()

    asyncio.run(run())


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in held-item check")
def test_native_food_use_and_cutoff(headless: bool, minecraft_world_path: Path) -> None:
    root = Path(os.environ.get("MINECRAFT_TEST_OUTPUT", "output/test"))
    game = MinecraftGame(
        track="structured_tool", output_dir=root / f"minecraft-use-{uuid4().hex}",
        world_path=minecraft_world_path, headless=headless,
        player_state=PlayerState(position=(.5, 72, .5), food=10, saturation=0,
                                 inventory=[{"slot": 0, "item": "bread", "count": 3}]),
    )

    async def run() -> None:
        try:
            await game.start()
            await game.begin()
            public = game.get_agent_interface()
            rejected = await public.call_tool("AttackTool", {})
            assert not rejected["success"]
            before = await public.observe()
            used = await public.call_tool("UseHeldItemTool", {"duration": 2})
            assert used["success"], used
            after = await public.observe()
            assert after["hunger"] > before["hunger"]
            assert next(item["count"] for item in after["inventory"] if item["name"] == "bread") == 2
            active = asyncio.create_task(public.call_tool("UseHeldItemTool", {"duration": 5}))
            await asyncio.sleep(.2)
            await asyncio.wait_for(game.end(), timeout=5)
            assert active.cancelled()
            with pytest.raises(RuntimeError):
                await public.call_tool("UseHeldItemTool", {"duration": .1})
        finally:
            await game.close()

    asyncio.run(run())
