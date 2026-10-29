"""Validated private journal projection for snapshot consumers."""

import json
import os
from pathlib import Path


def snapshot_rows(
    path: Path, run_id: str, *, after_sequence: int | None = None, encounters: bool = False,
    contracts: bool = False, equipment_uid: int | None = None, pickups: bool = False,
) -> list[dict]:
    """Validate every row; retain equipment transitions, not every world-wide health sample."""
    retained = {}
    latest_binding = last = None
    equipment = {}
    sequence = 0
    with path.open("rb") as stream:
        # Bound the read even while the native server continues appending.
        remaining = os.fstat(stream.fileno()).st_size
        while remaining:
            line = stream.readline(remaining)
            if not line:
                raise ValueError("private native journal truncated during snapshot")
            remaining -= len(line)
            if not line.endswith(b"\n"):
                break
            row = json.loads(line)
            if (row["schema"], row["version"], row["private"], row["sequence"]) != (
                "rpg-native-oracle", "1.1", True, sequence,
            ):
                raise ValueError("private native journal schema/sequence mismatch")
            if sequence == 0:
                if row["event"] != "opened" or row["data"]["run_id"] != run_id:
                    raise ValueError("private native journal run mismatch")
                retained[sequence] = row
            elif row["event"] == "opened":
                raise ValueError("multiple native processes in private journal")
            if row["event"] == "combat_entity_bindings":
                latest_binding = row
                changed = []
                for binding in row["data"]["bindings"]:
                    if equipment_uid is not None and binding["uid"] != equipment_uid:
                        continue
                    key = (binding["uid"], binding["server_entity"])
                    current = binding.get("equipment")
                    if key not in equipment or equipment[key] != current:
                        changed.append(binding)
                        equipment[key] = current
                if changed and (contracts or encounters and after_sequence is not None
                                and sequence > after_sequence):
                    retained[sequence] = {**row, "data": {**row["data"], "bindings": changed}}
            elif pickups and row["event"] in {
                "item_drop_created", "item_pickup_applied", "item_drop_expired",
                "item_drop_merged", "item_drop_merged_on_creation",
            }:
                retained[sequence] = row
            elif contracts or after_sequence is not None and sequence > after_sequence and (
                row["event"] == "native_entity_death"
                or encounters and row["event"] in ("health_effect_applied", "attack_health_effect_queued")
            ):
                retained[sequence] = row
            last = row
            sequence += 1
    if last is None:
        raise ValueError("private native journal run mismatch")
    if latest_binding is not None:
        retained[latest_binding["sequence"]] = latest_binding
    retained[last["sequence"]] = last
    return [retained[key] for key in sorted(retained)]
