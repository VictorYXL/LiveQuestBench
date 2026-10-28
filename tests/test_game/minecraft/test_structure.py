"""Structure scores from saved Anvil evidence and actual native block placement."""

import asyncio
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4
import zlib

import pytest

nbtlib = pytest.importorskip("nbtlib", reason="Install the minecraft extra")

from game.minecraft.evaluators.structure import evaluate_structure


def test_level_crossing_accepts_detour_but_rejects_blocked_headroom(tmp_path):
    from game.minecraft.evaluators.crossing import evaluate_crossing

    before, after = tmp_path / "before", tmp_path / "after"
    banks = {(0, 0, 0): "stone", (4, 0, 0): "stone"}
    _save_world(before, banks)
    deck = banks | {(x, 0, 1): "oak_planks" for x in range(5)}
    goal = {"region": {"min": [0, 0, 0], "max": [4, 2, 2]},
            "start": [0, 0, 0], "end": [4, 0, 0]}
    _save_world(after, deck)
    assert evaluate_crossing(before, after, **goal)["success"]
    blocked = tmp_path / "blocked"
    _save_world(blocked, deck | {(2, 2, 1): "stone"})
    assert not evaluate_crossing(before, blocked, **goal)["success"]
    assert not evaluate_crossing(after, after, **goal)["success"]


