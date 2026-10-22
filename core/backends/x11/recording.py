"""Record fresh bound-window frames independently of Agent observations."""

import asyncio
from pathlib import Path
import shutil

from core.backends.x11.capture import WindowCapture


class WindowRecording:
    def __init__(self, window_id: int, display_name: str, path: Path, fps: int = 10,
                 *, title_prefix: str, class_tokens: tuple[str, ...] = ()):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required when recording is enabled")
        if type(fps) is not int or not 1 <= fps <= 60:
            raise ValueError("recording fps must be an integer in [1, 60]")
        self.window_id, self.display_name, self.path, self.fps = window_id, display_name, path, fps
        self.title_prefix, self.class_tokens = title_prefix, class_tokens
        self._stop = asyncio.Event()
        self.task: asyncio.Task | None = None
        self._capture: WindowCapture | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._stderr: asyncio.Task | None = None

    async def start(self) -> None:
        self._capture = WindowCapture(self.display_name, title_prefix=self.title_prefix,
                                      class_tokens=self.class_tokens)
        try:
            first = self._capture.capture(self.window_id).image
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-use_wallclock_as_timestamps", "1",
                "-f", "rawvideo", "-pixel_format", "rgb24",
                "-video_size", f"{first.width}x{first.height}", "-framerate", str(self.fps),
                "-i", "pipe:0", "-an", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(self.path),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            assert self._process.stderr is not None
            self._stderr = asyncio.create_task(self._process.stderr.read())
            assert self._process.stdin is not None
            self._process.stdin.write(first.tobytes())
            await self._process.stdin.drain()
            self.task = asyncio.create_task(self._record(first.size))
        except BaseException:
            await self.stop()
            raise

    async def _record(self, size: tuple[int, int]) -> None:
        assert self._capture is not None and self._process is not None and self._process.stdin is not None
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), 1 / self.fps)
                break
            except TimeoutError:
                pass
            frame = await asyncio.to_thread(self._capture.capture, self.window_id)
            if frame.image.size != size:
                raise RuntimeError("Recorded window resized; video dimensions must stay fixed")
            self._process.stdin.write(frame.image.tobytes())
            await self._process.stdin.drain()

    async def stop(self) -> None:
        self._stop.set()
        try:
            if self.task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(self.task), 10)
                except TimeoutError:
                    if self._process is not None and self._process.returncode is None:
                        self._process.kill()
                    await self.task
                    raise RuntimeError("Recording worker did not stop in time")
        finally:
            try:
                if self._process is not None:
                    if self._process.stdin is not None:
                        self._process.stdin.close()
                    try:
                        await asyncio.wait_for(self._process.wait(), 15)
                    except TimeoutError:
                        self._process.kill()
                        await self._process.wait()
                        raise RuntimeError("Video finalization timed out")
                    errors = await self._stderr if self._stderr is not None else b""
                    if self._process.returncode != 0:
                        raise RuntimeError("Video encoding failed: " + errors.decode(errors="replace")[-2000:])
            finally:
                if self._capture is not None:
                    self._capture.close()
