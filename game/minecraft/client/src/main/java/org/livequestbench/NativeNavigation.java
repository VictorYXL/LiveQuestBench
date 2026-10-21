package org.livequestbench;

import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Vec3d;
import java.util.*;

final class NativeNavigation {
    private record Node(BlockPos position, double score) {}

    private static boolean standable(BlockPos pos) {
        var world = NativeBridge.client().world;
        return world.isChunkLoaded(pos) && world.isChunkLoaded(pos.up())
                && world.getBlockState(pos).getCollisionShape(world, pos).isEmpty()
                && world.getBlockState(pos.up()).getCollisionShape(world, pos.up()).isEmpty()
                && world.getBlockState(pos).getFluidState().isEmpty()
                && world.getBlockState(pos.up()).getFluidState().isEmpty()
                && !world.getBlockState(pos.down()).getCollisionShape(world, pos.down()).isEmpty()
                && world.getBlockState(pos.down()).getFluidState().isEmpty();
    }

    static NativeBridge.Job create(Vec3d target) {
        var mc = NativeBridge.client();
        BlockPos start = mc.player.getBlockPos(), goal = BlockPos.ofFloored(target);
        if (start.getSquaredDistance(goal) > 64 * 64 || !standable(goal))
            return () -> NativeBridge.fail("Target must be a loaded, standable location within 64 blocks");
        PriorityQueue<Node> open = new PriorityQueue<>(Comparator.comparingDouble(Node::score));
        Map<BlockPos, BlockPos> parents = new HashMap<>();
        Map<BlockPos, Integer> costs = new HashMap<>();
        costs.put(start, 0); open.add(new Node(start, 0));
        int visited = 0;
        while (!open.isEmpty() && visited++ < 4096) {
            BlockPos current = open.remove().position();
            if (current.equals(goal)) break;
            for (int[] direction : new int[][]{{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
                for (int dy : new int[]{0, 1, -1}) {
                    BlockPos next = current.add(direction[0], dy, direction[1]);
                    if (!standable(next) || (dy > 0 && !mc.world.getBlockState(current.up(2)).isAir())) continue;
                    int cost = costs.get(current) + 1 + Math.abs(dy);
                    if (cost < costs.getOrDefault(next, Integer.MAX_VALUE)) {
                        costs.put(next, cost); parents.put(next, current);
                        open.add(new Node(next, cost + Math.sqrt(next.getSquaredDistance(goal))));
                    }
                    break;
                }
            }
        }
        if (!costs.containsKey(goal)) return () -> NativeBridge.fail("No bounded walking path found");
        List<BlockPos> path = new ArrayList<>();
        for (BlockPos at = goal; !at.equals(start); at = parents.get(at)) path.add(at);
        Collections.reverse(path);
        return new NativeBridge.Job() {
            int index;
            long progressed = System.nanoTime();
            Vec3d previous = mc.player.getPos();
            public com.google.gson.JsonObject step() {
                if (index >= path.size()) return NativeBridge.ok("position", NativeBridge.vector(mc.player.getPos()));
                BlockPos waypoint = path.get(index);
                if (!standable(waypoint)) return NativeBridge.fail("Path changed; movement stopped");
                Vec3d desired = Vec3d.ofBottomCenter(waypoint);
                Vec3d delta = desired.subtract(mc.player.getPos());
                if (delta.horizontalLengthSquared() < 0.09 && Math.abs(delta.y) < 0.6) {
                    index++; return null;
                }
                if (mc.player.getPos().squaredDistanceTo(previous) > 0.04) {
                    progressed = System.nanoTime(); previous = mc.player.getPos();
                } else if (System.nanoTime() - progressed > 2_000_000_000L) {
                    return NativeBridge.fail("Navigation made no progress");
                }
                NativeBridge.look(desired.add(0, mc.player.getEyeHeight(mc.player.getPose()), 0));
                mc.options.forwardKey.setPressed(true);
                mc.options.jumpKey.setPressed(delta.y > 0.4);
                return null;
            }
        };
    }
}
