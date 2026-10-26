"""Offline, fail-closed export of the independently validated native island.

This is an administrative migration utility, not a game startup dependency.
Only full chunks matching the recorded generator's complete block plan are kept.
"""

import argparse
from collections import Counter
from io import BytesIO
import gzip
import hashlib
import json
from pathlib import Path
import zlib

import nbtlib
import numpy as np


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def chunk_records(region: Path):
    raw = region.read_bytes()
    for index in range(1024):
        location = raw[index * 4:index * 4 + 4]
        sector, sectors = int.from_bytes(location[:3], "big"), location[3]
        if not sector and not sectors:
            continue
        offset = sector * 4096
        length = int.from_bytes(raw[offset:offset + 4], "big")
        if sector < 2 or not 1 <= length <= sectors * 4096 - 4 or offset + 4 + length > len(raw):
            raise ValueError(f"Invalid chunk record in {region}")
        if raw[offset + 4] != 2:
            raise ValueError("Export requires ordinary zlib-compressed native chunks")
        yield index, nbtlib.File.parse(BytesIO(zlib.decompress(raw[offset + 5:offset + 4 + length])))


def section_names(section: nbtlib.Compound, names: list[str]) -> np.ndarray:
    states = section["block_states"]
    palette = [str(entry["Name"]).removeprefix("minecraft:") for entry in states["palette"]]
    if any(name not in names for name in palette):
        raise ValueError(f"Unexpected block palette: {palette}")
    lookup = np.array([names.index(name) for name in palette])
    if len(palette) == 1:
        return np.full(4096, lookup[0])
    bits = max(4, (len(palette) - 1).bit_length())
    per_long = 64 // bits
    words = np.asarray(states["data"], dtype=np.int64).view(np.uint64)
    if len(words) != (4096 + per_long - 1) // per_long:
        raise ValueError("Invalid packed block states")
    indices = (words[:, None] >> (np.arange(per_long, dtype=np.uint64) * bits)) & ((1 << bits) - 1)
    return lookup[indices.ravel()[:4096]]


