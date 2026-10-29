"""Native setup scheduling preserves exact geometry and column dependencies."""

import math

from game.veloren import fixture as fixtures


def test_authoring_clusters_reduce_native_anchor_moves_without_changing_geometry():
    voxels = {
        (x, y, z) for x in range(-20, 20) for y in range(-16, 16) for z in range(1, 10)
        if x in (-20, 19) or y in (-16, 15) or z == 9
    }
    ordered = fixtures.native_authoring_order(voxels)
    assert len(ordered) == len(voxels) and {tuple(point) for point in ordered} == voxels
    columns = {}
    for x, y, z in ordered:
        assert z > columns.get((x, y), -math.inf)
        columns[x, y] = z

    def native_anchor_moves(points):
        anchor, moves = None, 0
        for x, y, z in points:
            top = [x + .5, y + .5, z + 1]
            if anchor is None or math.dist(anchor[:2], top[:2]) > 8 or abs(anchor[2] - top[2]) > 1.5:
                anchor, moves = [top[0], top[1], top[2] + .8], moves + 1
        return moves

    assert native_anchor_moves(ordered) < native_anchor_moves(sorted(voxels)) / 2
