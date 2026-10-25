"""Private episode death counts from saved vanilla statistics, not tool attempts."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

from game.minecraft.evaluators.state import custom_statistics


def evaluate_deaths(before: Path, after: Path, player: UUID) -> dict:
    metadata = []
    for world, phase in ((before, "ready"), (after, "ended")):
        meta = json.loads((world / "_livequest_snapshot.json").read_text())
        if meta["phase"] != phase or meta["player_uuid"] != str(player):
            raise ValueError("Native death snapshot phase or player identity changed")
        relative = f"stats/{player}.json"
        path = world / relative
        expected = meta["sha256"].get(relative)
        if expected is None:
            if path.exists():
                raise ValueError("Native statistics are absent from the snapshot manifest")
        elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Native statistics are missing or differ from the snapshot checksum")
        metadata.append(meta)
    if metadata[0]["copied_at_ns"] > metadata[1]["capture_started_at_ns"]:
        raise ValueError("Native death snapshot boundaries overlap or are reversed")
    first = custom_statistics(before, player).get("minecraft:deaths", 0)
    last = custom_statistics(after, player).get("minecraft:deaths", 0)
    if last < first:
        raise ValueError("Native death count moved backwards")
    return {"deaths": {
        "count": last - first,
        "before_count": first,
        "after_count": last,
        "source": "minecraft:custom/minecraft:deaths",
        "semantics": "native_player_deaths_during_episode",
        "player_uuid": str(player),
    }}
