package org.livequestbench.mixin;

import org.livequestbench.LinuxLibraryPath;
import org.lwjgl.system.SharedLibrary;
import org.lwjgl.system.linux.LinuxLibrary;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(value = LinuxLibrary.class, remap = false)
public abstract class LinuxLibraryMixin implements SharedLibrary {
    // Backport LWJGL/lwjgl3#1148 without changing the pinned rendering libraries.
    @Inject(method = "getPath", at = @At("HEAD"), cancellable = true, remap = false)
    private void livequestLibraryPath(CallbackInfoReturnable<String> callback) {
        callback.setReturnValue(LinuxLibraryPath.resolve(address()));
    }
}
