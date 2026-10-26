"""Preparation observed before combat, followed by native encounter and return goals."""

from pathlib import Path
import re

from game.veloren.evaluators.encounter import encounter_checks, player_damage, validate_encounter
from game.veloren.evaluators.endpoints import load_pair


def validate_expedition(*, chest_item: str, roles: list[str], **state) -> None:
    if not isinstance(chest_item, str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", chest_item):
        raise ValueError("Expedition chest_item must be a native item identifier")
    validate_encounter(roles=roles, **state)
    if state.get("equipment", {}).get("chest") != chest_item or "position" not in state:
        raise ValueError("Expedition must require the prepared chest equipped and a final return position")


def expedition_checks(initial: dict, final: dict, *, chest_item: str, roles: list[str], **state) -> dict:
    validate_expedition(chest_item=chest_item, roles=roles, **state)
    result = encounter_checks(initial, final, roles=roles, **state)
    first, last = (row["private_encounter_evidence"] for row in (initial, final))
    source = first["registry"]["source"]
    expected = {"slot": {"Armor": "Chest"}, "item": {"Simple": chest_item}}
    if expected in source["equipment"]:
        raise ValueError("Expedition player was already prepared at initialization")
    if first["equipment_samples"]:
        raise ValueError("Opening expedition samples must be empty")
    prepared = []
    previous = first["through_sequence"]
    for sample in last["equipment_samples"]:
        if (sample["uid"] != source["uid"] or sample["server_entity"] != source["server_entity"]
                or not previous < sample["sequence"] <= last["through_sequence"]
                or not isinstance(sample["equipment"], list)):
            raise ValueError("Invalid ordered native preparation evidence")
        previous = sample["sequence"]
        if expected in sample["equipment"]:
            prepared.append(sample["sequence"])
    strikes = [event["sequence"] for event in last["events"]
               if any(player_damage(event, source, target["binding"])
                      for target in first["registry"]["targets"])]
    passed = bool(prepared and strikes and min(prepared) < min(strikes))
    result["checks"].insert(0, {
        "kind": "prepared_before_first_damage", "item": chest_item,
        "prepared_sequence": min(prepared) if prepared else None,
        "first_damage_sequence": min(strikes) if strikes else None, "passed": passed,
    })
    result["success"] = result["success"] and passed
    result["semantics"] += (
        " Native server equipment observation must show the prepared chest before the first own "
        "damaging hit on any designated target. This is ordered equipment evidence, not a recipe-event "
        "or continuous-equipment claim; no recovery action is mandatory."
    )
    return result


def evaluate_expedition(before: Path, after: Path, *, chest_item: str, roles: list[str], **state) -> dict:
    return expedition_checks(*load_pair(before, after), chest_item=chest_item, roles=roles, **state)
