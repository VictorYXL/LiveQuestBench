"""Both native circuit output modes after actual input changes."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import nbtlib

from game.minecraft.evaluators.state import evaluate_state
from game.minecraft.evaluators.world import read_blocks
from game.minecraft.fixtures.circuit import SCHEMA, expected_hashes


def events(world):
    expected = expected_hashes()
    if json.loads((world / "livequest-circuit.json").read_text()) != {"schema": SCHEMA, "sha256": expected}:
        raise ValueError("Circuit observer manifest changed")
    for name, digest in expected.items():
        if hashlib.sha256((world / "datapacks/livequest_circuit" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Circuit observer implementation changed")
    native = nbtlib.load(world / "data/command_storage_livequest.dat")
    if int(native["DataVersion"]) != 3700:
        raise ValueError("Circuit evidence requires Minecraft 1.20.4")
    record = native["data"]["contents"]["circuit"]
    if str(record["schema"]) != SCHEMA:
        raise ValueError("Circuit evidence storage identity changed")
    return [{"input": int(row["input"]), "tick": int(row["tick"]),
             "player": list(map(int, row["player"]))} for row in record["events"]]


def evaluate_circuit(before: Path, after: Path, player: UUID, *, position: dict):
    if events(before):
        raise ValueError("Circuit task must start without input/output demonstrations")
    record = events(after)
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    if last < first:
        raise ValueError("The native circuit clock moved backwards")
    if any(row["player"] != identity or row["input"] not in (0, 1)
           or not first <= row["tick"] <= last for row in record):
        raise ValueError("Invalid native circuit transition identity or time")
    if any(right["tick"] - left["tick"] < 10 for left, right in zip(record, record[1:])):
        raise ValueError("Circuit demonstrations require distinct native stability intervals")
    result = evaluate_state(before, after, player, position=position)
    both = {row["input"] for row in record} == {0, 1}
    final = read_blocks(after, (23, 72, 7), (25, 73, 7), "minecraft:overworld")
    controls = read_blocks(after, (0, 72, 5), (24, 72, 5), "minecraft:overworld")
    retained = (
        controls[0, 72, 5] == "minecraft:lever"
        and controls[24, 72, 5] == "minecraft:redstone_lamp"
        and all(final[24, y, 7] == "minecraft:iron_door" for y in (72, 73))
    )
    accessible = all(final[x, y, 7] in {"minecraft:air", "minecraft:redstone_wire"}
                     for x in (23, 25) for y in (72, 73))
    result["checks"].extend([
        {"kind": "native_on_and_off_demonstrated", "passed": both},
        {"kind": "native_controls_and_outputs_retained", "passed": retained},
        {"kind": "door_approaches_clear", "passed": accessible},
    ])
    result["success"] = all(row["passed"] for row in result["checks"])
    result["input_output_events"] = record
    result["semantics"] += (
        " The passive observer never presses the input: both matching door/lamp modes must follow native "
        "lever transitions, with ten native world ticks of stable response; frozen observer calls do not count. "
        "The lever, lamp and both door halves "
        "must remain at completion. A permanently powered output cannot pass."
    )
    return result
