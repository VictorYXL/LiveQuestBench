"""Credential-free stdio transport shared by isolated Python Agent workers."""

import json
import signal
import sys
import threading


class WorkerStopped(BaseException):
    """Bypass native retry handlers when the benchmark terminates a worker."""


class WorkerBridge:
    def __init__(self) -> None:
        self.output = sys.stdout
        self.config = json.loads(sys.stdin.readline())
        self._lock = threading.Lock()
        self._sequence = 0

    def rpc(self, operation: str, **payload: object) -> object:
        with self._lock:
            self._sequence += 1
            self.output.write(json.dumps({"id": self._sequence, "op": operation, **payload}) + "\n")
            self.output.flush()
            line = sys.stdin.readline()
            if not line:
                raise WorkerStopped("Benchmark bridge closed")
            reply = json.loads(line)
            if reply.get("id") != self._sequence:
                raise RuntimeError("Mismatched benchmark bridge reply")
            return reply["result"]

    def exit(self, reason: str, message: str, native_reason: str) -> None:
        self.output.write(json.dumps({"op": "exit", "result": {
            "reason": reason, "message": message, "native_reason": native_reason,
        }}) + "\n")
        self.output.flush()

    def install_stop_handler(self) -> None:
        def stop(*_: object) -> None:
            raise WorkerStopped("Benchmark requested termination")
        signal.signal(signal.SIGTERM, stop)
