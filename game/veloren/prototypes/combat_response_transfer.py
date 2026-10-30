"""Separately versioned, noncanonical native response task and dispatch diagnostic."""

from pathlib import Path

from game.veloren.fixture import validate_fixture
from game.veloren.evaluators.encounter import validate_encounter
from game.veloren.prototypes.combat_family import build_instance as stock_instance
from game.veloren.prototypes.combat_response_assets import PUBLIC_PROPOSAL


def build_instance(world: Path, seed: int, track: str = "visual_motor", *, diagnostic: bool = False):
    task, private = stock_instance(world, seed, track)
    fixture = task["fixture"]
    fixture["experimental_combat_response"] = "committed-second-strike-v1"
    fixture["blocks"] = []
    centers = [
        ("near_west", 18709.5, 10838.5), ("near_east", 18725.5, 10838.5),
        ("far_west", 18715.5, 10870.5), ("far_east", 18719.5, 10870.5),
    ]
    if diagnostic:
        fixture["platform"]["size"] = [12, 44]
        fixture["player_state"]["position"] = [18705.5, 10803.5, 501]
        centers = [("response_target", 18705.5, 10838.5)]
    else:
        for x in (18709, 18725):
            fixture["blocks"].extend([
                {"origin": [x - 3, 10835, 501], "size": [1, 7, 4]},
                {"origin": [x + 3, 10835, 501], "size": [1, 7, 4]},
                {"origin": [x - 3, 10841, 501], "size": [7, 1, 4]},
            ])
    fixture["encounters"] = [
        {"role": role, "asset": "common.entity.benchmark.male_green_legoom", "position": [x, y, 501]}
        for role, x, y in centers
    ]
    parameters = {"roles": [row["role"] for row in fixture["encounters"]], "no_death": True, "min_health": 1}
    task["id"] = ("native_combat_response_dispatch_diagnostic_v1" if diagnostic
                  else "native_combat_response_transfer_prototype_v1")
    task["task"] = PUBLIC_PROPOSAL.replace(
        "NONCANONICAL PROPOSAL, NOT A RUNNABLE OR ACCEPTED TASK.",
        "NONCANONICAL EXPERIMENT: NOT AN ACCEPTED LEARNING TASK.",
    )
    if diagnostic:
        task["task"] = (
            "One-enemy native dispatch diagnostic, not the four-enemy learning condition. "
            "Only one original native Green Legoom is present. Original health, weapon, armour "
            "and player resources are unchanged. Damage and defeat this original enemy, never "
            "die and finish with at least one health within900seconds. This score is not the "
            "engineering probe's objective; the probe may stop without attacking or winning.\n\n"
            + task["task"].split("The VM proposal", 1)[0].replace(
                "The proposed episode uses four ordinary Male Green Legoom bodies",
                "This diagnostic uses one ordinary Male Green Legoom body",
            )
            + "\nUse ordinary movement and attacks. No required failure, damage, probe count or block. "
            "Existing ST provides body/position/health, not raw combat timings. "
            "The declared second-response parameters persist for the whole episode."
        )
    task["evaluator"]["parameters"] = parameters
    validate_fixture(fixture)
    validate_encounter(**parameters)
    private = {
        "schema": "noncanonical-native-response-task/1", "seed": seed,
        "diagnostic": diagnostic, "canonical": False, "qualified": False,
        "native_validation": "not_run", "realized_response_count": 2,
        "runtime_requirement": "Matching separately admitted experimental_combat_response_assets runtime",
        "selection_scope": "One actual response configuration for the whole episode; no private score label",
        "policy_access": "Authoring only; not controller input",
    }
    return task, private
