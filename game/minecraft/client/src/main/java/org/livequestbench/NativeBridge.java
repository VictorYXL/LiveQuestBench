package org.livequestbench;

import com.google.gson.*;
import net.fabricmc.api.ClientModInitializer;
import net.minecraft.block.Block;
import net.minecraft.block.BlockState;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.entity.Entity;
import net.minecraft.entity.ItemEntity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.hit.EntityHitResult;
import net.minecraft.entity.projectile.ProjectileUtil;
import net.minecraft.util.hit.HitResult;
import net.minecraft.util.math.*;
import org.livequestbench.mixin.ChatHudAccessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ArrayBlockingQueue;

public class NativeBridge implements ClientModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("livequest");
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();
    private static final ArrayBlockingQueue<JsonObject> REQUESTS = new ArrayBlockingQueue<>(64);
    private static final PrintStream OUTPUT = new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8);
    private static boolean enabled;
    private static volatile boolean inputClosed;
    private static JsonObject activeRequest;
    private static Job active;
    private static long deadline;
    private static long ticks;

    interface Job {
        JsonObject step();
        default boolean allowsDeadPlayer() { return false; }
    }

    @Override
    public void onInitializeClient() {
        enabled = Boolean.getBoolean("livequest.structured");
        if (!enabled) return;
        Thread input = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    JsonObject request = JsonParser.parseString(line).getAsJsonObject();
                    if (request.get("protocol").getAsInt() != 1 || !request.has("id"))
                        throw new IOException("Invalid native bridge envelope");
                    if (!REQUESTS.offer(request)) error(request, "busy", "Native request queue is full");
                }
            } catch (IOException | RuntimeException error) {
                LOG.error("Native control input failed", error);
            } finally {
                inputClosed = true;
            }
        }, "livequest-stdin");
        input.setDaemon(true);
        input.start();
    }

    static MinecraftClient client() { return MinecraftClient.getInstance(); }
    static JsonObject object(Object... pairs) {
        JsonObject result = new JsonObject();
        for (int i = 0; i < pairs.length; i += 2) result.add((String) pairs[i], JSON.toJsonTree(pairs[i + 1]));
        return result;
    }
    static JsonObject ok(Object... pairs) {
        return object("success", true, "payload", object(pairs));
    }
    static JsonObject fail(String message) {
        return object("success", false, "message", message, "payload", object("failure_kind", "action_refused"));
    }
    private static void reply(JsonObject request, JsonObject result) {
        OUTPUT.println("LIVEQUEST_RPC " + object("protocol", 1, "id", request.get("id"), "ok", true, "result", result));
    }
    private static void error(JsonObject request, String code, String message) {
        OUTPUT.println("LIVEQUEST_RPC " + object("protocol", 1, "id", request.get("id"), "ok", false,
                "error", object("code", code, "message", message)));
    }
    static void release() {
        MinecraftClient mc = client();
        for (KeyBinding key : List.of(mc.options.forwardKey, mc.options.backKey, mc.options.leftKey,
                mc.options.rightKey, mc.options.jumpKey, mc.options.attackKey, mc.options.useKey))
            key.setPressed(false);
        if (mc.interactionManager != null) mc.interactionManager.cancelBlockBreaking();
    }
    private static void cancel() {
        release();
        if (activeRequest != null) error(activeRequest, "cancelled", "Native operation cancelled; applied effects persist");
        activeRequest = null;
        active = null;
    }
    public static void tick() {
        if (!enabled) return;
        ticks++;
        if (inputClosed) { cancel(); enabled = false; return; }
        JsonObject request;
        while ((request = REQUESTS.poll()) != null) {
            try {
                String method = request.get("method").getAsString();
                JsonObject params = request.getAsJsonObject("params");
                if (method.equals("cancel") || method.equals("pause")) {
                    cancel();
                    reply(request, object("stopped", true));
                } else if (method.equals("ready")) {
                    reply(request, object("ready", client().player != null && client().world != null
                            && client().getOverlay() == null && client().currentScreen == null));
                } else if (client().player == null || client().world == null) {
                    error(request, "not_connected", "Native client is not in a world");
                } else if (method.equals("observe")) {
                    reply(request, observe());
                } else if (method.equals("chat_inbox")) {
                    var messages = ((ChatHudAccessor) client().inGameHud.getChatHud()).livequestMessages();
                    List<JsonObject> rows = new ArrayList<>();
                    for (var line : messages)
                        rows.add(object("client_tick", line.creationTick(), "text", line.content().getString()));
                    Collections.reverse(rows);
                    reply(request, object("messages", rows, "scope", "own_native_chat_hud",
                            "history_limit", 100, "history_at_capacity", messages.size() >= 100));
                } else if (method.equals("chat_send")) {
                    String message = params.get("message").getAsString();
                    String recipient = text(params, "recipient", "");
                    if (message.isBlank() || message.length() > 200 || message.startsWith("/")
                            || message.chars().anyMatch(Character::isISOControl)
                            || !recipient.isEmpty() && !recipient.matches("[A-Za-z][A-Za-z0-9_]{0,15}"))
                        throw new IllegalArgumentException("Invalid ordinary chat message or player name");
                    if (recipient.isEmpty()) client().getNetworkHandler().sendChatMessage(message);
                    else client().getNetworkHandler().sendChatCommand("tell " + recipient + " " + message);
                    reply(request, object("submitted_to_server", true, "delivery_confirmed", null));
                } else if (method.equals("resume")) {
                    reply(request, object("ready", true));
                } else if (method.equals("recipes")) {
                    reply(request, NativeInventory.recipes(params));
                } else if (method.equals("action")) {
                    if (active != null) { error(request, "busy", "Another tool is active"); continue; }
                    String name = params.get("name").getAsString();
                    if (!client().player.isAlive() && !name.equals("respawn")) {
                        reply(request, fail("Player is dead; use RespawnTool for native recovery")); continue;
                    }
                    activeRequest = request;
                    deadline = System.nanoTime() + request.get("timeout_ms").getAsLong() * 1_000_000L;
                    active = action(name, params.getAsJsonObject("parameters"));
                } else {
                    error(request, "invalid_method", "Unsupported native bridge method");
                }
            } catch (RuntimeException exception) {
                LOG.error("Native request failed", exception);
                error(request, "native_error", exception.toString());
                if (request == activeRequest) { release(); activeRequest = null; active = null; }
            }
        }
        if (active != null) {
            try {
                if (System.nanoTime() >= deadline) {
                    error(activeRequest, "timeout", "Native tool deadline exceeded; partial effects persist");
                    release(); active = null; activeRequest = null;
                } else if (client().player == null || client().world == null) {
                    error(activeRequest, "not_connected", "Native participant disconnected");
                    release(); active = null; activeRequest = null;
                } else if (!client().player.isAlive() && !active.allowsDeadPlayer()) {
                    reply(activeRequest, fail("Player died; operation stopped without respawn"));
                    release(); active = null; activeRequest = null;
                } else {
                    JsonObject result = active.step();
                    if (result != null) {
                        release(); reply(activeRequest, result);
                        active = null; activeRequest = null;
                    }
                }
            } catch (RuntimeException exception) {
                LOG.error("Native operation failed", exception);
                error(activeRequest, "native_error", exception.toString());
                release(); active = null; activeRequest = null;
            }
        }
    }
    static double number(JsonObject params, String key, double fallback) {
        return params.has(key) ? params.get(key).getAsDouble() : fallback;
    }
    static String text(JsonObject params, String key, String fallback) {
        return params.has(key) ? params.get(key).getAsString() : fallback;
    }
    static Vec3d vector(JsonObject params) {
        return new Vec3d(params.get("x").getAsDouble(), params.get("y").getAsDouble(), params.get("z").getAsDouble());
    }
    static JsonObject vector(Vec3d value) { return object("x", value.x, "y", value.y, "z", value.z); }
    static JsonObject position(BlockPos value) { return object("x", value.getX(), "y", value.getY(), "z", value.getZ()); }
    static String itemName(ItemStack stack) { return Registries.ITEM.getId(stack.getItem()).getPath(); }
    static void look(Vec3d target) {
        Vec3d delta = target.subtract(client().player.getEyePos());
        client().player.setYaw((float) Math.toDegrees(Math.atan2(-delta.x, delta.z)));
        client().player.setPitch((float) -Math.toDegrees(Math.atan2(delta.y, Math.hypot(delta.x, delta.z))));
    }
    static BlockHitResult aimedBlock() {
        HitResult hit = client().player.raycast(4.5, 1, false);
        return hit.getType() == HitResult.Type.BLOCK ? (BlockHitResult) hit : null;
    }
    static JsonObject item(ItemStack stack, int slot) {
        if (stack.isEmpty()) return null;
        return object("name", itemName(stack), "count", stack.getCount(), "slot", slot,
                "description", stack.getName().getString(), "wear", stack.getDamage(),
                "eatable", stack.isFood() ? stack.getItem().getFoodComponent().getHunger() : 0);
    }
    static JsonObject block(BlockPos pos) {
        if (!loaded(pos))
            return object("name", "unknown", "loaded", false, "passable", false);
        BlockState state = client().world.getBlockState(pos);
        boolean liquid = !state.getFluidState().isEmpty();
        boolean passable = state.getCollisionShape(client().world, pos).isEmpty() && !liquid;
        return object("name", Registries.BLOCK.getId(state.getBlock()).getPath(), "loaded", true,
                "state_id", Block.getRawIdFromState(state), "passable", passable,
                "walkable", !passable, "liquid", liquid, "buildable_to", state.isReplaceable(),
                "diggable", state.getHardness(client().world, pos) >= 0);
    }
    private static boolean loaded(BlockPos pos) {
        return pos.getY() >= client().world.getBottomY() && pos.getY() < client().world.getTopY()
                && client().world.isChunkLoaded(pos);
    }
    private static JsonObject observe() {
        var player = client().player;
        var world = client().world;
        JsonArray inventory = new JsonArray(), entities = new JsonArray(), palette = new JsonArray(), data = new JsonArray();
        for (int i = 0; i < 36; i++) {
            ItemStack stack = player.getInventory().getStack(i);
            if (!stack.isEmpty()) inventory.add(item(stack, i + 1));
        }
        for (Entity entity : world.getEntities()) {
            if (entity == player || entity.squaredDistanceTo(player) > 225) continue;
            JsonObject description = object("id", entity.getId(), "name", Registries.ENTITY_TYPE.getId(entity.getType()).getPath(),
                    "type", entity instanceof LivingEntity ? "living" : "other",
                    "display_name", entity.getName().getString(), "position", vector(entity.getPos()),
                    "velocity", vector(entity.getVelocity()),
                    "health", entity instanceof LivingEntity living ? living.getHealth() : null);
            if (entity instanceof ItemEntity dropped) {
                description.addProperty("item_name", itemName(dropped.getStack()));
                description.addProperty("item_count", dropped.getStack().getCount());
            }
            entities.add(description);
        }
        BlockPos min = player.getBlockPos().add(-15, -14, -15);
        Map<Integer, Integer> indices = new HashMap<>();
        for (int z = 0; z < 31; z++) for (int y = 0; y < 31; y++) for (int x = 0; x < 31; x++) {
            BlockPos pos = min.add(x, y, z);
            int state = loaded(pos) ? Block.getRawIdFromState(world.getBlockState(pos)) : -1;
            if (!indices.containsKey(state)) { indices.put(state, palette.size()); palette.add(block(pos)); }
            data.add(indices.get(state));
        }
        BlockHitResult hit = aimedBlock();
        return object("agent_id", player.getGameProfile().getName(), "position", vector(player.getPos()),
                "health", player.getHealth(), "hunger", player.getHungerManager().getFoodLevel(),
                "inventory", inventory, "wielded_item", item(player.getMainHandStack(), player.getInventory().selectedSlot + 1),
                "wield_index", player.getInventory().selectedSlot + 1,
                "look_direction", vector(player.getRotationVec(1)),
                "block_under", block(BlockPos.ofFloored(player.getPos().add(0, -0.01, 0))).get("name"),
                "aimed_node_coords", hit == null ? null : position(hit.getBlockPos()),
                "nearby_entities", entities,
                "nearby_blocks", object("format", "palette_cube", "minp", position(min),
                        "maxp", position(min.add(30, 30, 30)), "dims", object("x", 31, "y", 31, "z", 31),
                        "palette", palette, "data", data, "coordinate_system", "minecraft_block_floor"));
    }
    private static Job action(String name, JsonObject params) {
        MinecraftClient mc = client();
        if (name.equals("respawn")) {
            if (mc.player.isAlive()) return () -> fail("Player is already alive; no respawn requested");
            release();
            mc.player.requestRespawn();
            long submittedAt = ticks;
            long confirmUntil = System.nanoTime() + 10_000_000_000L;
            return new Job() {
                public boolean allowsDeadPlayer() { return true; }
                public JsonObject step() {
                    if (ticks > submittedAt && mc.player.isAlive() && mc.player.getHealth() > 0)
                        return ok("respawned", true, "health", mc.player.getHealth(),
                                "position", vector(mc.player.getPos()));
                    if (System.nanoTime() >= confirmUntil)
                        return fail("Native respawn was not confirmed alive within 10 seconds; request effects persist");
                    return null;
                }
            };
        }
        if (!name.equals("craft") && !name.equals("smelt") && !name.equals("container_take")
                && !name.equals("merchant_inspect") && !name.equals("merchant_trade")
                && !name.equals("furnace_inspect") && !name.equals("furnace_click")
                && mc.currentScreen != null) mc.player.closeHandledScreen();
        switch (name) {
            case "stop": release(); return () -> ok();
            case "strike":
                look(vector(params));
                return () -> {
                    Vec3d eye = mc.player.getEyePos();
                    Vec3d direction = mc.player.getRotationVec(1).multiply(3);
                    double reach = eye.squaredDistanceTo(mc.player.raycast(3, 1, false).getPos());
                    EntityHitResult hit = ProjectileUtil.raycast(
                            mc.player, eye, eye.add(direction),
                            mc.player.getBoundingBox().stretch(direction).expand(1),
                            entity -> !entity.isSpectator() && entity.canHit(), reach);
                    if (hit == null || !hit.getEntity().isAlive())
                        return fail("No living entity along the aimed ray within unobstructed survival reach");
                    mc.interactionManager.attackEntity(mc.player, hit.getEntity());
                    mc.player.swingHand(Hand.MAIN_HAND);
                    return ok("submitted", true, "target_id", hit.getEntity().getId());
                };
            case "attack":
                if (!(mc.crosshairTarget instanceof EntityHitResult target))
                    return () -> fail("No entity under the current crosshair within native reach");
                if (!target.getEntity().isAlive())
                    return () -> fail("The aimed entity is not alive");
                if (mc.player.getEyePos().squaredDistanceTo(target.getPos()) > 9)
                    return () -> fail("The aimed entity is outside ordinary survival attack reach");
                mc.interactionManager.attackEntity(mc.player, target.getEntity());
                mc.player.swingHand(Hand.MAIN_HAND);
                return () -> ok("submitted", true, "target_id", target.getEntity().getId());
            case "use_held":
                long useUntil = System.nanoTime() + (long) (number(params, "duration", 1) * 1e9);
                return () -> {
                    if (System.nanoTime() >= useUntil) return ok("input_released", true);
                    mc.options.useKey.setPressed(true);
                    return null;
                };
            case "select":
                mc.player.getInventory().selectedSlot = params.get("slot").getAsInt() - 1;
                return () -> ok("slot", mc.player.getInventory().selectedSlot + 1);
            case "look": look(vector(params)); return () -> ok();
            case "aim_block":
                BlockPos target = BlockPos.ofFloored(vector(params));
                look(target.toCenterPos());
                return () -> {
                    BlockHitResult hit = aimedBlock();
                    return hit != null && hit.getBlockPos().equals(target) ? ok() : fail("Target is not reachable and visible");
                };
            case "move_forward": case "move_backward": case "move_left": case "move_right": case "jump":
                KeyBinding key = switch (name) {
                    case "move_forward" -> mc.options.forwardKey;
                    case "move_backward" -> mc.options.backKey;
                    case "move_left" -> mc.options.leftKey;
                    case "move_right" -> mc.options.rightKey;
                    default -> mc.options.jumpKey;
                };
                long until = System.nanoTime() + (long) (number(params, "duration", 0.3) * 1e9);
                return () -> {
                    if (System.nanoTime() >= until) return ok("position", vector(mc.player.getPos()));
                    key.setPressed(true);
                    return null;
                };
            case "dig_block":
                BlockPos targetBlock = BlockPos.ofFloored(vector(params));
                return () -> {
                    if (mc.world.getBlockState(targetBlock).isAir()) return ok("after_name", "air");
                    BlockHitResult hit = aimedBlock();
                    if (hit == null || !hit.getBlockPos().equals(targetBlock)) return fail("Block left interaction reach");
                    if (mc.world.getBlockState(targetBlock).getHardness(mc.world, targetBlock) < 0) return fail("Block is unbreakable");
                    mc.interactionManager.updateBlockBreakingProgress(targetBlock, hit.getSide());
                    if (ticks % 4 == 0) mc.player.swingHand(Hand.MAIN_HAND);
                    return null;
                };
            case "place":
                BlockPos support = BlockPos.ofFloored(vector(params));
                Direction side = switch (text(params, "face", "top")) {
                    case "bottom" -> Direction.DOWN; case "north" -> Direction.NORTH;
                    case "south" -> Direction.SOUTH; case "east" -> Direction.EAST;
                    case "west" -> Direction.WEST; default -> Direction.UP;
                };
                Vec3d point = support.toCenterPos().add(Vec3d.of(side.getVector()).multiply(0.499));
                if (point.squaredDistanceTo(mc.player.getEyePos()) > 4.5 * 4.5) return () -> fail("Support outside interaction reach");
                look(point);
                BlockHitResult supportHit = aimedBlock();
                if (supportHit == null || !supportHit.getBlockPos().equals(support) || supportHit.getSide() != side)
                    return () -> fail("Support face is occluded");
                String held = itemName(mc.player.getMainHandStack());
                if (!mc.interactionManager.interactBlock(mc.player, Hand.MAIN_HAND,
                        new BlockHitResult(point, side, support, false)).isAccepted()) return () -> fail("Placement refused");
                mc.player.swingHand(Hand.MAIN_HAND);
                long placedAt = ticks;
                return () -> {
                    if (ticks - placedAt < 5) return null;
                    String actual = Registries.BLOCK.getId(mc.world.getBlockState(support.offset(side)).getBlock()).getPath();
                    return actual.equals(held) ? ok("placed_name", actual) : fail("No matching placed block confirmed");
                };
            case "go_to_position": return NativeNavigation.create(vector(params));
            case "craft": return NativeInventory.craft(params);
            case "smelt": return NativeInventory.smelt(params);
            case "furnace_inspect": return NativeInventory.inspectFurnace();
            case "furnace_click": return NativeInventory.clickFurnace(params);
            case "container_inspect": return NativeInventory.inspectContainer();
            case "container_take": return NativeInventory.takeContainerItem(params);
            case "merchant_inspect": return NativeTrading.inspect();
            case "merchant_trade": return NativeTrading.trade(params);
            default: return () -> fail("Unknown native action: " + name);
        }
    }
}
