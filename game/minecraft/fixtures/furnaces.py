"""Passive native furnace production and empty-input burn accounting."""

import hashlib
import json
from pathlib import Path


SCHEMA = "minecraft-furnace-dispatch/1"
FURNACES = [(-9, 72, 2), (9, 72, 2)]


def furnace_pack() -> dict[str, str | dict]:
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive furnace production evidence"}},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_furnaces:tick"]},
    }
    tick = []
    for index, point in enumerate(FURNACES):
        coordinate = " ".join(map(str, point))
        for field, path in (("burn", "BurnTime"), ("input", "Items[{Slot:0b}].Count"),
                            ("output", "Items[{Slot:2b}].Count")):
            tick += [
                f"scoreboard players set #{field}{index} lqb_furn 0",
                f"execute store result score #{field}{index} lqb_furn run data get block {coordinate} {path}",
            ]
        tick += [
            f"execute if score #burn{index} lqb_furn matches 1.. run scoreboard players add #burning{index} lqb_furn 1",
            f"execute if score #burn{index} lqb_furn matches 1.. if score #input{index} lqb_furn matches 0 run scoreboard players add #empty{index} lqb_furn 1",
            f"execute if score #output{index} lqb_furn > #lastout{index} lqb_furn run function livequest_furnaces:output{index}",
            f"execute if score #burn{index} lqb_furn > #lastburn{index} lqb_furn run function livequest_furnaces:fuel{index}",
            f"execute if data block {coordinate} Items[{{Slot:1b}}] run data modify storage livequest:dispatch fuel{index} set from block {coordinate} Items[{{Slot:1b}}].id",
            f"scoreboard players operation #lastout{index} lqb_furn = #output{index} lqb_furn",
            f"scoreboard players operation #lastburn{index} lqb_furn = #burn{index} lqb_furn",
            f"execute store result storage livequest:dispatch metrics[{index}].burning_ticks long 1 run scoreboard players get #burning{index} lqb_furn",
            f"execute store result storage livequest:dispatch metrics[{index}].empty_input_burn_ticks long 1 run scoreboard players get #empty{index} lqb_furn",
        ]
        files[f"data/livequest_furnaces/functions/output{index}.mcfunction"] = "\n".join([
            f'data modify storage livequest:dispatch events append value {{kind:"completion",machine:{index}}}',
            "execute store result storage livequest:dispatch events[-1].tick long 1 run time query gametime",
            f"data modify storage livequest:dispatch events[-1].output set from block {coordinate} Items[{{Slot:2b}}]",
        ]) + "\n"
        files[f"data/livequest_furnaces/functions/fuel{index}.mcfunction"] = "\n".join([
            f'data modify storage livequest:dispatch events append value {{kind:"fuel",machine:{index}}}',
            "execute store result storage livequest:dispatch events[-1].tick long 1 run time query gametime",
            f"data modify storage livequest:dispatch events[-1].item set from storage livequest:dispatch fuel{index}",
        ]) + "\n"
    files["data/livequest_furnaces/functions/sample.mcfunction"] = "\n".join(tick) + "\n"
    files["data/livequest_furnaces/functions/tick.mcfunction"] = (
        "execute if data storage livequest:dispatch schema run function livequest_furnaces:sample\n"
    )
    return files


def pack_bytes():
    return {name: (value if isinstance(value, str) else json.dumps(value, indent=2) + "\n").encode()
            for name, value in furnace_pack().items()}


def expected_hashes():
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in pack_bytes().items()}


def install_observer(world: Path) -> list[str]:
    for name, raw in pack_bytes().items():
        path = world / "datapacks/livequest_furnaces" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (world / "livequest-furnaces.json").write_text(json.dumps({
        "schema": SCHEMA, "sha256": expected_hashes(),
    }, indent=2) + "\n")
    commands = [
        "scoreboard objectives add lqb_furn dummy",
        f'data merge storage livequest:dispatch {{schema:"{SCHEMA}",events:[],metrics:[{{burning_ticks:0L,empty_input_burn_ticks:0L}},{{burning_ticks:0L,empty_input_burn_ticks:0L}}]}}',
    ]
    for index in range(len(FURNACES)):
        commands += [f"scoreboard players set #{name}{index} lqb_furn 0"
                     for name in ("lastout", "lastburn", "burning", "empty")]
    return commands
