"""Original native cart identities and physical delivery, never collection alone."""
from pathlib import Path

from scripts.prove_timed_routing import score
from scripts.prove_two_cart import entities


def verify_initial(world: Path):
    rows = entities(world)
    for name in ("east", "west"):
        original = [row for row in rows if f"original_cart_{name}" in row.get("Tags", [])]
        if len(original) != 1:
            raise ValueError("Expected exactly one original cart per consignment")
        if not any(str(item.get("tag", {}).get("livequest_cargo", "")) == name + "_consignment"
                   for item in original[0].get("Items", [])):
            raise ValueError("Original cart lacks its native consignment")


def evaluate_routing(before, after, player):
    verify_initial(before)
    result = score(before, after, player)
    return {"success": bool(result["native_objective_success"]), "checks": result}
