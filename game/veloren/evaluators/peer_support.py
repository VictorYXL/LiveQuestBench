"""Source-bound peer regeneration during a still-live native encounter."""

from game.veloren.evaluators.encounter import player_damage, team_encounter_checks


def support_checks(initial: dict, final: dict, *, roles: list[str], window_seconds: float) -> dict:
    result = team_encounter_checks(initial, final, roles=roles)
    owner = next(iter(initial))
    evidence = final[owner]["private_encounter_evidence"]
    events = evidence["events"]
    targets = evidence["registry"]["targets"]
    peers = {
        role: row["private_death_evidence"]["registry"]
        for role, row in initial.items()
    }
    qualifying = []
    for event in events:
        if event["event"] != "health_effect_applied":
            continue
        data = event["data"]
        if not (data["changed"] is True and data["after"] > data["before"] and data["requested_amount"] > 0
                and data.get("cause") == {"Buff": "Regeneration"}):
            continue
        contributor = (data["contributor"] or {}).get("Group", {})
        source = next((role for role, peer in peers.items()
                       if peer["uid"] == contributor.get("entity_uid")
                       and peer["server_entity"] == data["contributor_entity"]), None)
        recipient = next((role for role, peer in peers.items()
                          if peer["uid"] == data["target_uid"]
                          and peer["server_entity"] == data["target_entity"]), None)
        group = data.get("contributor_group")
        if (source is None or recipient is None or source == recipient or group is None
                or group != data.get("target_group") or group != contributor.get("group")):
            continue
        for target in targets:
            binding = target["binding"]
            changes = [row for row in events if row["event"] == "health_effect_applied"
                       and row["sequence"] < event["sequence"]
                       and row["data"]["target_uid"] == binding["uid"]
                       and row["data"]["target_entity"] == binding["server_entity"]]
            health = changes[-1]["data"]["after"] if changes else binding["health"]
            if health <= 0:
                continue
            if any(row["event"] == "native_entity_death" and row["sequence"] <= event["sequence"]
                   and row["data"]["uid"] == binding["uid"]
                   and row["data"]["entity"] == binding["server_entity"] for row in events):
                continue
            hits = [row for row in events if row["sequence"] < event["sequence"]
                    and player_damage(row, binding, peers[recipient])
                    and 0 <= data["server_time"] - row["data"]["server_time"] <= window_seconds]
            if hits:
                qualifying.append({
                    "healer": source, "recipient": recipient, "target": target["role"],
                    "damage_sequence": hits[-1]["sequence"], "heal_sequence": event["sequence"],
                    "native_seconds_after_damage": data["server_time"] - hits[-1]["data"]["server_time"],
                    "health_restored": data["after"] - data["before"],
                })
    result["checks"].append({"kind": "peer_heal_after_original_target_damage",
                            "window_seconds": window_seconds, "events": qualifying, "passed": bool(qualifying)})
    result["success"] = all(row["passed"] for row in result["checks"])
    result["semantics"] += " Sourced peer regeneration must follow original-target damage within the native-time window while that target lives."
    return result
