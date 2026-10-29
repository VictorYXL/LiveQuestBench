from game.minecraft.evaluators.shaft import supported_route


def test_a_continuous_ladder_exit_passes_but_a_removed_section_does_not():
    blocks = {(x, y, 0): "minecraft:air" for x in (0, 1) for y in range(7)}
    blocks[0, 0, 0] = blocks[1, 3, 0] = "minecraft:stone"
    ladders = {(0, y, 0) for y in (1, 2, 3)}
    for point in ladders:
        blocks[point] = "minecraft:ladder"
    assert supported_route(blocks, ladders, (0, 1, 0), (1, 4, 0))
    blocks[0, 2, 0] = "minecraft:air"
    assert not supported_route(blocks, ladders - {(0, 2, 0)}, (0, 1, 0), (1, 4, 0))


def test_a_vertical_pillar_is_not_a_reusable_ascent():
    blocks = {(x, y, 0): "minecraft:air" for x in (0, 1) for y in range(7)}
    for y in range(4):
        blocks[0, y, 0] = "minecraft:cobblestone"
    blocks[1, 0, 0] = "minecraft:stone"
    assert not supported_route(blocks, set(), (1, 1, 0), (0, 4, 0))


def test_gathered_timber_steps_and_noncolliding_lighting_are_legal():
    blocks = {(x, y, 0): "minecraft:air" for x in range(3) for y in range(6)}
    for x, material in enumerate(("birch_planks", "spruce_log", "andesite")):
        blocks[x, x, 0] = f"minecraft:{material}"
    blocks[1, 2, 0] = "minecraft:torch"
    assert supported_route(blocks, set(), (0, 1, 0), (2, 3, 0))
    assert supported_route(blocks, set(), (2, 3, 0), (0, 1, 0))
    blocks[1, 2, 0] = "minecraft:cobblestone"
    assert not supported_route(blocks, set(), (0, 1, 0), (2, 3, 0))
