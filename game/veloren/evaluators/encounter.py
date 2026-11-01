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


def validate_encounter(*, roles: list[str], companion: dict | None = None,
                       companions: dict[str, dict] | None = None,
                       no_death: bool = True, required_attack: dict | None = None, **state) -> None:
    if required_attack is not None:
        if (not isinstance(required_attack, dict)
                or set(required_attack) - {"source", "tool", "lethal", "ability"}
                or {"source", "tool", "lethal"} - required_attack.keys()
                or required_attack["source"] not in ("Melee", "Projectile", "Beam")
                or required_attack["tool"] not in ("Bow", "Sword", "Sceptre", "Staff")
                or type(required_attack["lethal"]) is not bool):
            raise ValueError("required_attack requires native source, tool and boolean lethal")
    if type(no_death) is not bool:
        raise ValueError("no_death must be boolean")
    if (not isinstance(roles, list) or not roles
            or any(not isinstance(role, str) or not role for role in roles)
            or len(set(roles)) != len(roles)):
        raise ValueError("Encounter roles must be unique nonempty names")
    if companion is not None and companions is not None:
        raise ValueError("Score companion or companions, not both")
    if companions is not None and (
        not isinstance(companions, dict) or not 1 <= len(companions) <= 3
        or any(not isinstance(role, str) or not role for role in companions)
    ):
        raise ValueError("companions requires one to three named companion requirements")
    for companion in ([companion] if companion is not None else (companions or {}).values()):
        if (not isinstance(companion, dict)
                or {"max_distance", "min_health"} - companion.keys()
                or companion.keys() - {"max_distance", "min_health", "min_health_fraction", "healing_required",
                                       "heal_while_target_alive"}):
            raise ValueError("companion requires max_distance and min_health")
        if (finite(companion["max_distance"], "max_distance") <= 0
                or finite(companion["min_health"], "min_health") < 0):
            raise ValueError("Companion distance must be positive and health floor nonnegative")
        if "min_health_fraction" in companion and not 0 < finite(companion["min_health_fraction"], "fraction") <= 1:
            raise ValueError("Companion health fraction must be in (0, 1]")
        if "healing_required" in companion and type(companion["healing_required"]) is not bool:
            raise ValueError("Companion healing_required must be boolean")
        if ("heal_while_target_alive" in companion
                and (type(companion["heal_while_target_alive"]) is not bool
                     or companion["heal_while_target_alive"] and not companion.get("healing_required"))):
            raise ValueError("Live-target companion healing requires sourced healing")
    validate_state(**state)


