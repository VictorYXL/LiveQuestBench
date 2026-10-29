"""Score the physical original lock tokens and real owned arrow launches."""
import math
import nbtlib

from game.minecraft.fixtures.archery_evidence import evaluate_events


def tick(world):
    return int(nbtlib.load(world / "level.dat")["Data"]["Time"])


def evaluate_lock(before, after, player):
    native = nbtlib.load(after / "playerdata" / f"{player}.dat")
    tokens = {str(item.get("tag", {}).get("livequest_token", "")) for item in native["Inventory"]}
    raw = nbtlib.load(after / "data/command_storage_livequest.dat")["data"]["contents"]
    events = raw.get("archery", {}).get("events", [])
    events = events.unpack() if hasattr(events, "unpack") else list(events)
    identity = [int.from_bytes(player.bytes[i:i+4], "big", signed=True) for i in range(0, 16, 4)]
    evidence = evaluate_events(events, identity, start_tick=tick(before), end_tick=tick(after))
    x, y, z = map(float, native["Pos"])
    returned = (float(native["Health"]) > 0 and str(native["Dimension"]) == "minecraft:overworld"
                and math.hypot(x-.5, z-.5) < 3 and abs(y-72) < .5)
    complete = {"target_1", "target_2"} <= tokens
    return {"success": bool(complete and returned and evidence["application_diagnostic_success"]),
            "checks": {"original_tokens": sorted(tokens-{""}), "both_tokens": complete,
                       "living_return": returned, **evidence}}
