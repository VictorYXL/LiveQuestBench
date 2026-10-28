"""Native route observer identity, continuity, and fixture admission."""

import json
from pathlib import Path
from uuid import uuid4

import nbtlib
import pytest

from game.minecraft.evaluators.route_transfer import read_samples, verify_layout
from game.minecraft.fixtures.route_transfer import SCHEMA, expected_hashes, pack_text, route_pack


def observer(world, player, ticks):
    for name, value in route_pack().items():
        path = world / "datapacks/livequest_route" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pack_text(value))
    (world / "livequest-route-evidence.json").write_text(json.dumps({
        "schema": SCHEMA, "pack_sha256": expected_hashes(),
    }))
    (world / "data").mkdir(exist_ok=True)
    identity = [int.from_bytes(player.bytes[i:i + 4], "big", signed=True)
                for i in range(0, 16, 4)]
    nbtlib.File({
        "DataVersion": nbtlib.Int(3700),
        "data": nbtlib.Compound({"contents": nbtlib.Compound({
            "route": nbtlib.Compound({
                "schema": nbtlib.String(SCHEMA), "overflow": nbtlib.Byte(0),
                "samples": nbtlib.List[nbtlib.Compound]([
                    nbtlib.Compound({
                        "player": nbtlib.IntArray(identity), "tick": nbtlib.Long(tick),
                        "position": nbtlib.List[nbtlib.Double]([1, 201, 2]),
                    }) for tick in ticks
                ]),
            }),
        })}),
    }, gzipped=True).save(world / "data/command_storage_livequest.dat")


def test_native_route_rejects_another_player_missing_ticks_and_modified_observer(tmp_path):
    player = uuid4()
    observer(tmp_path, player, [100, 101])
    assert read_samples(tmp_path, player)[0]["position"] == [1, 2, 201]
    with pytest.raises(ValueError, match="another player"):
        read_samples(tmp_path, uuid4())
    observer(tmp_path, player, [100, 102])
    with pytest.raises(ValueError, match="missing game ticks"):
        read_samples(tmp_path, player)
    observer(tmp_path, player, [100, 101])
    (tmp_path / "datapacks/livequest_route/pack.mcmeta").write_text("{}")
    with pytest.raises(ValueError, match="observer changed"):
        read_samples(tmp_path, player)


def test_route_admission_rejects_a_world_that_does_not_match_the_layout(tmp_path, monkeypatch):
    import game.minecraft.evaluators.route_transfer as module

    monkeypatch.setattr(module, "build_layout", lambda *args: {
        "solid": {(0, 0, 200)}, "walking": {(0, 0, 201)},
    })
    blocks = {(0, 200, 0): "minecraft:bedrock",
              (0, 201, 0): "minecraft:air", (0, 202, 0): "minecraft:light"}
    monkeypatch.setattr(module, "read_blocks", lambda *args: blocks)
    verify_layout(tmp_path, variant=0, origin=[0, 0, 201])
    blocks[0, 200, 0] = "minecraft:air"
    with pytest.raises(ValueError, match="geometry differs"):
        verify_layout(tmp_path, variant=0, origin=[0, 0, 201])


@pytest.mark.parametrize(("ticks", "message"), [
    ([99, 101], "history changed"), ([100, 103], "outside measured play"),
])
def test_route_rejects_rewritten_or_cross_boundary_native_history(monkeypatch, ticks, message):
    import game.minecraft.evaluators.route_transfer as module

    def rows(values):
        return [{"sequence": tick, "position": [0, 0, 201]} for tick in values]

    monkeypatch.setattr(module, "read_samples",
                        lambda path, player: rows([100] if path.name == "before" else ticks))
    monkeypatch.setattr(module.nbtlib, "load", lambda path: {
        "Data": {"Time": 100 if path.parent.name == "before" else 102},
    })
    with pytest.raises(ValueError, match=message):
        module.evaluate_route(Path("before"), Path("after"), uuid4(), variant=0, origin=[0, 0, 201])