def _combat_checks(
    initial: dict, final: dict, *, roles: list[str], require_death: bool,
    companion: dict | None = None, companions: dict[str, dict] | None = None, no_death: bool = True,
    required_attack: dict | None = None,
    _contributors: list[dict] | None = None, **state,
) -> dict:
    validate_encounter(roles=roles, companion=companion, companions=companions, no_death=no_death,
                       required_attack=required_attack, **state)
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
        if event["event"] not in ("health_effect_applied", "native_entity_death", "attack_health_effect_queued"):
            raise ValueError("Unsupported encounter evidence event")
        previous = event["sequence"]

    def deaths(binding):
        return [row for row in events if row["event"] == "native_entity_death"
                and row["data"]["uid"] == binding["uid"]
                and row["data"]["entity"] == binding["server_entity"]]

    def alive_before(binding, sequence):
        changes = [row for row in events if row["event"] == "health_effect_applied"
                   and row["sequence"] < sequence and row["data"]["target_uid"] == binding["uid"]
                   and row["data"]["target_entity"] == binding["server_entity"]]
        health = changes[-1]["data"]["after"] if changes else binding["health"]
        return health > 0 and not any(row["sequence"] < sequence for row in deaths(binding))

    checks = []
    contributors = _contributors or [{
        **source, "opening_sequence": first["through_sequence"],
        "closing_sequence": last["through_sequence"],
    }]
    for target in targets:
        binding = target["binding"]
        if binding["alignment"] != "Enemy" or binding["dead"] is not False or binding["health"] <= 0:
            raise ValueError("Target was not a living native enemy at initialization")
        killed = deaths(binding)
        damage = []
        for event in events:
            if (any(player_damage(event, actor, binding)
                    and actor["opening_sequence"] < event["sequence"] <= actor["closing_sequence"]
                    for actor in contributors)
                    and (not killed or event["sequence"] < killed[0]["sequence"])):
                damage.append(event)
        checks.append({"kind": "encounter", "role": target["role"], "uid": binding["uid"],
                       "native_death": bool(killed), "player_damage_events": len(damage),
                       "damage": sum(row["data"]["before"] - row["data"]["after"] for row in damage),
                       "passed": bool(damage) and (bool(killed) or not require_death)})
        if required_attack is not None:
            from game.veloren.evaluators.attack import causes_native_death, qualifying_attack
            qualified = [row for row in damage if qualifying_attack(events, row, required_attack)]
            lethal = [row for row in qualified if required_attack["lethal"] and killed and row["data"]["before"] > 0
                      and row["data"]["after"] <= 0 and causes_native_death(row, killed[0])]
            checks.append({
                "kind": "required_attack", "role": target["role"],
                "qualifying_hits": len(qualified),
                "qualifying_lethal_hits": len(lethal) if required_attack["lethal"] else None,
                "requirement": required_attack,
                "passed": bool(qualified) and (not required_attack["lethal"] or bool(killed) and bool(lethal)),
            })
    pet_requirements = []
    if companions is not None:
        registered_pets = registry.get("companions")
        current_pets = last.get("companion_bindings")
        if (not isinstance(registered_pets, dict) or set(registered_pets) != set(companions)
                or not isinstance(current_pets, dict) or set(current_pets) != set(companions)
                or "companion" in registry):
            raise ValueError("Companion registry and terminal bindings must match all declared roles")
        pet_identities = [row["binding"] for row in registered_pets.values()]
        if (len({row["uid"] for row in pet_identities}) != len(pet_identities)
                or len({row["server_entity"] for row in pet_identities}) != len(pet_identities)):
            raise ValueError("Companion roles must bind distinct original native identities")
        pet_requirements = [(role, requirement, registered_pets[role], current_pets[role])
                            for role, requirement in companions.items()]
    elif companion is not None:
        pet_requirements = [(None, companion, registry["companion"], last["companion_binding"])]
    for role, requirement, registered, current in pet_requirements:
        pet = registered["binding"]
        if (pet["alignment"] != {"Owned": source["uid"]} or source["group"] is None
                or pet["group"] != source["group"] or pet["dead"] is not False
                or pet["health"] <= 0 or pet["health"] != registered.get("initial_health", pet["maximum_health"])
                or (pet["uid"], pet["server_entity"]) in identities
                or pet["uid"] == source["uid"]):
            raise ValueError("Companion opening lacks a distinct native owned group member at its declared health")
        public = next((row for row in final["nearby_entities"] if row["uid"] == pet["uid"]), None)
        requirement = {**requirement, "min_health": max(
            requirement["min_health"], pet["maximum_health"] * requirement.get("min_health_fraction", 0))}
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
                and 0 < finite(public["health"]["current"], "companion health") >= requirement["min_health"]
                and distance <= requirement["max_distance"]
            )
        native_alive = (
            current is not None and current["uid"] == pet["uid"] and current["server_entity"] == pet["server_entity"]
            and current["alignment"] == {"Owned": source["uid"]} and current["dead"] is False
            and 0 < finite(current["health"], "native companion health") >= requirement["min_health"]
            and public is not None and current["group"] == public["group"]
        )
        killed = bool(deaths(pet))
        checks.append({"kind": "companion_preserved", "uid": pet["uid"], "native_death": killed,
                       **({"role": role} if role is not None else {}),
                       "distance": distance, "minimum_health": requirement["min_health"],
                       "maximum_distance": requirement["max_distance"],
                       "passed": visible_alive and native_alive and not killed})
        if requirement.get("healing_required"):
            heals = []
            for event in events:
                if event["event"] != "health_effect_applied":
                    continue
                data = event["data"]
                contributor = data["contributor"] or {}
                group = data.get("contributor_group")
                if (data["changed"] is True and data["after"] > data["before"]
                        and data["requested_amount"] > 0 and data["target_uid"] == pet["uid"]
                        and data["target_entity"] == pet["server_entity"]
                        and contributor.get("Group", {}).get("entity_uid") == source["uid"]
                        and data["contributor_entity"] == source["server_entity"]
                        and group is not None and group == data.get("target_group")
                        and contributor["Group"]["group"] == group
                        and data.get("cause") == {"Buff": "Regeneration"}):
                    if requirement.get("heal_while_target_alive") and not any(
                        alive_before(target["binding"], event["sequence"]) for target in targets
                    ):
                        continue
                    heals.append(event)
            checks.append({"kind": "player_sourced_companion_healing", "events": heals,
                           **({"role": role} if role is not None else {}),
                           "while_original_target_alive": requirement.get("heal_while_target_alive", False),
                           "health_restored": sum(row["data"]["after"] - row["data"]["before"] for row in heals),
                           "passed": bool(heals)})
    if no_death:
        checks.append({"kind": "player_never_died", "passed": not deaths(source)})
    result = state_checks(initial, final, **state)
    checks.extend(result["checks"])
    return {"success": all(row["passed"] for row in checks), "checks": checks,
            "semantics": ("Designated native UID/entity-generation death, real player damaging contribution "
                          "before death, " if require_death else
                          "Designated native UID/entity-generation target, no kill required, "
                          "real player damaging contribution before any target death, ")
                         + ("no player death, and " if no_death else
                            "player death measured separately, and ")
                         + "simultaneous terminal requirements. "
                         + ("The required native attack must cause the lethal health change. "
                            if required_attack is not None and required_attack["lethal"]
                            else "No last-blow requirement. ")
                         + "Disappearance and loot do not prove death. "
                         "Evidence ends at post-gate client snapshot, not an atomic server pause."
                         + (" Original owned companion must never die and remain alive, owned, grouped and "
                            "within the declared terminal distance." if companion else "")
                         + (" Actual player-sourced regeneration must restore companion health."
                            if companion and companion.get("healing_required") else "")
                         + (" Every named original companion must independently satisfy preservation and "
                            "its declared actual player-sourced healing requirement." if companions else "")}


