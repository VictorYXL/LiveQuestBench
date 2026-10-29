"""Paid native skill acquisition plus causally matching configured ability damage."""

from pathlib import Path

from game.veloren.evaluators.encounter import encounter_checks, validate_encounter
from game.veloren.evaluators.endpoints import load_pair


def validate_active_build(*, paid_skill: str, **parameters) -> None:
    if paid_skill not in parameters.get("sword_skills", []):
        raise ValueError("Paid skill must be a required learned Sword skill")
    attack = parameters.get("required_attack") or {}
    auxiliary = parameters.get("auxiliary_ability") or {}
    expected = {"ability": {"MainWeaponAux": auxiliary.get("mainhand_index")}, "context_index": None}
    if (attack.get("tool") != "Sword" or attack.get("ability") != expected
            or "slot" not in auxiliary):
        raise ValueError("Required native attack must match the configured Sword auxiliary")
    validate_encounter(**parameters)


def paid_skill_check(initial: dict, final: dict, skill: str) -> dict:
    groups = []
    for boundary in (initial, final):
        matches = [group for group in boundary["skill_tree"]["groups"]
                   if group["group"] == {"Weapon": "Sword"}]
        if len(matches) != 1:
            raise ValueError("Paid skill lacks a unique native Sword group")
        group = matches[0]
        earned, available = group["earned_points"], group["available_points"]
        if (type(earned) is not int or type(available) is not int
                or not 0 <= available <= earned):
            raise ValueError("Invalid native earned/available Sword points")
        groups.append(group)
    first, last = groups
    rows = [[entry for entry in group["skills"] if entry["skill"] == {"Sword": skill}]
            for group in groups]
    if any(len(entries) != 1 for entries in rows):
        raise ValueError("Paid skill lacks unique native skill entries")
    before, after = rows[0][0], rows[1][0]
    cost = before["next_cost"]
    spent = (last["earned_points"] - last["available_points"]
             - first["earned_points"] + first["available_points"])
    if last["earned_points"] < first["earned_points"]:
        raise ValueError("Native earned Sword points regressed")
    return {"kind": "paid_native_unlock", "skill": skill, "native_initial_cost": cost,
            "spent_point_delta": spent, "passed": before["learned_level"] in (None, 0)
            and type(cost) is int and cost > 0
            and type(after["learned_level"]) is int and after["learned_level"] >= 1 and spent >= cost}


def active_build_checks(initial: dict, final: dict, *, paid_skill: str, **parameters) -> dict:
    validate_active_build(paid_skill=paid_skill, **parameters)
    result = encounter_checks(initial, final, **parameters)
    result["checks"].append(paid_skill_check(initial, final, paid_skill))
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " Required skill starts unlearned with a positive native cost and spent Sword points must "
        "increase; earned-point progression is accounted for. Original native attack/application "
        "joins bind actual damage to the final configured auxiliary, not merely an unlock and kill."
    )
    return result


def evaluate_active_build(before: Path, after: Path, **parameters) -> dict:
    return active_build_checks(*load_pair(before, after), **parameters)
