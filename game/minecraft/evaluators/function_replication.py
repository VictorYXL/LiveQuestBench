"""Private post-terminal native truth-table test of the final construction."""
import asyncio
import hashlib
import json
import secrets

import nbtlib

from game.minecraft.evaluators.world import _chunk
from game.minecraft.fixtures.function_replication import count_removals, public_manifest


def block(world, position, cache=None):
    cache = {} if cache is None else cache
    x, y, z = position
    key = x//16, z//16
    if key not in cache:
        cache[key] = _chunk(world / "region", *key)
    section = next(row for row in cache[key]["sections"] if int(row["Y"]) == y//16)
    states = section["block_states"]
    palette = states["palette"]
    bits = max(4, (len(palette)-1).bit_length())
    index = (y % 16)*256 + (z % 16)*16 + x % 16
    value = 0 if len(palette) == 1 else (
        int(states["data"][index//(64//bits)]) >> ((index % (64//bits))*bits)
    ) & ((1 << bits)-1)
    return palette[value].unpack()


def fingerprint(world):
    digest = hashlib.sha256()
    for path in sorted(world.rglob("*")):
        if path.is_file() and path.name != "session.lock":
            digest.update(str(path.relative_to(world)).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def reference_table(world):
    rows = nbtlib.load(world / "data/command_storage_livequest.dat")[
        "data"]["contents"]["function_preflight"]["cases"].unpack()
    table = {(int(row["a"]), int(row["b"])): int(row["outputs"][0]) for row in rows}
    if len(rows) != 4 or set(table) != {(0, 0), (0, 1), (1, 0), (1, 1)}:
        raise ValueError("Missing complete original native reference measurements")
    if any(value not in (0, 1) for value in table.values()):
        raise ValueError("Invalid native lamp measurement")
    return table


def initial_function(world):
    connections = [block(world, pos)["Name"] == "minecraft:cobblestone"
                   for pos in ((71, 72, 3), (57, 72, 3))]
    if connections.count(True) != 1:
        raise ValueError("Reference must have one original native AND/OR connection")
    table = reference_table(world)
    function = "AND" if connections[0] else "OR"
    if any(value != int(bool(a and b) if function == "AND" else bool(a or b))
           for (a, b), value in table.items()):
        raise ValueError("Native reference measurements disagree with its original connection")
    return function


def select_world(world):
    manifest = world / "native-function-variants.json"
    if not manifest.exists():
        raise ValueError("Hidden-function admission requires its native instance distribution manifest")
    data = json.loads(manifest.read_text())
    if (data.get("selection") != "uniform_once_before_episode"
            or not isinstance(data.get("worlds"), list) or len(data["worlds"]) != 2
            or not all(isinstance(path, str) and path for path in data["worlds"])):
        raise ValueError("Expected the frozen two-instance native distribution")
    worlds = [(world / path).resolve() for path in data["worlds"]]
    if len(set(worlds)) != 2 or {initial_function(path) for path in worlds} != {"AND", "OR"}:
        raise ValueError("Native instance family must contain distinct verified AND and OR circuits")
    public = [json.loads((path / "livequest-function-public.json").read_text()) for path in worlds]
    if public[0] != public[1]:
        raise ValueError("Native variants must have identical public contracts")
    index = secrets.randbelow(len(worlds))
    return worlds[index], {
        "selection": data["selection"], "instance_index": index,
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "selected_fixture_sha256": fingerprint(worlds[index]),
        "resampling_after_outcome": False,
    }


def truth_table_passes(rows, expected):
    pairs = {(0, 0), (0, 1), (1, 0), (1, 1)}
    if len(rows) != 4 or {(row["a"], row["b"]) for row in rows} != pairs:
        return False
    return all(list(row["outputs"]) == list(row["settled_outputs"]) == [
        expected[(row["a"], row["b"])]
    ] * 3 for row in rows)


async def probe_final(game, before, after):
    if game.phase != "ended" or game._session is None or game._session.server is None:
        raise RuntimeError("Functional verification requires a closed episode and its leased native server")
    receipt = game.output_dir / "final-function-verification.json"
    identity = {"before_sha256": fingerprint(before), "after_sha256": fingerprint(after)}
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if any(saved[key] != value for key, value in identity.items()):
            raise ValueError("Final verification belongs to different immutable snapshots")
        return saved
    function = initial_function(before)
    expected = reference_table(before)
    public = public_manifest()
    stations = [public["reference"], *public["panels"]]
    cache = {}
    states = [[block(after, pos, cache) for pos in station["inputs"]] for station in stations]
    result = {**identity, "kind": "private_post_terminal_native_truth_table",
              "public_attempt_count_required": False, "original_function": function,
              "original_native_outputs": {f"{a}{b}": value for (a, b), value in expected.items()},
              "same_leased_server": True, "cases": [], "passed": False}
    if any(value["Name"] != "minecraft:lever" for pair in states for value in pair):
        result["failure"] = "A declared native input is no longer a lever"
        receipt.write_text(json.dumps(result, indent=2) + "\n")
        return result
    server = game._session.server
    commands = []

    async def command(text):
        lines = await server.command(text)
        commands.append({"command": text, "feedback": lines})
        return lines

    # Inputs are exercised only after controls close and the measured after-save
    # is immutable. No blocks in the final construction are repaired or supplied.
    await command("data modify storage livequest:final_check cases set value []")
    for a, b in ((0, 0), (1, 0), (1, 1), (0, 1)):
        for station, pair in zip(stations, states):
            for value, pos, state in zip((a, b), station["inputs"], pair):
                properties = {**state.get("Properties", {}), "powered": str(bool(value)).lower()}
                suffix = ",".join(f"{key}={value}" for key, value in sorted(properties.items()))
                await command(f"setblock {' '.join(map(str,pos))} minecraft:lever[{suffix}]")
        await command("tick step 200")
        await asyncio.sleep(10.5)
        await command(f"data modify storage livequest:final_check cases append value {{a:{a},b:{b},outputs:[0,0,0],settled_outputs:[0,0,0]}}")
        for i, station in enumerate(stations):
            xyz = " ".join(map(str, station["output"]))
            await command(f"execute if block {xyz} redstone_lamp[lit=true] run data modify storage livequest:final_check cases[-1].outputs[{i}] set value 1")
        await command("tick step 40")
        await asyncio.sleep(2.5)
        for i, station in enumerate(stations):
            xyz = " ".join(map(str, station["output"]))
            await command(f"execute if block {xyz} redstone_lamp[lit=true] run data modify storage livequest:final_check cases[-1].settled_outputs[{i}] set value 1")
    lines = await command("data get storage livequest:final_check cases")
    text = next(line.split("contents: ", 1)[1] for line in lines if "contents: " in line)
    result["cases"] = nbtlib.parse_nbt(text).unpack()
    result["passed"] = truth_table_passes(result["cases"], expected)
    result["commands"] = commands
    receipt.write_text(json.dumps(result, indent=2, default=lambda x: x.tolist()) + "\n")
    return result


def evaluate_function(before, after, player, *, game, loop):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Use asyncio.to_thread for private final native verification")
    probe = asyncio.run_coroutine_threadsafe(probe_final(game, before, after), loop).result(timeout=120)
    first = int(nbtlib.load(before / "level.dat")["Data"]["Time"])
    last = int(nbtlib.load(after / "level.dat")["Data"]["Time"])
    ledger = game.output_dir / "successful-breaks.jsonl"
    events = [json.loads(row) for row in ledger.read_text().splitlines()] if ledger.exists() else []
    events = [event for event in events if int(event["native_tick"]) <= last]
    removals = count_removals(events, player, start_tick=first, end_tick=last)
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    alive = float(native["Health"]) > 0
    return {"success": bool(probe["passed"] and removals["within_six_removal_budget"] and alive),
            "checks": {"final_native_function": probe["passed"], "alive": alive, **removals},
            "private_verification": str(game.output_dir / "final-function-verification.json")}
