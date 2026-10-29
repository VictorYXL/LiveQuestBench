"""Joint original-source collection and unchanged native encounter requirements."""

from pathlib import Path

from game.veloren.evaluators.encounter import encounter_checks, validate_encounter
from game.veloren.evaluators.endpoints import load_pair
from game.veloren.evaluators.pickups import collection_checks, validate_supplies


def validate_encounter_supplies(*, supplies, **encounter):
    validate_supplies(supplies=supplies)
    validate_encounter(**encounter)


def encounter_supply_checks(initial, final, *, supplies, **encounter):
    validate_encounter_supplies(supplies=supplies, **encounter)
    combat = initial["private_encounter_evidence"]["registry"]
    pickup = initial["private_pickup_evidence"]["registry"]
    if (any(combat[key] != pickup[key] for key in ("run_id", "nonce", "opening_sequence"))
            or any(combat["source"][key] != pickup["actor"][key]
                   for key in ("uid", "server_entity"))
            or final["private_encounter_evidence"]["through_sequence"]
            != final["private_pickup_evidence"]["through_sequence"]):
        raise ValueError("Supply and encounter evidence must share the original world, player and boundary")
    declared = [{"item": row["item"], "amount": row["amount"]} for row in pickup["sources"]]
    if declared != supplies:
        raise ValueError("Supply requirement differs from the original native source registry")
    result = encounter_checks(initial, final, **encounter)
    collection = collection_checks(initial, final)
    result["checks"].extend(collection["checks"])
    result["native_pickup_events"] = collection["native_pickup_events"]
    result["native_expiry_events"] = collection["native_expiry_events"]
    result["semantics"] += " " + collection["semantics"]
    result["success"] = all(check["passed"] for check in result["checks"])
    return result


def evaluate_encounter_supplies(before: Path, after: Path, **parameters):
    return encounter_supply_checks(*load_pair(before, after), **parameters)