def export(research: Path, destination: Path) -> None:
    source = research / "output/temp/island_native_validation_v2"
    world = source / "world"
    pack = world / "datapacks/agentcraft_island"
    manifest = json.loads((source / "island_manifest.json").read_text())
    checkpoints = json.loads((source / "island_checkpoints.json").read_text())
    pack_files = {
        str(path.relative_to(pack)): digest(path.read_bytes())
        for path in sorted(pack.rglob("*")) if path.is_file()
    }
    if digest(canonical(pack_files)) != manifest["pack_sha256"]:
        raise ValueError("Source datapack differs from its generation manifest")
    if digest(canonical(checkpoints)) != manifest["checkpoints_sha256"]:
        raise ValueError("Source checkpoints differ from the generation manifest")
    names = ["air", "bedrock", "stone", "sand", "water"]
    commands = {}
    for checkpoint in checkpoints:
        folder = pack / f"data/agentcraft_island/functions/chunks/c{checkpoint['index'] - 1:04d}"
        lines = [
            line for path in sorted(folder.glob("p*.mcfunction"), key=lambda p: int(p.stem[1:]))
            for line in path.read_text().splitlines() if line.startswith(("fill ", "setblock "))
        ]
        if len(lines) != checkpoint["commands"] or digest(("\n".join(lines) + "\n").encode()) != checkpoint["sha256"]:
            raise ValueError("Mutation commands differ from their checkpoint")
        key = tuple(checkpoint["chunk"])
        commands[key] = []
        for line in lines:
            parts = line.split()
            if parts[0] == "fill":
                x, y, z, xx, yy, zz = map(int, parts[1:7])
                block = parts[7]
            else:
                x, y, z = map(int, parts[1:4])
                xx, yy, zz = x, y, z
                block = parts[4]
            block = block.split("[")[0].removeprefix("minecraft:")
            if not (-64 <= y <= yy < 320 and x <= xx and z <= zz
                    and (x // 16, z // 16) == key == (xx // 16, zz // 16)):
                raise ValueError("Unexpected mutation bounds")
            if block not in names:
                names.append(block)
            commands[key].append((x, y, z, xx, yy, zz, names.index(block)))
    level = nbtlib.load(world / "level.dat")
    data = level["Data"]
    if "Player" in data or any(p.is_file() for p in (world / "playerdata").rglob("*")):
        raise ValueError("The validation source must have no players")
    generator = data["WorldGenSettings"]["dimensions"]["minecraft:overworld"]["generator"]
    layers = [(str(layer["block"]), int(layer["height"])) for layer in generator["settings"]["layers"]]
    if int(data["DataVersion"]) != 3700 or str(generator["type"]) != "minecraft:flat" or layers != [
        ("minecraft:bedrock", 1), ("minecraft:stone", 118), ("minecraft:sand", 2), ("minecraft:water", 7),
    ]:
        raise ValueError("Unexpected native base world")
    regions, counts, statuses, full = {}, Counter(), Counter(), set()
    for path in sorted((world / "region").glob("*.mca")):
        records = []
        for index, chunk in chunk_records(path):
            statuses[str(chunk["Status"])] += 1
            if str(chunk["Status"]) != "minecraft:full":
                continue
            cx, cz = int(chunk["xPos"]), int(chunk["zPos"])
            if int(chunk["DataVersion"]) != 3700 or chunk["block_entities"]:
                raise ValueError("Unexpected version or block entities")
            if path.name != f"r.{cx // 32}.{cz // 32}.mca" or index != (cx % 32) + (cz % 32) * 32:
                raise ValueError("Misplaced saved chunk")
            expected = np.zeros((384, 16, 16), dtype=np.uint8)
            expected[0], expected[1:119], expected[119:121], expected[121:128] = 1, 2, 3, 4
            for x, y, z, xx, yy, zz, block in commands.get((cx, cz), []):
                expected[y + 64:yy + 65, z % 16:zz % 16 + 1, x % 16:xx % 16 + 1] = block
            sections = {int(section["Y"]): section for section in chunk["sections"]}
            if set(sections) != set(range(-4, 20)) or len(sections) != len(chunk["sections"]):
                raise ValueError("Missing or duplicate native sections")
            for sy, section in sections.items():
                actual = section_names(section, names)
                if not np.array_equal(actual, expected[(sy + 4) * 16:(sy + 5) * 16].ravel()):
                    raise ValueError(f"Source is not pristine at chunk {(cx, cz)}, section {sy}")
                unique, values = np.unique(actual, return_counts=True)
                counts.update({names[k]: int(v) for k, v in zip(unique, values)})
            full.add((cx, cz))
            chunk["LastUpdate"] = nbtlib.Long(0)
            chunk["InhabitedTime"] = nbtlib.Long(0)
            chunk["block_ticks"] = nbtlib.List[nbtlib.Compound]()
            chunk["fluid_ticks"] = nbtlib.List[nbtlib.Compound]()
            buffer = BytesIO()
            chunk.write(buffer)
            payload = zlib.compress(buffer.getvalue())
            records.append((index, (len(payload) + 5 + 4095) // 4096,
                            (len(payload) + 1).to_bytes(4, "big") + b"\x02" + payload))
        if records:
            header, body = bytearray(8192), bytearray()
            for index, sectors, record in records:
                header[index * 4:index * 4 + 4] = (2 + len(body) // 4096).to_bytes(3, "big") + bytes([sectors])
                body.extend(record + bytes(sectors * 4096 - len(record)))
            regions[path.name] = bytes(header + body)
    if not set(commands) <= full:
        raise ValueError("Not every generated resource chunk is fully saved")
    for name, count in manifest["counts"].items():
        if name.endswith("_ore") and counts[name] != count:
            raise ValueError("Resource counts do not match the generation manifest")
    if sum(count for name, count in counts.items() if name.endswith("_log")) != manifest["counts"]["log_blocks"]:
        raise ValueError("Tree counts do not match the generation manifest")
    data["DataPacks"]["Enabled"] = nbtlib.List[nbtlib.String](["vanilla"])
    data["ScheduledEvents"] = nbtlib.List[nbtlib.Compound]()
    data["CustomBossEvents"] = nbtlib.Compound()
    data["LevelName"] = nbtlib.String("LiveQuestBench pristine resource island v2")
    for key in ("Time", "LastPlayed"):
        data[key] = nbtlib.Long(0)
    data["DayTime"] = nbtlib.Long(6000)
    data["raining"], data["thundering"] = nbtlib.Byte(0), nbtlib.Byte(0)
    buffer = BytesIO()
    level.write(buffer)
    files = {"level.dat": gzip.compress(buffer.getvalue(), mtime=0)}
    files.update({f"region/{name}": raw for name, raw in regions.items()})
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    provenance = {
        "source": str(source), "source_world_version": manifest["world_version"],
        "source_level_sha256": digest((world / "level.dat").read_bytes()),
        "source_manifest_sha256": digest((source / "island_manifest.json").read_bytes()),
        "source_generator_sha256_at_generation": manifest["generator_sha256"],
        "source_generator_sha256_at_migration": digest((research / "benchmark/island_generator.py").read_bytes()),
        "source_pack_sha256": manifest["pack_sha256"], "source_checkpoints_sha256": manifest["checkpoints_sha256"],
        "source_region_sha256": {p.name: digest(p.read_bytes()) for p in sorted((world / "region").glob("*.mca"))},
        "source_task_sha256": {p.name: digest(p.read_bytes()) for p in sorted((research / "benchmark/tasks/island").glob("*.yaml"))},
        "source_manifest": manifest,
        "validation": {
            "method": "Every full chunk block name equals the flat ocean base plus all checksum-verified generator fill/setblock commands.",
            "full_chunks": len(full), "checked_blocks": len(full) * 384 * 256,
            "generated_chunks": len(commands), "mismatched_blocks": 0,
            "source_chunk_statuses": dict(statuses), "block_counts": dict(sorted(counts.items())),
            "game_started": False, "model_called": False,
        },
        "export": "Full native chunks only; preserve palettes/properties, heights, biomes and light. Reset chunk times/ticks and world time. Omit protochunks, entities, players, history, dimensions, POI, data/scoreboards, locks and generator datapack. Vanilla flat ocean fills unsaved chunks.",
        "sha256": hashes, "fixture_sha256": digest(canonical(hashes)),
    }
    if destination.exists() or destination.with_suffix(".source.json").exists():
        raise FileExistsError("Refusing to replace an existing immutable fixture")
    destination.mkdir(parents=True)
    for name, raw in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    destination.with_suffix(".source.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance["validation"], indent=2))
    print("fixture_sha256:", provenance["fixture_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research_root", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export(args.research_root.resolve(), args.destination.resolve())
