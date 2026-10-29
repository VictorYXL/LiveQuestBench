"""Isolated, unadmitted flush-receptacle variant of courier v3."""

from game.minecraft.fixtures import camel_delivery as v3
from game.minecraft.evaluators.camel_delivery import evaluate as evaluate_native


VERSION = "courier-v4-flush-destination-furnaces"
DESTINATIONS = tuple((x, y - 1, z) for x, y, z in v3.DESTINATIONS)
PUBLIC_GOAL = v3.PUBLIC_GOAL + (
    " The destination furnace tops are flush with the pad surfaces."
)


def commands(instance):
    replacements = {
        f"setblock {x} {y} {z} furnace[facing=north]":
        f"setblock {x} {y - 1} {z} furnace[facing=north]"
        for x, y, z in v3.DESTINATIONS
    }
    original = v3.commands(instance)
    if any(original.count(command) != 1 for command in replacements):
        raise ValueError("The versioned base must contain each destination exactly once")
    return [replacements.get(command, command) for command in original]


def evaluate(before, after, player_uuid):
    return evaluate_native(before, after, player_uuid, destinations=DESTINATIONS)
