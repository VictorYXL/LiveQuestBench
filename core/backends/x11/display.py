"""Owned Xvfb lifecycle for an isolated experiment display."""

import asyncio


class VirtualDisplay:
    def __init__(self):
        self.process: asyncio.subprocess.Process | None = None

    async def start(self) -> str:
        self.process = await asyncio.create_subprocess_exec(
            "Xvfb", "-displayfd", "1", "-screen", "0", "1024x768x24",
            "-nolisten", "tcp",
            stdout=asyncio.subprocess.PIPE,
        )
        assert self.process.stdout is not None
        # Xvfb writes the allocated display number only after it is ready.
        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=15)
        number = line.decode("ascii").strip()
        if not number.isdecimal() or self.process.returncode is not None:
            raise RuntimeError("Xvfb failed to start; see its stderr output")
        return ":" + number

    async def close(self) -> None:
        if self.process is None or self.process.returncode is not None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
            raise RuntimeError("Xvfb shutdown timed out; forced termination")
