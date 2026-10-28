import asyncio
from contextlib import AsyncExitStack

import pytest

from game.veloren.runtime.startup import start_setup_bridge


def test_reconnect_preserves_first_attempt_and_retires_both_bridges(tmp_path):
    attempts = []

    class Bridge:
        def __init__(self, path):
            self.path, self.closed = path, False
            attempts.append(self)

        async def start(self):
            (self.path / "receipt").write_text("native attempt")
            if len(attempts) == 1:
                raise RuntimeError("native bridge fatal: timed out entering the game world")

        async def close(self):
            self.closed = True

    async def run():
        async with AsyncExitStack() as cleanup:
            bridge = await start_setup_bridge(Bridge, tmp_path, cleanup, reconnect=True)
            assert bridge is attempts[1]
            assert attempts[0].closed and not bridge.closed
            assert (tmp_path / "receipt").read_text() == "native attempt"
            assert bridge.path == tmp_path / "administrator-reconnect"
        assert all(bridge.closed for bridge in attempts)

    asyncio.run(run())


@pytest.mark.parametrize(
    "reconnect,message,expected_attempts",
    [
        (False, "timed out entering the game world", 1),
        (True, "server denied authentication", 1),
        (True, "timed out entering the game world", 2),
    ],
)
def test_reconnect_is_bounded_and_only_for_existing_world_entry(
    tmp_path, reconnect, message, expected_attempts
):
    attempts = []

    class Bridge:
        def __init__(self, path):
            self.closed = False
            attempts.append(self)

        async def start(self):
            raise RuntimeError(message)

        async def close(self):
            self.closed = True

    async def run():
        async with AsyncExitStack() as cleanup:
            with pytest.raises(RuntimeError, match=message):
                await start_setup_bridge(Bridge, tmp_path, cleanup, reconnect=reconnect)
        assert len(attempts) == expected_attempts
        assert all(bridge.closed for bridge in attempts)

    asyncio.run(run())
