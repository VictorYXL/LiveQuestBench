"""Native AND/OR prototype and passive, function-independent evidence."""
import json
from pathlib import Path
import re


Y = 72
PANELS = ((-22, 0, 1), (-12, 24, -1))


def diode_command(command):
    # Minecraft diode FACING points toward its input, unlike our wiring flow notation.
    opposite = {"north": "south", "south": "north", "east": "west", "west": "east"}
    return re.sub(r"\b(repeater|comparator)\[facing=(north|south|east|west)",
                  lambda match: f"{match[1]}[facing={opposite[match[2]]}", command)


def point(panel, x, z):
    ox, oz, direction = panel
    return (ox + direction * x, Y, oz + z)


def module(panel, *, remote=False):
    """Two diode-isolated inputs feed real OR and De Morgan AND circuits."""
    blocks = {}

    def put(x, z, block):
        if panel[2] == -1:
            block = block.replace("east", "E").replace("west", "east").replace("E", "west")
        blocks[point(panel, x, z)] = block

    for z in (0, 6):
        put(0, z, "redstone_wire" if remote else "lever[face=floor,facing=north]")
        for x in (1, 2, 3):
            put(x, z, "redstone_wire")
        put(4, z, "stone_bricks")
        put(5, z, "redstone_wall_torch[facing=east]")
        put(6, z, "redstone_wire")
    put(2, 1, "repeater[facing=south]")
    put(2, 5, "repeater[facing=north]")
    for z in (2, 3, 4):
        put(2, z, "redstone_wire")
    for x in (1, 0, -1):
        put(x, 3, "redstone_wire")
    put(-2, 3, "repeater[facing=west]")
    put(-3, 3, "air")
    put(-4, 3, "repeater[facing=west]")
    for z in range(1, 6):
        put(6, z, "redstone_wire")
    put(7, 3, "redstone_wire")
    put(8, 3, "stone_bricks")
    put(9, 3, "redstone_wall_torch[facing=east]")
    put(10, 3, "repeater[facing=east]")
    put(11, 3, "air")
    put(12, 3, "repeater[facing=east]")
    for x in (-5, 13):
        for z in range(3, 11):
            put(x, z, "repeater[facing=south]" if z == 8 else "redstone_wire")
    for x in range(-4, 13):
        put(x, 10, "redstone_wire")
    if remote:
        put(4, 11, "redstone_wire")
    else:
        put(4, 11, "repeater[facing=south]")
        put(4, 12, "stone_bricks")
        put(5, 12, "piston[facing=up]")
        x, y, z = point(panel, 4, 12)
        blocks[(x, y + 1, z)] = "redstone_lamp"
    return blocks


def public_manifest():
    return {
        "kind": "native_function_replication_prototype",
        "family": ["AND", "OR"],
        "reference": {"inputs": [[0, 72, 0], [0, 72, 6]], "output": [0, 73, 14], "indicator": [0, 73, 15]},
        "panels": [
            {"inputs": [point(p, 0, 0), point(p, 0, 6)],
             "output": (point(p, 4, 12)[0], 73, point(p, 4, 12)[2]),
             "indicator": (point(p, 5, 12)[0], 73, point(p, 5, 12)[2]),
             "sockets": {"AND": point(p, 11, 3), "OR": point(p, -3, 3)}}
            for p in PANELS
        ],
        "goal": "Both constructed outputs must match the reference for 00,01,10,11 with one unchanged final construction.",
        "resources": {"cobblestone": 12, "maximum_successful_removals": 6},
        "limits": "Initial native feasibility family AND/OR only; no XOR implementation or learning claim.",
    }


