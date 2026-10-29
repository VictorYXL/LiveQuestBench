package org.livequestbench.observer;

import com.google.gson.JsonObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import net.minecraft.block.BlockState;
import net.minecraft.registry.Registries;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.network.ServerPlayerInteractionManager;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.util.math.BlockPos;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ServerPlayerInteractionManager.class)
public abstract class SuccessfulBreakMixin {
    @Shadow protected ServerWorld world;
    @Shadow @Final protected ServerPlayerEntity player;
    @Unique private BlockState livequest$oldState;

    @Inject(method = "tryBreakBlock", at = @At("HEAD"))
    private void livequest$capture(BlockPos pos, CallbackInfoReturnable<Boolean> callback) {
        livequest$oldState = world.getBlockState(pos);
    }

    @Inject(method = "tryBreakBlock", at = @At("RETURN"))
    private void livequest$record(BlockPos pos, CallbackInfoReturnable<Boolean> callback) {
        String destination = System.getProperty("livequest.break.events");
        if (!callback.getReturnValue() || destination == null || livequest$oldState.isAir()
                || world.getBlockState(pos).equals(livequest$oldState)) {
            return;
        }
        JsonObject event = new JsonObject();
        event.addProperty("schema", "livequest-native-successful-break/1");
        event.addProperty("player_uuid", player.getUuidAsString());
        event.addProperty("dimension", world.getRegistryKey().getValue().toString());
        event.addProperty("x", pos.getX());
        event.addProperty("y", pos.getY());
        event.addProperty("z", pos.getZ());
        event.addProperty("old_block_id", Registries.BLOCK.getId(livequest$oldState.getBlock()).toString());
        event.addProperty("native_tick", world.getTime());
        try {
            Files.writeString(Path.of(destination), event + "\n",
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException error) {
            // Evidence failure must be visible but must not change the native break outcome.
            System.err.println("LIVEQUEST_BREAK_EVIDENCE_ERROR " + error);
        }
    }
}
