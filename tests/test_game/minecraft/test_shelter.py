from game.minecraft.evaluators.shelter import connected


def corridor():
    return {(x, y, 0): "minecraft:stone" if y == 0 else "minecraft:air"
            for x in range(4) for y in range(5)}


def test_shelter_route_requires_two_high_clearance():
    blocks = corridor()
    assert connected(blocks, (0, 1, 0), {(3, 1, 0)})
    blocks[2, 2, 0] = "minecraft:oak_planks"
    assert not connected(blocks, (0, 1, 0), {(3, 1, 0)})


def test_one_block_step_needs_headroom():
    blocks = corridor()
    blocks[2, 1, 0] = blocks[3, 1, 0] = "minecraft:cobblestone"
    assert connected(blocks, (0, 1, 0), {(3, 2, 0)})
    blocks[1, 3, 0] = "minecraft:oak_planks"
    assert not connected(blocks, (0, 1, 0), {(3, 2, 0)})


def test_water_or_missing_support_is_not_an_accessible_floor():
    blocks = corridor()
    blocks[2, 0, 0] = "minecraft:water"
    assert not connected(blocks, (0, 1, 0), {(3, 1, 0)})
    del blocks[2, 0, 0]
    assert not connected(blocks, (0, 1, 0), {(3, 1, 0)})
