"""Private JSONL control channel to the owned native Minecraft client."""

import asyncio
import json
import math
from uuid import uuid4


class BridgeError(RuntimeError):
    """Transport or participant failure, distinct from an ordinary action refusal."""


class NativeBridge:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self._pending: dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()

    def receive(self, line: str) -> bool:
        if not line.startswith("LIVEQUEST_RPC "):
            return False
        response = json.loads(line.removeprefix("LIVEQUEST_RPC "))
        if not isinstance(response, dict) or response.get("protocol") != 1 or not isinstance(response.get("id"), str):
            raise BridgeError("Malformed native client response")
        future = self._pending.get(response["id"])
        if future is None or future.done():
            return True
        if response.get("ok") is True and isinstance(response.get("result"), dict):
            future.set_result(response["result"])
        else:
            error = response.get("error", {})
            future.set_exception(BridgeError(f"{error.get('code')}: {error.get('message')}"))
        return True

    def disconnected(self, reason: str) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(BridgeError(reason))

    async def request(self, method: str, params: dict, *, timeout: float = 30) -> dict:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("Bridge timeout must be finite and in (0, 300]")
        process = self.process
        if process.returncode is not None or process.stdin is None:
            raise BridgeError("Native Minecraft client is not running")
        identifier = uuid4().hex
        request = json.dumps({
            "protocol": 1, "id": identifier, "method": method, "params": params,
            "timeout_ms": math.ceil(timeout * 1000),
        }, allow_nan=False).encode() + b"\n"
        future = asyncio.get_running_loop().create_future()
        self._pending[identifier] = future
        try:
            async with self._write_lock:
                process.stdin.write(request)
                await process.stdin.drain()
            return await asyncio.wait_for(future, timeout + 0.5)
        except (TimeoutError, asyncio.CancelledError):
            if method != "cancel":
                await self.request("cancel", {}, timeout=5)
            elif process.returncode is None:
                process.terminate()
                raise BridgeError("Native cancellation was not acknowledged; client terminated")
            raise
        except (OSError, ConnectionError) as exc:
            raise BridgeError("Native client transport failed") from exc
        finally:
            self._pending.pop(identifier, None)