def team_encounter_checks(initial: dict[str, dict], final: dict[str, dict], *, roles: list[str],
                          min_health: float = 1) -> dict:
    """Use the owner's journal and each peer's independently bound native identity."""
    from game.veloren.evaluators.deaths import death_metrics

    if set(initial) != set(final) or len(initial) < 2:
        raise ValueError("Team encounter requires matching participant boundaries")
    owner = next(iter(initial))
    registry = initial[owner]["private_encounter_evidence"]["registry"]
    contributors = []
    for role, first in initial.items():
        last = final[role]
        death_metrics(first, last)
        opening, closing = (row["private_death_evidence"] for row in (first, last))
        identity = opening["registry"]
        if (identity["run_id"] != registry["run_id"] or identity["nonce"] != registry["nonce"]
                or identity["uid"] in {row["binding"]["uid"] for row in registry["targets"]}):
            raise ValueError("Team contributor is not a distinct player in the encounter session")
        contributors.append({
            "uid": identity["uid"], "server_entity": identity["server_entity"],
            "opening_sequence": opening["through_sequence"],
            "closing_sequence": closing["through_sequence"],
        })
    if len({row["uid"] for row in contributors}) != len(contributors):
        raise ValueError("Team contributors must have distinct native identities")
    opening_sequence = max(row["opening_sequence"] for row in contributors)
    bindings = contributors + [row["binding"] for row in registry["targets"]]
    if any(row["sequence"] <= opening_sequence and encounter_event_involves(row, bindings)
           for row in final[owner]["private_encounter_evidence"]["events"]):
        raise ValueError("Combat occurred across non-atomic team opening snapshots")
    for row in contributors:
        row["opening_sequence"] = opening_sequence
    result = _combat_checks(
        initial[owner], final[owner], roles=roles, require_death=True, no_death=False,
        _contributors=contributors, min_health=min_health,
    )
    for role in initial:
        result["checks"].append({
            "kind": "participant_alive", "role": role,
            "passed": state_checks(initial[role], final[role], min_health=min_health)["success"],
        })
    result["success"] = all(row["passed"] for row in result["checks"])
    result["semantics"] = (
        "Owner's identity-bound native target deaths with pre-death damage from any registered peer. "
        "Each contributor is bound to the same journal run/nonce and its own snapshot interval; "
        "both players must finish alive. No equal-damage or last-blow requirement. "
        "Sequential terminal snapshots are non-atomic; target evidence ends at the owner's snapshot."
    )
    return result