def _save_world(root: Path, blocks: dict[tuple[int, int, int], str]) -> None:
    """Write small real-format chunks with five-bit, padded palette indices."""
    region = root / "region"
    region.mkdir(parents=True)
    nbtlib.File({"Data": nbtlib.Compound({"DataVersion": nbtlib.Int(3700)})}, gzipped=True).save(root / "level.dat")
    names = ["air", "oak_planks", "glass", "stone", "dirt", "sand", "gravel", "granite",
             "andesite", "diorite", "cobblestone", "bedrock", "obsidian", "gold_block",
             "iron_block", "diamond_block", "emerald_block"]
    palette = nbtlib.List[nbtlib.Compound]([
        nbtlib.Compound({"Name": nbtlib.String("minecraft:" + name)}) for name in names
    ])
    for cx in (-1, 0):
        for cz in (-1, 0):
            sections = []
            for sy in (-1, 0):
                words = [0] * 342
                for (x, y, z), name in blocks.items():
                    if (x // 16, y // 16, z // 16) == (cx, sy, cz):
                        index = (y % 16) * 256 + (z % 16) * 16 + x % 16
                        words[index // 12] |= names.index(name) << ((index % 12) * 5)
                sections.append(nbtlib.Compound({
                    "Y": nbtlib.Byte(sy),
                    "block_states": nbtlib.Compound({"palette": palette, "data": nbtlib.LongArray(words)}),
                }))
            chunk = nbtlib.File({
                "DataVersion": nbtlib.Int(3700), "xPos": nbtlib.Int(cx), "zPos": nbtlib.Int(cz),
                "Status": nbtlib.String("minecraft:full"),
                "sections": nbtlib.List[nbtlib.Compound](sections),
            })
            buffer = BytesIO()
            chunk.write(buffer)
            payload = zlib.compress(buffer.getvalue())
            header = bytearray(8192)
            index = (cx % 32) + (cz % 32) * 32
            sectors = (len(payload) + 5 + 4095) // 4096
            header[index * 4:index * 4 + 4] = (2).to_bytes(3, "big") + bytes([sectors])
            record = (len(payload) + 1).to_bytes(4, "big") + b"\x02" + payload
            (region / f"r.{cx // 32}.{cz // 32}.mca").write_bytes(
                header + record + bytes(sectors * 4096 - len(record))
            )


def test_structure_scores_and_missing_evidence(tmp_path: Path) -> None:
    config = {
        "target": {"structure": [
            [["oak_planks", "glass"], ["air", None]],
            [["oak_planks", None], [None, None]],
        ]},
        "region": {"min": [-3, -1, -3], "max": [2, 1, 2]},
    }
    built = {(-1, 0, -1): "oak_planks", (-1, 0, 0): "glass", (-1, 1, -1): "oak_planks",
             (-2, 0, 0): "stone"}
    before, after = tmp_path / "before", tmp_path / "after"
    _save_world(before, {})
    _save_world(after, built)
    baseline_files = {path.relative_to(before): path.read_bytes() for path in before.rglob("*") if path.is_file()}
    result = evaluate_structure(before, after, config)
    assert result["success"] and result["best_match"]["rotation_degrees"] == 90
    assert result["best_match"]["offset"] == [-1, 0, -1]
    assert result["best_match"]["matched"] == 3
    assert not evaluate_structure(before, after, config | {"match": {"rotation_invariant": False}})["success"]
    assert not evaluate_structure(after, after, config)["success"]
    assert evaluate_structure(after, after, config | {"match": {"require_new_blocks": False}})["success"]

    for label, blocks, relaxed in (
        ("missing", {p: name for p, name in built.items() if name != "glass"},
         {"min_recall": 2 / 3, "min_iou": 2 / 3}),
        ("extra", built | {(2, 0, 2): "glass"}, {"min_precision": 0.75, "min_iou": 0.75}),
        ("occupied", built | {(-2, 0, -1): "stone"}, {"require_empty": False}),
    ):
        changed = tmp_path / label
        _save_world(changed, blocks)
        assert not evaluate_structure(before, changed, config)["success"]
        assert evaluate_structure(before, changed, config | {"match": relaxed})["success"]
    assert baseline_files == {path.relative_to(before): path.read_bytes() for path in before.rglob("*") if path.is_file()}

    # A perfect visible match must not conceal unreadable cells elsewhere in the declared region.
    region = after / "region/r.0.0.mca"
    original = region.read_bytes()
    length = int.from_bytes(original[8192:8196], "big")
    region.write_bytes(original[:8192 + 4 + length - 1])
    with pytest.raises(ValueError, match="Truncated chunk payload"):
        evaluate_structure(before, after, config)
    region.unlink()
    with pytest.raises(FileNotFoundError):
        evaluate_structure(before, after, config)
    wrong = deepcopy(config)
    wrong["region"]["min"][1] = -65
    with pytest.raises(ValueError, match="dimension height"):
        evaluate_structure(before, before, wrong)


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in native construction check")
def test_native_structure_placement(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool, minecraft_world_path: Path,
) -> None:
    from game.minecraft.game import MinecraftGame
    from game.minecraft.init_player_state import PlayerState
    from game.minecraft.structured_tools.interface import StructuredInterface

    root = Path(os.environ.get("MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[3] / "output/test")))
    output = root.resolve() / f"minecraft-structure-{uuid4().hex}"
    print(f"Structure evaluator artifacts: {output}")
    monkeypatch.setenv("MINECRAFT_PRISM_ROOT", str(output / "no-prism-or-accounts"))
    game = MinecraftGame(
        track="structured_tool", output_dir=output, headless=headless, recording=recording,
        world_path=minecraft_world_path,
        player_state=PlayerState(position=(0.5, 72, 0.5),
                                 inventory=[{"slot": 0, "item": "oak_planks", "count": 4}]),
    )

    async def run() -> None:
        try:
            await game.start()
            before = await game.save_snapshot(output / "before")
            interface = game.get_agent_interface()
            assert isinstance(interface, StructuredInterface)
            await game.begin()
            for y in (71, 72):
                placed = await interface.call_tool("PlaceTool", {"x": 1, "y": y, "z": 0, "face": "top"})
                assert placed["success"], placed
            await game.end()
            after = await game.save_snapshot(output / "after")
            config = {
                "target": {"structure": [[["oak_planks"]], [["oak_planks"]]]},
                "region": {"min": [0, 72, -1], "max": [2, 74, 1]},
            }
            result = evaluate_structure(before, after, config)
            (output / "structure_result.json").write_text(json.dumps(result, indent=2) + "\n")
            assert result["success"], result
            assert result["best_match"]["matched"] == 2
            assert result["coverage"]["changed_blocks"] == 2
            assert not evaluate_structure(before, before, config)["success"]
            assert not evaluate_structure(after, after, config)["success"]
        finally:
            await game.close()
        if recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )

    asyncio.run(run())
