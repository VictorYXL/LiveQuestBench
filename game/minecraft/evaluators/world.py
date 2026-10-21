"""Read a bounded block region from frozen Minecraft Java 1.20.4 saves.

Uses the Anvil/palette decoding approach of GameAgentVisual's world evaluator.
Missing chunks are missing evidence, never implicit air.
"""

import gzip
from io import BytesIO
from pathlib import Path
import re
import zlib

import nbtlib


Position = tuple[int, int, int]
AIR = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})
DIMENSIONS = {
    "minecraft:overworld": ("", -64, 320),
    "minecraft:the_nether": ("DIM-1", 0, 256),
    "minecraft:the_end": ("DIM1", 0, 256),
}
MAX_REGION_BLOCKS = 262144


def block_name(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(minecraft:)?[a-z0-9_]+", value):
        raise ValueError(f"Expected a vanilla block identifier, got {value!r}")
    return value if ":" in value else "minecraft:" + value


def region_bounds(region: object, dimension: str) -> tuple[Position, Position]:
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unsupported structure dimension: {dimension}")
    if not isinstance(region, dict) or set(region) != {"min", "max"}:
        raise ValueError("Structure evaluation requires region.min and region.max (inclusive XYZ)")
    corners = []
    for key in ("min", "max"):
        values = region[key]
        if not isinstance(values, (list, tuple)) or len(values) != 3 or any(type(v) is not int for v in values):
            raise ValueError(f"region.{key} must contain three integer coordinates")
        corners.append((values[0], values[1], values[2]))
    low, high = corners
    _, min_y, max_y = DIMENSIONS[dimension]
    if any(a > b for a, b in zip(low, high)) or not min_y <= low[1] <= high[1] < max_y:
        raise ValueError("Invalid region ordering or dimension height")
    if any(abs(p[axis]) >= 30000000 for p in corners for axis in (0, 2)):
        raise ValueError("Region exceeds the supported world coordinates")
    volume = (high[0] - low[0] + 1) * (high[1] - low[1] + 1) * (high[2] - low[2] + 1)
    if volume > MAX_REGION_BLOCKS:
        raise ValueError(f"Structure region must contain at most {MAX_REGION_BLOCKS} blocks")
    return low, high


def _chunk(region: Path, x: int, z: int) -> nbtlib.File:
    path = region / f"r.{x // 32}.{z // 32}.mca"
    with path.open("rb") as stream:
        size = path.stat().st_size
        if size < 8192:
            raise ValueError(f"Invalid region file size: {path}")
        stream.seek(4 * ((x % 32) + (z % 32) * 32))
        location = stream.read(4)
        sector, sectors = int.from_bytes(location[:3], "big"), location[3]
        if sector == 0 and sectors == 0:
            raise ValueError(f"Missing saved chunk {(x, z)} in {path}")
        if sector < 2 or sectors == 0 or sector * 4096 + 5 > size:
            raise ValueError(f"Invalid chunk location {(x, z)} in {path}")
        stream.seek(sector * 4096)
        length = int.from_bytes(stream.read(4), "big")
        if not 1 <= length <= sectors * 4096 - 4:
            raise ValueError(f"Invalid chunk payload length {(x, z)}")
        codec = stream.read(1)[0]
        raw = stream.read(length - 1)
        # An acknowledged live save may leave the final sector unpadded.
        if len(raw) != length - 1:
            raise ValueError(f"Truncated chunk payload {(x, z)} in {path}")
        if codec & 128:
            if length != 1:
                raise ValueError(f"Invalid external chunk stub {(x, z)}")
            raw = (region / f"c.{x}.{z}.mcc").read_bytes()
            codec &= 127
        if codec == 1:
            raw = gzip.decompress(raw)
        elif codec == 2:
            raw = zlib.decompress(raw)
        elif codec != 3:
            raise ValueError(f"Unsupported Anvil compression: {codec}")
    data = nbtlib.File.parse(BytesIO(raw))
    if int(data["DataVersion"]) != 3700:
        raise ValueError(f"Structure evaluation requires Minecraft Java 1.20.4: chunk {(x, z)}")
    if (int(data["xPos"]), int(data["zPos"])) != (x, z):
        raise ValueError(f"Saved chunk position mismatch: {(x, z)}")
    if str(data["Status"]).removeprefix("minecraft:") != "full":
        raise ValueError(f"Incomplete saved chunk: {(x, z)}")
    return data


def _section(section: nbtlib.Compound | None) -> list[str]:
    if section is None or "block_states" not in section:
        return ["minecraft:air"] * 4096
    states = section["block_states"]
    palette = [block_name(str(entry["Name"])) for entry in states["palette"]]
    if not 1 <= len(palette) <= 4096:
        raise ValueError("Invalid saved block palette")
    if len(palette) == 1:
        return palette * 4096
    bits = max(4, (len(palette) - 1).bit_length())
    per_long = 64 // bits
    packed = states["data"]
    if len(packed) != (4096 + per_long - 1) // per_long:
        raise ValueError("Invalid packed block-state array length")
    indices = [
        (int(packed[index // per_long]) >> ((index % per_long) * bits)) & ((1 << bits) - 1)
        for index in range(4096)
    ]
    if max(indices) >= len(palette):
        raise ValueError("Saved block palette index is out of bounds")
    return [palette[index] for index in indices]


def read_blocks(
    world: Path, low: Position, high: Position, dimension: str,
) -> dict[Position, str]:
    """Read every requested cell; raise if any selected chunk lacks usable evidence."""
    low, high = region_bounds({"min": low, "max": high}, dimension)
    level = nbtlib.load(Path(world) / "level.dat")
    if int(level["Data"]["DataVersion"]) != 3700:
        raise ValueError("Structure evaluation requires Minecraft Java 1.20.4")
    folder, _, _ = DIMENSIONS[dimension]
    region = Path(world) / folder / "region"
    blocks: dict[Position, str] = {}
    for cx in range(low[0] // 16, high[0] // 16 + 1):
        for cz in range(low[2] // 16, high[2] // 16 + 1):
            chunk = _chunk(region, cx, cz)
            sections = {int(section["Y"]): section for section in chunk["sections"]}
            if len(sections) != len(chunk["sections"]):
                raise ValueError(f"Duplicate saved section in chunk {(cx, cz)}")
            for sy in range(low[1] // 16, high[1] // 16 + 1):
                values = _section(sections.get(sy))
                for y in range(max(low[1], sy * 16), min(high[1], sy * 16 + 15) + 1):
                    for z in range(max(low[2], cz * 16), min(high[2], cz * 16 + 15) + 1):
                        for x in range(max(low[0], cx * 16), min(high[0], cx * 16 + 15) + 1):
                            blocks[x, y, z] = values[(y % 16) * 256 + (z % 16) * 16 + x % 16]
    return blocks
