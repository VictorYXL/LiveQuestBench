"""Join native attack emission to applied damage, never nearby input timestamps."""


def attack_join(events: list[dict], effect: dict) -> dict | None:
    applied = effect["data"]
    contributor = applied["contributor"]
    uid = (contributor.get("Solo", (contributor.get("Group") or {}).get("entity_uid"))
           if isinstance(contributor, dict) else None)
    matches = []
    for event in events:
        if event["event"] != "attack_health_effect_queued" or event["sequence"] >= effect["sequence"]:
            continue
        queued = event["data"]
        if (uid is not None and queued["source_uid"] == uid
                and queued["source_entity"] == applied["contributor_entity"]
                and queued["target_uid"] == applied["target_uid"]
                and queued["target_entity"] == applied["target_entity"]
                and queued["instance"] == applied["instance"]
                and queued["requested_amount"] == applied["requested_amount"]
                and queued["server_time"] == applied["change_time"]):
            matches.append(event)
    return matches[0] if len(matches) == 1 else None


def qualifying_attack(events: list[dict], effect: dict, requirement: dict) -> bool:
    if effect["data"]["cause"] != {"Attack": requirement["source"]}:
        return False
    joined = attack_join(events, effect)
    if joined is None:
        raise ValueError("Missing or ambiguous native attack/application causal join")
    data = joined["data"]
    ability = data["ability"]
    if ability is None:
        raise ValueError("Native attack lacks its originating ability")
    return (data["attack_source"] == requirement["source"] and ability["tool"] == requirement["tool"]
            and ("ability" not in requirement or ability["ability"] == requirement["ability"]))


def causes_native_death(effect: dict, death: dict) -> bool:
    """A zero-health hit is not lethal proof if death protection or another cause intervenes."""
    if "cause" not in death["data"]:
        raise ValueError("Native death lacks its recorded causal HealthChange")
    cause = death["data"]["cause"]
    if cause is None:
        return False
    applied = effect["data"]
    return (cause["instance"] == applied["instance"] and cause["time"] == applied["change_time"]
            and cause["amount"] == applied["requested_amount"] and cause["by"] == applied["contributor"]
            and cause["cause"] == applied["cause"])
