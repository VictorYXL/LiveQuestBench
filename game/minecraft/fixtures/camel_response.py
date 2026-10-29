"""Unadopted native locomotion diagnostic; no task registration or private score."""
import math


SPEEDS = (0.05, 0.20)


def commands(instance):
    if type(instance) is not int or instance not in range(len(SPEEDS)):
        raise ValueError("Expected one of the two authored native instances")
    result = [
        "tick freeze",
        "gamerule doMobSpawning false", "gamerule doTraderSpawning false",
        "gamerule doDaylightCycle false", "gamerule doWeatherCycle false",
        "time set noon", "weather clear", "kill @e[type=!minecraft:player]",
        "forceload add -48 -16 63 47",
    ]
    # Players continue moving under vanilla tick freeze. Preserve the initial
    # support column until the complete practice floor exists.
    for left, right in ((-39, -8), (-7, 24), (25, 56), (57, 63)):
        result += [
            f"fill {left} 65 -8 {right} 84 39 air",
            f"fill {left} 64 -8 {right} 64 39 bedrock",
            f"fill {left} 65 -8 {right} 67 39 water",
        ]
    result += [
        "fill -44 71 -3 -1 71 4 bedrock",
        "fill -42 71 -1 -25 71 -1 yellow_concrete",
        "fill -42 71 4 -25 71 4 yellow_concrete",
        "fill -4 71 0 0 71 23 bedrock",
        "fill 5 71 20 8 71 23 gold_block",
        "fill 13 71 20 16 71 23 gold_block",
        "fill 21 71 20 24 71 23 yellow_concrete",
        "setworldspawn -42 72 1",
        'summon camel -40.5 72 1.5 {Tags:["lq_camel_response"],PersistenceRequired:1b,'
        'Tame:1b,Age:0,Rotation:[-90f,0f],SaddleItem:{id:"minecraft:saddle",Count:1b},'
        'Attributes:[{Name:"minecraft:generic.movement_speed",Base:'
        + str(SPEEDS[instance]) + '},{Name:"minecraft:horse.jump_strength",Base:0.42d}]}',
        "save-all flush",
    ]
    return result


def application_charge(public_probe_distance):
    """Choose from measured public motion, never the authored instance index."""
    if not math.isfinite(public_probe_distance) or public_probe_distance <= 0:
        raise ValueError("A positive public displacement measurement is required")
    return 0.18 if public_probe_distance > 14 else 0.50


def in_pad(position, index):
    left = (5, 13)[index]
    return left <= position["x"] < left + 4 and 20 <= position["z"] < 24
