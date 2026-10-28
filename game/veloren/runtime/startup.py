"""Bounded setup-only recovery for native administrator character re-entry."""

from contextlib import AsyncExitStack
from pathlib import Path


async def start_setup_bridge(factory, output: Path, cleanup: AsyncExitStack, *, reconnect: bool):
    for attempt in range(2 if reconnect else 1):
        directory = output if attempt == 0 else output / "administrator-reconnect"
        directory.mkdir(parents=True, exist_ok=True)
        bridge = factory(directory)
        try:
            await bridge.start()
        except BaseException as error:
            await bridge.close()
            # Pending logout persistence can reject the bridge's one-shot character request.
            if (not reconnect or attempt or not isinstance(error, RuntimeError)
                    or "timed out entering the game world" not in str(error)):
                raise
        else:
            cleanup.push_async_callback(bridge.close)
            return bridge
