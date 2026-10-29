"""Incrementally validate a native journal and retain its latest actor bindings."""

import json
from pathlib import Path


class NativeBindingCursor:
    """Reuse across polls; the first poll still scans all existing complete rows.

    Bindings are the latest complete event, not an atomic live-state query or
    evidence that an absent actor died.
    """

    def __init__(self, path: Path, run_id: str):
        self.path, self.run_id = path, run_id
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
                if row["event"] == "loaded_actor_bindings":
                    self.bindings = row["data"]["bindings"]
                self.sequence += 1
                self.offset = stream.tell()
        return self.bindings
