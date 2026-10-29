"""Export player-free v4 native assets; change only the reviewed camel speed in variant1."""
import argparse
from io import BytesIO
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zlib

import nbtlib

from game.minecraft.evaluators.camel_delivery import original_camel
from game.minecraft.fixtures import camel_delivery_flush_v4 as fixture
from game.minecraft.runtime.session import validate_world


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_speed(world, expected, replacement):
    changes = 0
    for path in sorted((world / "entities").glob("r.*.*.mca")):
        original = path.read_bytes()
        if not original:
            continue
        data = bytearray(original)
        for index in range(1024):
            offset = int.from_bytes(original[index * 4:index * 4 + 3], "big") * 4096
            if not offset:
                continue
            length = int.from_bytes(original[offset:offset + 4], "big")
            codec = original[offset + 4]
            payload = original[offset + 5:offset + 4 + length]
            decoded = gzip.decompress(payload) if codec == 1 else zlib.decompress(payload) if codec == 2 else payload
            chunk = nbtlib.File.parse(BytesIO(decoded))
            changed = False
            for entity in chunk["Entities"]:
                if (str(entity.get("id")) != "minecraft:camel"
                        or "lq_camel_response" not in list(map(str, entity.get("Tags", [])))):
                    continue
                attribute = next(row for row in entity["Attributes"]
                                 if str(row["Name"]) == "minecraft:generic.movement_speed")
                if float(attribute["Base"]) != expected:
                    raise ValueError("Unexpected original native movement attribute")
                attribute["Base"] = nbtlib.Double(replacement)
                changes += 1
                changed = True
            if changed:
                buffer = BytesIO()
                chunk.write(buffer)
                compressed = zlib.compress(buffer.getvalue())
                block = (len(compressed) + 1).to_bytes(4, "big") + b"\x02" + compressed
                sectors = (len(block) + 4095) // 4096
                if sectors >= 256:
                    raise ValueError("Entity chunk exceeds ordinary region storage")
                data.extend(b"\0" * ((-len(data)) % 4096))
                new_offset = len(data) // 4096
                data[index * 4:index * 4 + 4] = new_offset.to_bytes(3, "big") + bytes([sectors])
                data.extend(block + b"\0" * (sectors * 4096 - len(block)))
        if data != original:
            path.write_bytes(data)
    if changes != 1:
        raise ValueError("Expected exactly one original camel attribute change")


def export(snapshot, destination):
    manifest = json.loads((snapshot / "_livequest_snapshot.json").read_text())
    for name, digest in manifest["sha256"].items():
        if sha(snapshot / name) != digest:
            raise ValueError(f"Native source snapshot changed: {name}")
    identity, original = original_camel(snapshot)
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, speed in enumerate((.05, .20)):
        world = destination / f"instance_{index}"
        shutil.copytree(snapshot, world, ignore=shutil.ignore_patterns(
            "session.lock", "playerdata", "advancements", "stats",
            "_livequest_snapshot.json", "level.dat_old",
        ))
        level = nbtlib.load(world / "level.dat")
        if "Player" in level["Data"]:
            del level["Data"]["Player"]
            level.save()
        if index:
            rewrite_speed(world, .05, speed)
        actual_identity, actual = original_camel(world)
        if actual_identity != identity:
            raise ValueError("Original camel identity changed")
        expected = original.copy()
        expected["Attributes"] = nbtlib.List[nbtlib.Compound]([
            nbtlib.Compound({**attribute, **(
                {"Base": nbtlib.Double(speed)}
                if str(attribute["Name"]) == "minecraft:generic.movement_speed" else {}
            )}) for attribute in original["Attributes"]
        ])
        if actual.snbt() != nbtlib.Compound(expected).snbt():
            raise ValueError("Native entity changed beyond its reviewed movement attribute")
        validate_world(world)
        rows.append({
            "path": world.name, "movement_speed": speed,
            "recipe_sha256": hashlib.sha256(json.dumps(
                fixture.commands(index), separators=(",", ":"), ensure_ascii=True,
            ).encode()).hexdigest(),
            "files": {str(p.relative_to(world)): sha(p) for p in sorted(world.rglob("*")) if p.is_file()},
        })
    data = {
        "schema": "livequest-native-camel-variants/4",
        "condition": fixture.VERSION,
        "selection": "uniform_once_before_episode",
        "worlds": rows,
        "source_snapshot_manifest_sha256": sha(snapshot / "_livequest_snapshot.json"),
        "source_snapshot": str(snapshot),
        "exporter_sha256": sha(Path(__file__)),
        "method": "Player-free native v4 before snapshot; variant1 differs only in the stored "
                  "original camel movement attribute, matching reviewed commands(1). "
                  "Offline export, not a new native execution.",
    }
    (destination / "native-camel-variants.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"exported": str(destination), "instances": len(rows),
                      "native_episodes": 0, "manifest_sha256": sha(destination / "native-camel-variants.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export(args.snapshot, args.destination)
