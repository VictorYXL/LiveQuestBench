"""Private identity-bound native death and player-contribution scoring."""

from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state


def player_damage(event: dict, source: dict, target: dict) -> bool:
    if event["event"] != "health_effect_applied":
        return False
    data = event["data"]
    contributor = data["contributor"]
    uid = (contributor.get("Solo", (contributor.get("Group") or {}).get("entity_uid"))
           if isinstance(contributor, dict) else None)
    return (data["changed"] is True and data["requested_amount"] < 0
            and data["after"] < data["before"] and uid == source["uid"]
            and data["contributor_entity"] == source["server_entity"]
            and data["target_uid"] == target["uid"]
            and data["target_entity"] == target["server_entity"])


def validate_encounter(*, roles: list[str], **state) -> None:
    if (not isinstance(roles, list) or not roles
            or any(not isinstance(role, str) or not role for role in roles)
            or len(set(roles)) != len(roles)):
        raise ValueError("Encounter roles must be unique nonempty names")
    validate_state(**state)


def encounter_checks(initial: dict, final: dict, *, roles: list[str], **state) -> dict:
    validate_encounter(roles=roles, **state)
    first, last = (row["private_encounter_evidence"] for row in (initial, final))
    registry = first["registry"]
    if (first["schema"] != "livequest-encounter/1" or last["schema"] != first["schema"]
            or registry != last["registry"] or not registry["nonce"] or not registry["run_id"]
            or first["events"] or first["through_sequence"] != registry["opening_sequence"]
            or last["through_sequence"] < first["through_sequence"]):
        raise ValueError("Encounter registry or opening evidence changed")
    source, targets = registry["source"], registry["targets"]
    if (source["uid"] != initial["self_identity"]["uid"]
            or source["health"] <= 0 or source["dead"] is not False
            or len(targets) != len(roles) or {row["role"] for row in targets} != set(roles)):
        raise ValueError("Encounter opening lacks the declared living player or targets")
    identities = {(row["binding"]["uid"], row["binding"]["server_entity"]) for row in targets}
    if len(identities) != len(targets) or (source["uid"], source["server_entity"]) in identities:
        raise ValueError("Ambiguous player/target identities")
    events = last["events"]
    previous = first["through_sequence"]
    for event in events:
        if (event["schema"], event["version"], event["private"]) != ("rpg-native-oracle", "1.1", True):
            raise ValueError("Invalid native event schema")
        if not previous < event["sequence"] <= last["through_sequence"]:
            raise ValueError("Native event sequence is not strictly ordered within the boundary")
        if event["event"] not in ("health_effect_applied", "native_entity_death"):
            raise ValueError("Unsupported encounter evidence event")
        previous = event["sequence"]

    def deaths(binding):
        return [row for row in events if row["event"] == "native_entity_death"
                and row["data"]["uid"] == binding["uid"]
                and row["data"]["entity"] == binding["server_entity"]]

    checks = []
    for target in targets:
        binding = target["binding"]
        if binding["alignment"] != "Enemy" or binding["dead"] is not False or binding["health"] <= 0:
            raise ValueError("Target was not a living native enemy at initialization")
        killed = deaths(binding)
        damage = []
        for event in events:
            if (player_damage(event, source, binding)
                    and (not killed or event["sequence"] < killed[0]["sequence"])):
                damage.append(event)
        checks.append({"kind": "encounter", "role": target["role"], "uid": binding["uid"],
                       "native_death": bool(killed), "player_damage_events": len(damage),
                       "damage": sum(row["data"]["before"] - row["data"]["after"] for row in damage),
                       "passed": bool(killed) and bool(damage)})
    checks.append({"kind": "player_never_died", "passed": not deaths(source)})
    result = state_checks(initial, final, **state)
    checks.extend(result["checks"])
    return {"success": all(row["passed"] for row in checks), "checks": checks,
            "semantics": "Designated native UID/entity-generation death, real player damaging contribution "
                         "before death, no player death, and simultaneous terminal requirements. "
                         "No last-blow requirement; disappearance and loot do not prove death. "
                         "Evidence ends at post-gate client snapshot, not an atomic server pause."}


def evaluate_encounter(before: Path, after: Path, *, roles: list[str], **state) -> dict:
    return encounter_checks(*load_pair(before, after), roles=roles, **state)
