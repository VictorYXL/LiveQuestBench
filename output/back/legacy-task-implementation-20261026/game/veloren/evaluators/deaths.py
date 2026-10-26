"""Private native player-death accounting, independent of task success."""

from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair


def death_snapshot(rows: list[dict], identity: dict, registry: dict | None = None) -> dict:
    snapshot = next((row for row in reversed(rows) if row["event"] == "combat_entity_bindings"), None)
    if snapshot is None:
        raise ValueError("Native player death accounting lacks a binding snapshot")
    bindings = snapshot["data"]["bindings"]
    matches = [row for row in bindings if row["uid"] == identity["uid"]]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous native player death binding")
    binding = matches[0]
    if registry is None:
        if binding["dead"] is not False or binding["health"] <= 0:
            raise ValueError("Death accounting requires a living opening player")
        registry = {
            "run_id": rows[0]["data"]["run_id"], "nonce": rows[0]["data"]["nonce"],
            "opening_sequence": rows[-1]["sequence"], "identity": identity,
            "uid": binding["uid"], "server_entity": binding["server_entity"],
        }
    if (registry["identity"] != identity
            or registry["server_entity"] != binding["server_entity"]
            or registry["nonce"] != rows[0]["data"]["nonce"]
            or registry["run_id"] != rows[0]["data"]["run_id"]):
        raise ValueError("Native death-accounting session or player identity changed")
    events = []
    for row in rows:
        if (row["sequence"] > registry["opening_sequence"]
                and row["event"] == "native_entity_death" and row["data"]["uid"] == registry["uid"]):
            if row["data"]["entity"] != registry["server_entity"]:
                raise ValueError("Native player death belongs to a different entity generation")
            events.append(row)
    return {
        "schema": "livequest-player-deaths/1", "registry": registry,
        "through_sequence": rows[-1]["sequence"], "events": events,
    }


def death_metrics(initial: dict, final: dict) -> dict:
    first, last = (row["private_death_evidence"] for row in (initial, final))
    registry = first["registry"]
    if (first["schema"] != "livequest-player-deaths/1" or last["schema"] != first["schema"]
            or registry != last["registry"] or not registry["nonce"] or not registry["run_id"]
            or registry["identity"] != initial["self_identity"]
            or registry["identity"] != final["self_identity"]
            or registry["uid"] != registry["identity"]["uid"]
            or first["events"] or first["through_sequence"] != registry["opening_sequence"]
            or last["through_sequence"] < first["through_sequence"]):
        raise ValueError("Invalid player-death registry or boundary")
    previous = first["through_sequence"]
    for event in last["events"]:
        if ((event["schema"], event["version"], event["private"], event["event"])
                != ("rpg-native-oracle", "1.1", True, "native_entity_death")
                or not previous < event["sequence"] <= last["through_sequence"]
                or event["data"]["uid"] != registry["uid"]
                or event["data"]["entity"] != registry["server_entity"]
                or not isinstance(event["host_unix_ns"], str)
                or not event["host_unix_ns"].isascii() or not event["host_unix_ns"].isdecimal()):
            raise ValueError("Invalid native player-death event")
        previous = event["sequence"]
    return {"deaths": {
        "count": len(last["events"]), "source": "native_entity_death",
        "events": last["events"],
        "semantics": "Original player UID/server generation; opening to terminal private snapshot. "
                     "Native host_unix_ns timestamps are server wall-clock times, not runner monotonic times. "
                     "Respawn does not reset the count; this metric does not change task success.",
    }}


def evaluate_deaths(before: Path, after: Path) -> dict:
    return death_metrics(*load_pair(before, after))
