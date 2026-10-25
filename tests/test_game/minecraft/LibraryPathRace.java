import com.sun.jna.Function;
import com.sun.jna.NativeLibrary;
import com.sun.jna.Platform;
import com.sun.jna.Pointer;
import java.util.concurrent.CountDownLatch;
import org.livequestbench.LinuxLibraryPath;
import org.lwjgl.system.linux.LinuxLibrary;

public class LibraryPathRace {
    public static void main(String[] args) throws Exception {
        Function open = NativeLibrary.getInstance(Platform.C_LIBRARY_NAME).getFunction("dlopen");
        Function close = NativeLibrary.getInstance(Platform.C_LIBRARY_NAME).getFunction("dlclose");
        LinuxLibrary target = new LinuxLibrary("libm.so.6");
        String expected = target.getPath();
        if (!expected.equals(LinuxLibraryPath.resolve(target.address()))) {
            throw new AssertionError("Resolved library paths differ");
        }
        try {
            LinuxLibraryPath.resolve(0);
            throw new AssertionError("Null library handle accepted");
        } catch (IllegalArgumentException expectedFailure) {
        }
        CountDownLatch start = new CountDownLatch(1);
        Thread loader = new Thread(() -> {
            try {
                start.await();
                for (int i = 0; i < 20000; i++) {
                    Pointer handle = open.invokePointer(new Object[]{args[0], 2});
                    if (handle == null || close.invokeInt(new Object[]{handle}) != 0) {
                        throw new AssertionError("Probe library load/unload failed");
                    }
                }
            } catch (InterruptedException error) {
                throw new RuntimeException(error);
            }
        });
        Thread resolver = new Thread(() -> {
            try {
                start.await();
                for (int i = 0; i < 20000; i++) {
                    if (!expected.equals(LinuxLibraryPath.resolve(target.address()))) {
                        throw new AssertionError("Path changed under concurrent loading");
                    }
                }
            } catch (InterruptedException error) {
                throw new RuntimeException(error);
            }
        });
        loader.setUncaughtExceptionHandler((thread, error) -> { error.printStackTrace(); System.exit(2); });
        resolver.setUncaughtExceptionHandler((thread, error) -> { error.printStackTrace(); System.exit(2); });
        loader.start();
        resolver.start();
        start.countDown();
        loader.join();
        resolver.join();
        target.free();
        System.out.println("PASS: 20000 concurrent library loads and path resolutions");
    }
}
