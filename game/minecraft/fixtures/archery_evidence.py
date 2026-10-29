"""Passive vanilla target-hit ownership and native bow-use evidence."""

import json
from pathlib import Path


TARGETS = {"application_1": (18, 73, 0), "application_2": (28, 77, 0)}


def pack():
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 26, "description": "Passive owned archery evidence"}},
        "data/minecraft/tags/functions/load.json": {"values": ["livequest_archery:load"]},
        "data/minecraft/tags/functions/tick.json": {"values": ["livequest_archery:tick"]},
        "data/livequest_archery/functions/load.mcfunction":
            "scoreboard objectives add lq_bow minecraft.used:minecraft.bow\n"
            "scoreboard objectives add lq_prev dummy\n",
        "data/livequest_archery/functions/tick.mcfunction":
            "execute as @a unless score @s lq_prev matches 0.. run scoreboard players set @s lq_prev 0\n"
            "execute as @a if score @s lq_bow > @s lq_prev run function livequest_archery:shot\n",
    }

    def event(kind, target=None):
        value = {"kind": kind}
        if target:
            value["target"] = target
        return [
            "data modify storage livequest:archery events append value " + json.dumps(value),
            "data modify storage livequest:archery events[-1].player set from entity @s UUID",
            "execute store result storage livequest:archery events[-1].tick long 1 run time query gametime",
            "execute store result storage livequest:archery events[-1].shots int 1 run scoreboard players get @s lq_bow",
        ]

    files["data/livequest_archery/functions/shot.mcfunction"] = "\n".join(
        event("shot") + ["scoreboard players operation @s lq_prev = @s lq_bow"]
    ) + "\n"
    for name, (x, y, z) in TARGETS.items():
        files[f"data/livequest_archery/advancements/{name}.json"] = {
            "criteria": {"hit": {"trigger": "minecraft:target_hit", "conditions": {
                "signal_strength": {"min": 1},
                "projectile": {"type": "minecraft:arrow", "location": {"position": {
                    "x": {"min": x - 4, "max": x + 1},
                    "y": {"min": y - 2, "max": y + 3},
                    "z": {"min": z - 2, "max": z + 2},
                }}},
            }}},
            "rewards": {"function": f"livequest_archery:{name}"},
        }
        files[f"data/livequest_archery/functions/{name}.mcfunction"] = "\n".join(
            event("target_hit", name)
            + [f"advancement revoke @s only livequest_archery:{name}"]
        ) + "\n"
    return files


def install(world: Path):
    root = world / "datapacks/livequest_archery"
    for name, contents in pack().items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contents, indent=2) + "\n" if isinstance(contents, dict) else contents)


def evaluate_events(events, player, *, start_tick, end_tick, initial_shots=0, budget=12):
    """Validate diagnostic events; this is not a full-task or learning scorer."""
    identity = list(player)
    hits, shots, previous_tick = set(), initial_shots, start_tick
    for event in events:
        if list(event["player"]) != identity:
            continue
        tick, count = int(event["tick"]), int(event["shots"])
        if not start_tick <= tick <= end_tick or tick < previous_tick or count < shots:
            raise ValueError("Invalid owned archery event ordering")
        previous_tick = tick
        if event["kind"] == "shot":
            if count <= shots:
                raise ValueError("Shot event must advance the native launch counter")
            shots = count
        elif event["kind"] == "target_hit":
            if event["target"] not in TARGETS or count < 1:
                raise ValueError("Invalid native target-hit identity")
            hits.add(event["target"])
            shots = count
        else:
            raise ValueError("Unknown archery event")
    used = shots - initial_shots
    return {"owned_targets": sorted(hits), "native_launches": used,
            "application_diagnostic_success": hits == set(TARGETS) and 0 < used <= budget}
