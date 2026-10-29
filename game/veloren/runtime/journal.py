"""Validated private journal projection for snapshot consumers."""

import json
import os
from pathlib import Path


def snapshot_rows(
    path: Path, run_id: str, *, after_sequence: int | None = None, encounters: bool = False,
    contracts: bool = False, equipment_uid: int | None = None, pickups: bool = False,
    prefix: dict | None = None, prepare_prefix: dict | None = None,
) -> list[dict]:
    """Validate every row; retain equipment transitions, not every world-wide health sample."""
    retained = {}
    pickup_rows = {}
    latest_binding = last = None
    equipment = {}
    sequence = 0
    valid_offset = 0
    if prefix is not None:
        if (contracts or prepare_prefix is not None or prefix["run_id"] != run_id
                or after_sequence is not None and after_sequence < prefix["next_sequence"] - 1):
            raise ValueError("private native journal prefix does not cover this snapshot")
        retained[0] = prefix["opening"]
        if pickups:
            retained.update(prefix["pickup_rows"])
        latest_binding, last = prefix["latest_binding"], prefix["last"]
        equipment = dict(prefix["equipment"])
        sequence, valid_offset = prefix["next_sequence"], prefix["offset"]
    if prepare_prefix is not None and (contracts or after_sequence is not None or equipment_uid is not None):
        raise ValueError("private native journal prefix requires a complete setup projection")
    with path.open("rb") as stream:
        # Bound the read even while the native server continues appending.
        boundary = os.fstat(stream.fileno())
        if prefix is not None and (
            (boundary.st_dev, boundary.st_ino) != prefix["file_identity"] or boundary.st_size < valid_offset
        ):
            raise ValueError("private native journal replaced or truncated after prefix validation")
        stream.seek(valid_offset)
        remaining = boundary.st_size - valid_offset
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
            elif (pickups or prepare_prefix is not None) and row["event"] in {
                "item_drop_created", "item_pickup_applied", "item_drop_expired",
                "item_drop_merged", "item_drop_merged_on_creation",
            }:
                pickup_rows[sequence] = row
                if pickups:
                    retained[sequence] = row
            elif contracts or after_sequence is not None and sequence > after_sequence and (
                row["event"] == "native_entity_death"
                or encounters and row["event"] in ("health_effect_applied", "attack_health_effect_queued")
            ):
                retained[sequence] = row
            last = row
            sequence += 1
            valid_offset = stream.tell()
    if last is None:
        raise ValueError("private native journal run mismatch")
    if latest_binding is not None:
        retained[latest_binding["sequence"]] = latest_binding
    retained[last["sequence"]] = last
    if prepare_prefix is not None:
        prepare_prefix.update(
            run_id=run_id, opening=retained[0], latest_binding=latest_binding, last=last,
            equipment=equipment, next_sequence=sequence, offset=valid_offset,
            file_identity=(boundary.st_dev, boundary.st_ino),
            pickup_rows=pickup_rows,
        )
    return [retained[key] for key in sorted(retained)]
