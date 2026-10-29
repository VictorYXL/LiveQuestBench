from copy import deepcopy

import pytest

from game.veloren.evaluators.active_build import paid_skill_check, validate_active_build


def test_paid_skill_counts_earned_progress_but_not_unspent_grants():
    first = {"skill_tree": {"groups": [{
        "group": {"Weapon": "Sword"}, "earned_points": 2, "available_points": 2,
        "skills": [{"skill": {"Sword": "DefensiveRiposte"}, "learned_level": None, "next_cost": 1}],
    }]}}
    last = deepcopy(first)
    group = last["skill_tree"]["groups"][0]
    group.update(earned_points=3, available_points=1)
    group["skills"][0]["learned_level"] = 1
    assert paid_skill_check(first, last, "DefensiveRiposte")["passed"]
    group["available_points"] = 3
    assert not paid_skill_check(first, last, "DefensiveRiposte")["passed"]


def test_build_rejects_unrelated_ability_damage_requirement():
    with pytest.raises(ValueError, match="configured Sword auxiliary"):
        validate_active_build(
            paid_skill="DefensiveRiposte", roles=["legoom"],
            sword_skills=["DefensiveRiposte"],
            auxiliary_ability={"slot": 0, "mainhand_index": 10},
            required_attack={"source": "Melee", "tool": "Sword", "lethal": False,
                             "ability": {"ability": {"MainWeaponAux": 2}, "context_index": None}},
        )
