"""Owned displays survive gaps between preflight and runtime capture clients."""

import asyncio
import shutil

import pytest

pytest.importorskip("Xlib")
pytest.importorskip("PIL")

from game.backends.x11.capture import WindowCapture
from game.backends.x11.display import VirtualDisplay


@pytest.mark.skipif(shutil.which("Xvfb") is None, reason="Xvfb is not installed")
def test_capture_can_reconnect_after_last_client_closes(tmp_path):
    async def exercise():
        server = VirtualDisplay()
        try:
            name = await server.start(tmp_path / "xvfb.log")
            for _ in range(20):
                with WindowCapture(name, title_prefix="Minecraft", class_tokens=("minecraft", "lwjgl")):
                    pass
        finally:
            await server.close()

    asyncio.run(exercise())
