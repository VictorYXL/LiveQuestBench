"""Minecraft installation, world isolation, snapshots and recording checks."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import pytest

nbtlib = pytest.importorskip("nbtlib", reason="Install the minecraft extra to run game checks")
pytest.importorskip("Xlib", reason="Install the minecraft extra to run game checks")
pytest.importorskip("PIL", reason="Install the minecraft extra to run game checks")

from game.minecraft.evaluators.inventory import evaluate_inventory
from game.minecraft.game import MinecraftGame
from game.minecraft.init_player_state import PlayerState
from game.minecraft.runtime.install import check_installation
from game.minecraft.runtime.session import copy_world


@pytest.fixture
def tmp_path():
    root = Path(__file__).resolve().parents[3] / "output" / "test"
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="minecraft-offline-", dir=root) as directory:
        yield Path(directory)


def test_world_evidence(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    nbtlib.File({"Data": nbtlib.Compound({"DataVersion": nbtlib.Int(3700)})}, gzipped=True).save(fixture / "level.dat")
    original = (fixture / "level.dat").read_bytes()
    player = UUID("00000000-0000-0000-0000-000000000001")
    initial = PlayerState(position=(0.5, 72, 0.5), inventory=[{"slot": 0, "item": "dirt", "count": 2}])
    before, after = tmp_path / "before", tmp_path / "after"
    copy_world(fixture, before, initial, player)
    copy_world(fixture, after, initial, player)
    final = PlayerState(position=(0.5, 72, 0.5), inventory=[{"slot": 0, "item": "dirt", "count": 5}])
    final.write(after, player, replace=True)
    final.verify(nbtlib.load(after / "playerdata" / f"{player}.dat"), player)
    assert (fixture / "level.dat").read_bytes() == original
    assert not (fixture / "playerdata").exists()
    result = evaluate_inventory(before, after, player, [{"item": "dirt", "min_count": 5, "min_delta": 3}])
    assert result["success"] and result["checks"][0]["delta"] == 3
    assert not evaluate_inventory(before, after, player, [{"item": "dirt", "min_delta": 4}])["success"]
    with pytest.raises(ValueError, match="thresholds"):
        evaluate_inventory(before, after, player, [{"item": "dirt", "min_count": None}])
    with pytest.raises(ValueError, match="thresholds"):
        evaluate_inventory(before, after, player, [{"item": "dirt"}])
    assert evaluate_inventory(after, before, player, [{"item": "dirt", "min_count": 2}])["success"]
    assert not evaluate_inventory(after, before, player, [{"item": "dirt", "min_delta": 0}])["success"]
    assert evaluate_inventory(before, after, player, [{"item": "oak_log", "min_delta": 0}])["success"]
    assert evaluate_inventory(before, after, player, [{"item": "oak_log", "max_count": 0}])["success"]
    with pytest.raises(FileExistsError):
        copy_world(fixture, before, initial, player)
    with pytest.raises(ValueError, match="player data"):
        copy_world(before, tmp_path / "invalid", initial, player)
    with pytest.raises(FileNotFoundError):
        evaluate_inventory(before, tmp_path / "missing", player, [{"item": "dirt", "min_count": 1}])
    with pytest.raises(ValueError):
        PlayerState(position=(float("nan"), 72, 0))


def test_minecraft_lifecycle_requires_explicit_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINECRAFT_EULA_ACCEPTED", raising=False)
    game = MinecraftGame(world_path=tmp_path / "missing", output_dir=tmp_path / "run",
                         player_state=PlayerState(position=(0.5, 72, 0.5)))

    async def check() -> None:
        with pytest.raises(RuntimeError):
            await game.begin()
        with pytest.raises(RuntimeError):
            await game.end()
        with pytest.raises(RuntimeError):
            game.get_agent_interface()
        with pytest.raises(PermissionError):
            await game.start()
        await game.close()
        await game.close()
        assert game.phase == "closed"
        assert not game.output_dir.exists()

    asyncio.run(check())


def test_initial_tool_wear_is_written_and_verified():
    player = UUID("00000000-0000-0000-0000-000000000001")
    state = PlayerState(position=(0.5, 72, 0.5),
                        inventory=[{"slot": 0, "item": "iron_pickaxe", "count": 1, "damage": 238}])
    native = state.nbt(player)
    state.verify(native, player)
    native["Inventory"][0]["tag"]["Damage"] = nbtlib.Int(0)
    with pytest.raises(RuntimeError, match="Inventory damage"):
        state.verify(native, player)


@pytest.mark.parametrize("damage,count", [(-1, 1), (True, 1), (1.5, 1), (238, 2)])
def test_initial_tool_wear_rejects_invalid_or_stacked_damage(damage, count):
    with pytest.raises(ValueError, match="damage"):
        PlayerState(position=(0.5, 72, 0.5),
                    inventory=[{"slot": 0, "item": "iron_pickaxe", "count": count, "damage": damage}])


def test_native_state_distinguishes_selection_effects_and_history(tmp_path):
    from game.minecraft.evaluators.state import evaluate_state, validate_state

    player = UUID(int=1)
    before, after = tmp_path / "before", tmp_path / "after"
    for world in (before, after):
        world.mkdir()
        PlayerState(position=(0.5, 72, 0.5), food=10,
                    inventory=[{"slot": 1, "item": "wooden_pickaxe", "count": 1}]).write(world, player)
    assert not evaluate_state(before, after, player, held_item="wooden_pickaxe")["success"]
    assert not evaluate_state(before, after, player, statistics={"open_chest": 1})["success"]
    path = after / "playerdata" / f"{player}.dat"
    native = nbtlib.load(path)
    native["SelectedItemSlot"] = nbtlib.Int(1)
    native["OnGround"] = nbtlib.Byte(1)
    native.save(path)
    assert evaluate_state(before, after, player, held_item="wooden_pickaxe")["success"]
    assert not evaluate_state(before, after, player, min_food=15)["success"]
    position = {"target": [0.5, 72, 0.5], "horizontal_tolerance": 0.5,
                "vertical_tolerance": 0.5, "max_speed": 0.1}
    assert evaluate_state(before, after, player, position=position)["success"]
    native["OnGround"] = nbtlib.Byte(0)
    native.save(path)
    assert not evaluate_state(before, after, player, position=position)["success"]
    (after / "stats").mkdir()
    stats = after / "stats" / f"{player}.json"
    stats.write_text(json.dumps({"DataVersion": 3700, "stats": {"minecraft:custom": {
        "minecraft:open_chest": 1, "minecraft:damage_dealt": 10,
    }}}))
    assert evaluate_state(before, after, player, statistics={"open_chest": 1, "damage_dealt": 1})["success"]
    assert not evaluate_state(after, after, player, statistics={"open_chest": 1})["success"]
    with pytest.raises(ValueError, match="backwards"):
        evaluate_state(after, before, player, statistics={"open_chest": 1})
    for params in ({}, {"statistics": {"jump": 0}}, {"min_food": True},
                   {"held_item": "invalid name"}, {"position": position | {"max_speed": float("nan")}}):
        with pytest.raises(ValueError):
            validate_state(**params)


def test_native_block_then_damage_requires_identity_order_and_same_life(tmp_path):
    from game.minecraft.evaluators.state import evaluate_state
    from game.minecraft.fixtures.actions import ACTION_SCHEMA, action_hashes, action_pack

    player = UUID(int=1)
    before, after = tmp_path / "before", tmp_path / "after"
    for world, tick in ((before, 20), (after, 100)):
        world.mkdir()
        PlayerState(position=(0.5,72,0.5)).write(world, player)
        nbtlib.File({"Data": nbtlib.Compound({"DataVersion": nbtlib.Int(3700),
                                            "Time": nbtlib.Long(tick)})}, gzipped=True).save(world / "level.dat")
        for name, value in action_pack().items():
            path = world / "datapacks/livequest_actions" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value))
        (world / "livequest-action-evidence.json").write_text(json.dumps({
            "schema": ACTION_SCHEMA, "pack_sha256": action_hashes(world),
        }))
        (world / "data").mkdir()

    def write(world, kinds, actor=player):
        identity = [int.from_bytes(actor.bytes[i:i + 4], "big", signed=True) for i in range(0, 16, 4)]
        events = [nbtlib.Compound({"kind": nbtlib.String(kind), "player": nbtlib.IntArray(identity),
                                  "tick": nbtlib.Long(21)}) for kind in kinds]
        nbtlib.File({"DataVersion": nbtlib.Int(3700), "data": nbtlib.Compound({
            "contents": nbtlib.Compound({"actions": nbtlib.Compound({
                "schema": nbtlib.String(ACTION_SCHEMA), "events": nbtlib.List[nbtlib.Compound](events),
            })}),
        })}, gzipped=True).save(world / "data/command_storage_livequest.dat")

    write(before, [])
    parameters = {"action_sequence": ["block", "damage"], "no_death": True}
    write(after, ["damage", "block"])
    assert not evaluate_state(before, after, player, **parameters)["success"]
    write(after, ["block", "damage"])
    assert evaluate_state(before, after, player, **parameters)["success"]
    write(after, ["block", "damage"], UUID(int=2))
    with pytest.raises(ValueError, match="identity"):
        evaluate_state(before, after, player, **parameters)
    write(after, ["block", "damage"])
    (after / "stats").mkdir()
    (after / "stats" / f"{player}.json").write_text(json.dumps({
        "DataVersion": 3700, "stats": {"minecraft:custom": {"minecraft:deaths": 1}},
    }))
    assert not evaluate_state(before, after, player, **parameters)["success"]
    write(before, ["block"])
    with pytest.raises(ValueError, match="start empty"):
        evaluate_state(before, after, player, **parameters)


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Opt-in installed-game check")
def test_installation_world_and_recording(
    monkeypatch: pytest.MonkeyPatch, headless: bool, recording: bool, minecraft_world_path: Path,
) -> None:
    monkeypatch.setenv("MINECRAFT_PRISM_ROOT", "/nonexistent-livequest-prism")
    installation = check_installation()
    assert installation["version"] == "1.20.4"
    assert installation["client"] == "fabric-development"
    assert "prism_root" not in installation
    fixture = minecraft_world_path
    root = Path(os.environ.get(
        "MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[3] / "output" / "test"),
    )).resolve()
    output = root / f"minecraft-game-{uuid4().hex}"
    print(f"Minecraft game artifacts: {output}")
    state = PlayerState(position=(0.5, 72, 0.5), yaw=180,
                        inventory=[{"slot": 0, "item": "dirt", "count": 2}])
    game = MinecraftGame(
        world_path=fixture, output_dir=output, player_state=state,
        recording=recording, recording_fps=2, headless=headless,
    )
    hashes = {str(path.relative_to(fixture)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in fixture.rglob("*") if path.is_file()} if fixture is not None else {}

    async def run() -> None:
        try:
            await game.start()
            before = await game.save_snapshot(output / "before")
            await game.begin()
            await asyncio.sleep(1.5)
            await game.end()
            after = await game.save_snapshot(output / "after")
            assert game.player_uuid is not None
            assert int(nbtlib.load(after / "level.dat")["Data"]["Time"]) > int(nbtlib.load(before / "level.dat")["Data"]["Time"])
            result = evaluate_inventory(before, after, game.player_uuid, [{"item": "dirt", "min_count": 2}])
            assert result["success"]
            for snapshot, phase in ((before, "ready"), (after, "ended")):
                receipt = json.loads((snapshot / "_livequest_snapshot.json").read_text())
                assert receipt["phase"] == phase
                assert receipt["sha256"]
                for name, digest in receipt["sha256"].items():
                    assert hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == digest
        finally:
            await game.close()
        await game.close()
        if game.recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )
        if fixture is not None:
            assert hashes == {str(path.relative_to(fixture)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in fixture.rglob("*") if path.is_file()}

    asyncio.run(run())
