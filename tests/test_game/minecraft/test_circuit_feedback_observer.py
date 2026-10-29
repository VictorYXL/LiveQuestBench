from uuid import UUID
from pathlib import Path

import pytest

from game.minecraft.evaluators.circuit_feedback import final_modes
from game.minecraft.fixtures.circuit_feedback_observer import pack

PLAYER = UUID("00000000-0000-0000-0000-000000000001")
IDENTITY = [0, 0, 0, 1]


def event(mode, start, *, mined=0, edits=0):
    return {"input": mode, "start_tick": start, "tick": start + 99,
            "player": IDENTITY, "mined": mined, "edits": edits}


def test_coherent_final_repair_accepts_either_demonstration_order():
    for modes in ((0, 1), (1, 0)):
        record = {"events": [event(modes[0], 10), event(modes[1], 120)], "edits": []}
        assert final_modes(record, PLAYER, 0, 500, 0) == {0, 1}


@pytest.mark.parametrize("kind", ["mining", "interaction"])
def test_different_repairs_cannot_combine_input_modes(kind):
    record = {"events": [event(1, 10), event(0, 220)], "edits": []}
    if kind == "mining":
        record["events"][1]["mined"] = 1
    else:
        record["edits"] = [{"tick": 150, "player": IDENTITY}]
        record["events"][1]["edits"] = 1
    assert final_modes(record, PLAYER, 0, 500, int(kind == "mining")) == {0}


@pytest.mark.parametrize("kind", ["mining", "interaction"])
def test_later_repair_invalidates_previously_complete_pair(kind):
    record = {"events": [event(1, 10), event(0, 120)], "edits": []}
    if kind == "interaction":
        record["edits"] = [{"tick": 300, "player": IDENTITY}]
    assert final_modes(record, PLAYER, 0, 500, int(kind == "mining")) == set()


def test_short_transient_is_not_a_settled_demonstration():
    record = {"events": [event(1, 10)], "edits": []}
    record["events"][0]["tick"] = 20
    with pytest.raises(ValueError, match="stable feedback"):
        final_modes(record, PLAYER, 0, 500, 0)


@pytest.mark.parametrize("mutate", [
    lambda r: r["events"][0].update(player=[0, 0, 0, 2]),
    lambda r: r["events"][0].update(start_tick=-1),
    lambda r: r["events"][0].update(mined=1),
    lambda r: r["edits"].append({"tick": 50, "player": IDENTITY}),
])
def test_invalid_identity_time_or_revision_fails_closed(mutate):
    record = {"events": [event(1, 10)], "edits": []}
    mutate(record)
    with pytest.raises(ValueError):
        final_modes(record, PLAYER, 0, 500, 0)


def test_native_observer_counts_all_mining_and_resets_interactions_without_driving_world():
    commands = pack()
    functions = "\n".join(v for k, v in commands.items() if k.endswith(".mcfunction"))
    assert "minecraft.mined:minecraft.redstone_wire" in functions
    assert "minecraft.mined:minecraft.repeater" in functions
    assert "minecraft.mined:minecraft.cobblestone" in functions
    # Render assets include these entities, but native mining criteria reject them.
    assert "minecraft.mined:minecraft.item_frame" not in functions
    assert "minecraft.mined:minecraft.glow_item_frame" not in functions
    assert "scoreboard players set #stable lqf 0" in commands[
        "data/livequest_feedback/functions/edit.mcfunction"]
    assert "unless score #mined lqf = #start_mined lqf" in commands[
        "data/livequest_feedback/functions/finish.mcfunction"]
    assert not any(word in functions for word in ("setblock ", "fill ", "tick step", "tp ", "give "))


def test_backwards_clock_is_invalid_even_without_events():
    with pytest.raises(ValueError, match="clock moved backwards"):
        final_modes({"events": [], "edits": []}, PLAYER, 100, 99, 0)


@pytest.mark.parametrize("folder", ["structured_tools", "visual_motor"])
def test_published_feedback_binding_keeps_identity_and_vanilla_server(folder, tmp_path):
    from benchmark.config import load_task
    from benchmark.factory import make_game

    root = Path(__file__).resolve().parents[3]
    published = root / "config/minecraft/tasks" / folder / "workshop_circuit_feedback_v3.yaml"
    frozen = root / "config/minecraft/prototypes" / folder / published.name
    assert published.read_bytes() == frozen.read_bytes()
    task = load_task(published)
    assert task.id == "workshop_circuit_feedback_v3"
    output = tmp_path / "not-started"
    binding = make_game(task, output, headless=True, recording=False, recording_fps=10)
    assert binding.game.server_factory is None
    assert not output.exists()
