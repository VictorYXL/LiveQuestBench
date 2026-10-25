package org.livequestbench;

import com.sun.jna.Function;
import com.sun.jna.Native;
import com.sun.jna.NativeLibrary;
import com.sun.jna.Platform;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.PointerByReference;

public final class LinuxLibraryPath {
    private static final int RTLD_DI_LINKMAP = 2;
    private static final Function DLINFO = NativeLibrary.getInstance(Platform.C_LIBRARY_NAME).getFunction("dlinfo");

    private LinuxLibraryPath() {}

    public static String resolve(long handle) {
        if (handle == 0) {
            throw new IllegalArgumentException("A loaded Linux library handle is required");
        }
        PointerByReference result = new PointerByReference();
        if (DLINFO.invokeInt(new Object[]{new Pointer(handle), RTLD_DI_LINKMAP, result}) != 0
                || result.getValue() == null) {
            throw new IllegalStateException("Could not resolve the loaded Linux library link map");
        }
        // ELF link_map starts with l_addr followed by l_name; the library remains loaded.
        Pointer name = result.getValue().getPointer(Native.POINTER_SIZE);
        if (name == null) {
            throw new IllegalStateException("Loaded Linux library has no link-map name");
        }
        return name.getString(0);
    }
}
