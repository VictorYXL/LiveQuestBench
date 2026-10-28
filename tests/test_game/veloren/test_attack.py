"""Causal projectile attribution rejects endpoint and preceding-hit substitutes."""

from copy import deepcopy

import pytest

from game.veloren.evaluators.encounter import encounter_checks
from tests.test_game.veloren.test_encounter import evidence


def test_bow_lethal_requires_same_applied_native_attack_not_prior_arrow():
    initial, final = evidence()
    events = final["private_encounter_evidence"]["events"]
    effect = events[0]
    effect["sequence"] = 12
    effect["data"].update(cause={"Attack": "Projectile"}, instance=7, change_time=4.5)
    events[1]["sequence"] = 13
    events[1]["data"]["cause"] = {
        "amount": -25, "by": {"Solo": 1}, "cause": {"Attack": "Projectile"}, "instance": 7, "time": 4.5,
    }
    queued = {
        "schema": "rpg-native-oracle", "version": "1.1", "private": True,
        "event": "attack_health_effect_queued", "sequence": 11,
        "data": {"source_uid": 1, "source_entity": "player-generation-1",
                 "target_uid": 2, "target_entity": "enemy-generation-1",
                 "instance": 7, "requested_amount": -25, "server_time": 4.5,
                 "attack_source": "Projectile", "ability": {"tool": "Bow"}},
    }
    events.insert(0, queued)
    final["private_encounter_evidence"]["through_sequence"] = 13
    requirement = {"source": "Projectile", "tool": "Bow", "lethal": True}
    assert encounter_checks(initial, final, roles=["enemy"], required_attack=requirement)["success"]
    for where, key, value in (
        ("ability", "tool", "Staff"), ("effect", "after", 1),
        ("effect", "cause", {"Attack": "Melee"}),
    ):
        changed = deepcopy(final)
        pair = changed["private_encounter_evidence"]["events"]
        (pair[0]["data"]["ability"] if where == "ability" else pair[1]["data"])[key] = value
        assert not encounter_checks(initial, changed, roles=["enemy"], required_attack=requirement)["success"]
    queued["data"]["instance"] = 8
    with pytest.raises(ValueError, match="causal join"):
        encounter_checks(initial, final, roles=["enemy"], required_attack=requirement)
    queued["data"]["instance"] = 7
    events[-1]["data"]["cause"]["instance"] = 9
    assert not encounter_checks(initial, final, roles=["enemy"], required_attack=requirement)["success"]
    events[-1]["data"].pop("cause")
    with pytest.raises(ValueError, match="causal HealthChange"):
        encounter_checks(initial, final, roles=["enemy"], required_attack=requirement)