def encounter_event_involves(event: dict, bindings: list[dict]) -> bool:
    """The server journal also contains unrelated NPC combat elsewhere in the world."""
    data = event["data"]
    if event["event"] == "native_entity_death":
        identities = [(data["uid"], data["entity"])]
    elif event["event"] == "attack_health_effect_queued":
        identities = [(data["source_uid"], data["source_entity"]),
                      (data["target_uid"], data["target_entity"])]
    elif event["event"] == "health_effect_applied":
        contributor = data["contributor"] or {}
        uid = contributor.get("Solo", (contributor.get("Group") or {}).get("entity_uid"))
        identities = [(uid, data["contributor_entity"]),
                      (data["target_uid"], data["target_entity"])]
    else:
        raise ValueError("Unsupported encounter evidence event")
    # Either identity component is enough to reject contamination, including a
    # malformed/rebound generation; the regular scorer still validates all rows.
    return any(uid == binding["uid"] or entity == binding["server_entity"]
               for uid, entity in identities for binding in bindings)


def encounter_checks(initial: dict, final: dict, *, roles: list[str], **state) -> dict:
    return _combat_checks(initial, final, roles=roles, require_death=True, **state)


def damage_checks(initial: dict, final: dict, *, roles: list[str], **state) -> dict:
    return _combat_checks(initial, final, roles=roles, require_death=False, **state)


def evaluate_encounter(before: Path, after: Path, *, roles: list[str], **state) -> dict:
    return encounter_checks(*load_pair(before, after), roles=roles, **state)


def evaluate_damage(before: Path, after: Path, *, roles: list[str], **state) -> dict:
    return damage_checks(*load_pair(before, after), roles=roles, **state)


def evaluate_escort(before: Path, after: Path, *, roles: list[str], companion: dict) -> dict:
    """Validate original companion preservation without requiring enemy engagement."""
    initial, final = load_pair(before, after)
    result = _combat_checks(initial, final, roles=roles, require_death=False,
                            no_death=False, companion=companion, min_health=0)
    result["checks"] = [row for row in result["checks"] if row["kind"] != "encounter"]
    result["success"] = all(row["passed"] for row in result["checks"])
    result["semantics"] = (
        "Original native owned companion remains alive, grouped and within the declared distance. "
        "Avoiding or defeating enemies is legal; no damage quotas or NPC path controller."
    )
    evidence = final["private_encounter_evidence"]
    pet = evidence["registry"]["companion"]["binding"]
    changes = [row["data"] for row in evidence["events"]
               if row["event"] == "health_effect_applied" and row["data"]["changed"] is True
               and row["data"]["target_uid"] == pet["uid"]
               and row["data"]["target_entity"] == pet["server_entity"]]
    current = evidence["companion_binding"]
    terminal_health = (current["health"] if current is not None
                       and current["uid"] == pet["uid"]
                       and current["server_entity"] == pet["server_entity"] else None)
    observed = [pet["health"], *[row["after"] for row in changes]]
    if terminal_health is not None:
        observed.append(terminal_health)
    result["diagnostics"] = {
        "initial_health": pet["health"], "terminal_health": terminal_health,
        "minimum_observed_health": min(observed),
        "summed_health_loss": sum(max(0, row["before"] - row["after"]) for row in changes),
        "summed_health_restoration": sum(max(0, row["after"] - row["before"]) for row in changes),
        "semantics": "Original companion native health changes, not a counterfactual protection benefit.",
    }
    return result
