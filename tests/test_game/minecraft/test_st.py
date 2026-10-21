"""ST state, ordinary player tools and cancellation without an online account."""

import asyncio
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
from game.minecraft.structured_tools.interface import StructuredInterface


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in ST check")
def test_st_observation_and_tools(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool,
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
        fixture=Path(os.environ["MINECRAFT_TEST_FIXTURE"]) if os.environ.get("MINECRAFT_TEST_FIXTURE") else None,
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
            initial = await interface.observe()
            assert initial["health"] == 20 and initial["position"] is not None
            assert initial["profile"] == "minecraft-1.20.4-st-native-v2"
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
            move = await interface.call_tool("MoveTool", {"direction": "backward", "duration": 0.5})
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
                {"item": "oak_planks", "min_count": 4, "min_delta": 4},
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
