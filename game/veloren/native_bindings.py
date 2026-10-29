"""Incrementally validate a native journal and retain its latest actor bindings."""

import asyncio
import json
from pathlib import Path
import time


class NativeBindingCursor:
    """Reuse across polls; the first poll still scans all existing complete rows.

    Bindings are the latest complete event, not an atomic live-state query or
    evidence that an absent actor died.
    """

    def __init__(self, path: Path, run_id: str, *, binding_event="loaded_actor_bindings"):
        if binding_event not in ("loaded_actor_bindings", "combat_entity_bindings"):
            raise ValueError("Unsupported native binding event")
        self.path, self.run_id = path, run_id
        self.binding_event = binding_event
        self.offset = self.sequence = 0
        self.bindings: list[dict] = []

    def poll(self) -> list[dict]:
        with self.path.open("rb") as stream:
            if self.path.stat().st_size < self.offset:
                raise ValueError("Native binding journal was truncated")
            stream.seek(self.offset)
            while line := stream.readline():
                if not line.endswith(b"\n"):
                    break
                row = json.loads(line)
                if (row["schema"], row["version"], row["private"], row["sequence"]) != (
                        "rpg-native-oracle", "1.1", True, self.sequence):
                    raise ValueError("Native binding journal schema/sequence mismatch")
                if self.sequence == 0:
                    if row["event"] != "opened" or row["data"]["run_id"] != self.run_id:
                        raise ValueError("Native binding journal run mismatch")
                elif row["event"] == "opened":
                    raise ValueError("Multiple native processes in binding journal")
                if row["event"] == self.binding_event:
                    self.bindings = row["data"]["bindings"]
                self.sequence += 1
                self.offset = stream.tell()
        return self.bindings


async def combat_binding(actor, uid: int, *, timeout: float = 10) -> dict:
    """Keep the original latest-snapshot binding rule without repeated full scans."""
    cursor = getattr(actor, "_native_combat_binding_cursor", None)
    if cursor is None:
        cursor = NativeBindingCursor(
            actor.out / "private-native-oracle.ndjson", actor.out.name,
            binding_event="combat_entity_bindings",
        )
        actor._native_combat_binding_cursor = cursor
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        bindings = await asyncio.to_thread(cursor.poll)
        matches = [row for row in bindings if row["uid"] == uid]
        if len(matches) > 1:
            raise ValueError("ambiguous native entity binding")
        if matches:
            return matches[0]
        await asyncio.sleep(.1)
    raise RuntimeError(f"private native UID/entity binding unavailable: {uid}")