def install_recorder(world: Path):
    public = public_manifest()
    stations = [public["reference"], *public["panels"]]
    root = world / "datapacks/livequest_function"
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive native input/output evidence"}},
        "data/minecraft/tags/functions/load.json": {"values": ["livequest_function:load"]},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_function:tick"]},
        "data/livequest_function/functions/load.mcfunction": "scoreboard objectives add lq_func dummy\n",
    }
    tick = ["scoreboard players add #sample lq_func 1",
            "execute if score #sample lq_func matches 10.. run function livequest_function:sample",
            "execute if score #sample lq_func matches 10.. run scoreboard players set #sample lq_func 0"]
    sample = []
    for index, station in enumerate(stations):
        stem = f"data/livequest_function/functions/station_{index}"
        lines = [f'data modify storage livequest:function current set value {{station:{index},a:0,b:0,lit:0,connections:[]}}']
        for name, pos in zip(("a", "b"), station["inputs"]):
            xyz = " ".join(map(str, pos))
            lines.append(f"execute if block {xyz} lever[powered=true] run data modify storage livequest:function current.{name} set value 1")
        xyz = " ".join(map(str, station["output"]))
        lines.append(f"execute if block {xyz} redstone_lamp[lit=true] run data modify storage livequest:function current.lit set value 1")
        # Record the full local construction/circuit volume, not just designated sockets.
        if index:
            ox, oz, direction = PANELS[index - 1]
            for x in range(-6, 15):
                for z in range(-1, 13):
                    for y in range(72, 75):
                        xyz = f"{ox + direction*x} {y} {oz+z}"
                        lines.append(f"execute if block {xyz} cobblestone run data modify storage livequest:function current.connections append value [I;{ox+direction*x},{y},{oz+z}]")
        lines += [
            f"execute store success score #changed{index} lq_func run data modify storage livequest:function last{index} set from storage livequest:function current",
            f"execute if score #changed{index} lq_func matches 1 run scoreboard players set #stable{index} lq_func 0",
            f"execute if score #changed{index} lq_func matches 0 run scoreboard players add #stable{index} lq_func 1",
            f"execute if score #stable{index} lq_func matches 6 run function livequest_function:record_{index}",
        ]
        files[stem + ".mcfunction"] = "\n".join(lines) + "\n"
        files[f"data/livequest_function/functions/record_{index}.mcfunction"] = (
            "data modify storage livequest:function events append from storage livequest:function current\n"
            "execute store result storage livequest:function events[-1].tick long 1 run time query gametime\n"
        )
        sample.append(f"function livequest_function:station_{index}")
    files["data/livequest_function/functions/tick.mcfunction"] = "\n".join(tick) + "\n"
    files["data/livequest_function/functions/sample.mcfunction"] = "\n".join(sample) + "\n"
    for name, value in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value)


def score(events, *, start_tick, final_connections):
    cases = {(0, 0), (0, 1), (1, 0), (1, 1)}
    reference = {}
    panels = [{}, {}]
    for event in events:
        if int(event["tick"]) < start_tick:
            continue
        pair = (int(event["a"]), int(event["b"]))
        station = int(event["station"])
        if station == 0:
            value = bool(event["lit"])
            if pair in reference and reference[pair] != value:
                raise ValueError("Reference function changed within the episode")
            reference[pair] = value
        elif station in (1, 2):
            connection = sorted(tuple(map(int, row)) for row in event["connections"])
            if connection == sorted(map(tuple, final_connections[station - 1])):
                panels[station - 1][pair] = bool(event["lit"])
            else:
                panels[station - 1].clear()
    complete = set(reference) == cases and all(set(panel) == cases for panel in panels)
    allowed = [{pair: bool(pair[0] and pair[1]) for pair in cases},
               {pair: bool(pair[0] or pair[1]) for pair in cases}]
    valid = set(reference) == cases and reference in allowed
    return {"all_four_cases": complete, "fixture_function_valid": valid,
            "native_function_match": complete and valid and all(panel == reference for panel in panels),
            "reference": {f"{a}{b}": value for (a, b), value in reference.items()},
            "panels": [{f"{a}{b}": value for (a, b), value in panel.items()} for panel in panels]}


def count_removals(events, player, *, start_tick, end_tick):
    """This prototype has no reset/phase exclusion: every owned native removal counts."""
    count, previous = 0, start_tick
    for event in events:
        if event["player_uuid"] != str(player):
            continue
        tick = int(event["native_tick"])
        if not start_tick <= tick <= end_tick or tick < previous:
            raise ValueError("Invalid native removal event ordering")
        previous = tick
        if event["schema"] != "livequest-native-successful-break/1" or event["old_block_id"] == "minecraft:air":
            raise ValueError("Not a successful native removal")
        count += 1
    return {"successful_removals": count, "within_six_removal_budget": count <= 6}
