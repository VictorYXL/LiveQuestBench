"""Private identity-bound native death and player-contribution scoring."""

from pathlib import Path
import math

from game.veloren.evaluators.endpoints import finite, load_pair, state_checks, validate_state


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


def validate_encounter(*, roles: list[str], companion: dict | None = None, **state) -> None:
    if (not isinstance(roles, list) or not roles
            or any(not isinstance(role, str) or not role for role in roles)
            or len(set(roles)) != len(roles)):
        raise ValueError("Encounter roles must be unique nonempty names")
    if companion is not None:
        if not isinstance(companion, dict) or set(companion) != {"max_distance", "min_health"}:
            raise ValueError("companion requires max_distance and min_health")
        if any(finite(value, key) <= 0 for key, value in companion.items()):
            raise ValueError("Companion distance and health thresholds must be positive")
    validate_state(**state)


def _combat_checks(
    initial: dict, final: dict, *, roles: list[str], require_death: bool,
    companion: dict | None = None, **state,
) -> dict:
    validate_encounter(roles=roles, companion=companion, **state)
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
                       "passed": bool(damage) and (bool(killed) or not require_death)})
    if companion is not None:
        registered = registry["companion"]
        pet = registered["binding"]
        if (pet["alignment"] != {"Owned": source["uid"]} or source["group"] is None
                or pet["group"] != source["group"] or pet["dead"] is not False
                or pet["health"] <= 0 or pet["health"] != pet["maximum_health"]
                or (pet["uid"], pet["server_entity"]) in identities
                or pet["uid"] == source["uid"]):
            raise ValueError("Companion opening lacks a distinct, fully healthy native owned group member")
        public = next((row for row in final["nearby_entities"] if row["uid"] == pet["uid"]), None)
        current = last["companion_binding"]
        distance = None
        visible_alive = False
        if public is not None:
            point = public["position"]
            if not isinstance(point, list) or len(point) != 3:
                raise ValueError("Companion position must contain native XYZ")
            distance = math.dist([finite(value, "companion position") for value in point], final["position"])
            visible_alive = (
                public["control_target"] == registered["player_target"]
                and public["companion"]["owned_by_actor"] is True and public["same_native_group"] is True
                and public["health"] is not None and public["health"]["dead"] is False
                and finite(public["health"]["current"], "companion health") >= companion["min_health"]
                and distance <= companion["max_distance"]
            )
        native_alive = (
            current is not None and current["uid"] == pet["uid"] and current["server_entity"] == pet["server_entity"]
            and current["alignment"] == {"Owned": source["uid"]} and current["dead"] is False
            and finite(current["health"], "native companion health") >= companion["min_health"]
            and public is not None and current["group"] == public["group"]
        )
        killed = bool(deaths(pet))
        checks.append({"kind": "companion_preserved", "uid": pet["uid"], "native_death": killed,
                       "distance": distance, "minimum_health": companion["min_health"],
                       "maximum_distance": companion["max_distance"],
                       "passed": visible_alive and native_alive and not killed})
    checks.append({"kind": "player_never_died", "passed": not deaths(source)})
    result = state_checks(initial, final, **state)
    checks.extend(result["checks"])
    return {"success": all(row["passed"] for row in checks), "checks": checks,
            "semantics": ("Designated native UID/entity-generation death, real player damaging contribution "
                          "before death, " if require_death else
                          "Designated native UID/entity-generation target, no kill required, "
                          "real player damaging contribution before any target death, ")
                         + "no player death, and simultaneous terminal requirements. "
                         "No last-blow requirement; disappearance and loot do not prove death. "
                         "Evidence ends at post-gate client snapshot, not an atomic server pause."
                         + (" Original owned companion must never die and remain alive, owned, grouped and "
                            "within the declared terminal distance; no required support input." if companion else "")}


def encounter_checks(initial: dict, final: dict, *, roles: list[str], **state) -> dict:
    return _combat_checks(initial, final, roles=roles, require_death=True, **state)


def damage_checks(initial: dict, final: dict, *, roles: list[str], **state) -> dict:
    return _combat_checks(initial, final, roles=roles, require_death=False, **state)


def evaluate_encounter(before: Path, after: Path, *, roles: list[str], **state) -> dict:
    return encounter_checks(*load_pair(before, after), roles=roles, **state)


def evaluate_damage(before: Path, after: Path, *, roles: list[str], **state) -> dict:
    return damage_checks(*load_pair(before, after), roles=roles, **state)
