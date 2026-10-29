from pathlib import Path
from uuid import UUID

import pytest

from game.minecraft.evaluators import circuit


@pytest.mark.parametrize("modes,removed,expected", [
    ([1], None, False), ([1, 0], None, True),
    ([1, 0], (0, 72, 5), False), ([1, 0], (24, 72, 5), False),
    ([1, 0], (24, 72, 7), False),
])
def test_both_modes_and_retained_native_components_are_required(monkeypatch, modes, removed, expected):
    monkeypatch.setattr(circuit, "events", lambda p: [] if p == Path("before") else [
        {"input": mode, "tick": 100 + 10 * i, "player": [0, 0, 0, 1]} for i, mode in enumerate(modes)
    ])
    monkeypatch.setattr(circuit.nbtlib, "load",
                        lambda p: {"Data": {"Time": 0 if p.parts[0] == "before" else 200}})
    monkeypatch.setattr(circuit, "evaluate_state",
                        lambda *_a, **_kw: {"success": True, "checks": [{"passed": True}], "semantics": ""})
    blocks = {
        (x, y, 7): "minecraft:air" for x in (23, 25) for y in (72, 73)
    }
    blocks.update({(0, 72, 5): "minecraft:lever", (24, 72, 5): "minecraft:redstone_lamp",
                   (24, 72, 7): "minecraft:iron_door", (24, 73, 7): "minecraft:iron_door"})
    if removed:
        blocks[removed] = "minecraft:air"
    monkeypatch.setattr(circuit, "read_blocks", lambda *_a: blocks)
    assert circuit.evaluate_circuit(Path("before"), Path("after"), UUID(int=1), position={})["success"] is expected


def test_same_world_tick_cannot_demonstrate_two_stable_modes(monkeypatch):
    monkeypatch.setattr(circuit, "events", lambda p: [] if p == Path("before") else [
        {"input": mode, "tick": 100, "player": [0, 0, 0, 1]} for mode in (1, 0)
    ])
    monkeypatch.setattr(circuit.nbtlib, "load",
                        lambda p: {"Data": {"Time": 0 if p.parts[0] == "before" else 200}})
    with pytest.raises(ValueError, match="native stability intervals"):
        circuit.evaluate_circuit(Path("before"), Path("after"), UUID(int=1), position={})


def test_reversed_native_clock_is_invalid_without_events(monkeypatch):
    monkeypatch.setattr(circuit, "events", lambda _p: [])
    monkeypatch.setattr(circuit.nbtlib, "load",
                        lambda p: {"Data": {"Time": 200 if p.parts[0] == "before" else 100}})
    monkeypatch.setattr(circuit, "evaluate_state",
                        lambda *_a, **_kw: {"success": True, "checks": [], "semantics": ""})
    monkeypatch.setattr(circuit, "read_blocks", lambda *_a: {
        **{(x, y, 7): "minecraft:air" for x in (23, 25) for y in (72, 73)},
        (0, 72, 5): "minecraft:air",
    })
    with pytest.raises(ValueError, match="native circuit clock moved backwards"):
        circuit.evaluate_circuit(Path("before"), Path("after"), UUID(int=1), position={})
