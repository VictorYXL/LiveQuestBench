"""Versioned locomotion-calibration course using only native blocks and attributes."""
import math

from game.minecraft.fixtures.camel_response import commands as response_commands


SOURCE = (-42, 72, 3)
DESTINATIONS = ((5, 72, 23), (12, 72, 23))
PADS = ((4, 8, 20, 24), (11, 15, 20, 24))
CARGO = ("camel_pad_a", "camel_pad_b")
PUBLIC_GOAL = (
    "Deliver the two original marked clay parcels from the depot furnace to the "
    "matching A and B furnace INPUT slots. Finish alive with the original courier "
    "camel alive, grounded and stopped on pad B. Each gold/emerald pad is four "
    "blocks square. The same camel's native dash response applies throughout this "
    "episode. The marked practice lanes are optional; discover a useful response "
    "by any legal means. All ordinary actions, dismounting, recovery and shortcuts "
    "are allowed. Do not smelt the parcels. No prescribed probe or initial failure."
)


def commands(instance):
    result = response_commands(instance)
    result += [
        "fill -44 71 -6 40 71 7 bedrock",
        "fill -44 72 -8 -40 84 33 air",
        "fill -44 68 -8 -40 70 33 air",
        "fill -44 71 -8 -40 71 -7 air",
        "fill -44 71 8 -40 71 33 air",
        "fill -44 64 -8 -40 64 33 bedrock",
        "fill -44 65 -8 -40 67 33 water",
        "fill 5 71 20 24 71 23 air",
        "fill 4 71 20 7 71 23 gold_block",
        "fill 11 71 20 14 71 23 emerald_block",
        "fill -45 64 -9 -45 85 34 bedrock",
        "fill 41 64 -9 41 85 34 bedrock",
        "fill -44 64 -9 40 85 -9 bedrock",
        "fill -44 64 34 40 85 34 bedrock",
    ]
    for z in (-5, -1, 3, 7):
        result.append(f"fill -42 71 {z} -25 71 {z} yellow_concrete")
    for z in range(8, 15):
        result.append(f"fill -42 {79-z} {z} -39 {79-z} {z} bedrock")
    for point in DESTINATIONS:
        result.append("setblock " + " ".join(map(str, point)) + " furnace[facing=north]")
    result.append(
        'setblock -42 72 3 furnace[facing=north]{Items:['
        '{Slot:0b,id:"minecraft:clay_ball",Count:1b,tag:{livequest_cargo:"camel_pad_a",'
        'display:{Name:\'{"text":"Pad A clay","italic":false}\'}}},'
        '{Slot:1b,id:"minecraft:clay_ball",Count:1b,tag:{livequest_cargo:"camel_pad_b",'
        'display:{Name:\'{"text":"Pad B clay","italic":false}\'}}}]}'
    )
    result.extend(["kill @e[type=minecraft:item]", "save-all flush"])
    return result


def policy(measurements):
    """Fit launch points to this episode's measurements and public course geometry.

    Flat-floor displacement is an estimate, not a guarantee of airborne reach.
    No unmeasured charge or previously calibrated response is substituted.
    """
    launch_bands = ((-3.5, .5), (4.5, 7.5))
    for measurement in measurements:
        charge, distance = measurement["charge"], measurement["distance"]
        if (not math.isfinite(charge) or not 0 < charge <= .5
                or not math.isfinite(distance) or distance <= 0):
            raise ValueError("A positive measured displacement and valid charge are required")
    for measurement in measurements:
        distance = measurement["distance"]
        launches = tuple(
            max(low, min(high, (pad[0] + pad[1]) / 2 - distance))
            for pad, (low, high) in zip(PADS, launch_bands)
        )
        landings = tuple(launch + distance for launch in launches)
        if all(pad[0] + .5 <= landing <= pad[1] - .5
               for pad, landing in zip(PADS, landings)):
            return {"charge": measurement["charge"], "launch_x": launches,
                    "measured_distance": distance, "predicted_landing_x": landings}
    return None


def on_pad(position, index):
    left, right, near, far = PADS[index]
    return (left <= position["x"] < right and near <= position["z"] < far
            and abs(position["y"] - 72) <= .1)
