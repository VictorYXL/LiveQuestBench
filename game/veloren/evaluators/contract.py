"""Identity-bound native Slay activation, combat and actual reward-delivery scoring."""

from pathlib import Path
import re

from game.veloren.evaluators.encounter import encounter_checks
from game.veloren.evaluators.endpoints import load_pair, validate_state


def validate_contract(*, min_reward: int = 1000, **state) -> None:
    if type(min_reward) is not int or min_reward < 1:
        raise ValueError("min_reward must be a positive integer")
    validate_state(**state)


def contract_checks(initial: dict, final: dict, *, min_reward: int = 1000, **state) -> dict:
    validate_contract(min_reward=min_reward, **state)
    result = encounter_checks(initial, final, roles=["contract_target"], **state)
    first, last = (row["private_contract_evidence"] for row in (initial, final))
    registry = first["registry"]
    combat_registry = initial["private_encounter_evidence"]["registry"]
    if (first["schema"] != "livequest-native-contract/1" or last["schema"] != first["schema"]
            or last["registry"] != registry or first["candidates"] or first["player_deaths"]
            or first["through_sequence"] != registry["opening_sequence"]
            or registry["opening_sequence"] != combat_registry["opening_sequence"]
            or registry["nonce"] != combat_registry["nonce"] or registry["run_id"] != combat_registry["run_id"]
            or last["through_sequence"] != final["private_encounter_evidence"]["through_sequence"]
            or not re.fullmatch(r"[0-9a-f]{64}", registry["helper_sha256"])
            or registry["player"]["uid"] != initial["self_identity"]["uid"]
            or registry["player"]["server_entity"] != combat_registry["source"]["server_entity"]
            or registry["player"]["client_session_id"] != initial["session_id"]
            or registry["player"]["client_actor"] != initial["control_actor"]):
        raise ValueError("Native contract registry, helper provenance or capture boundary changed")

    def sequences(values, after):
        if (not isinstance(values, list) or len(values) != len(set(values))
                or any(type(value) is not int or not after < value <= last["through_sequence"] for value in values)):
            raise ValueError("Invalid native contract event sequence proof")
        return values

    deaths = sequences(last["player_deaths"], registry["opening_sequence"])
    candidates = last["candidates"]
    if not isinstance(candidates, list):
        raise ValueError("Native contract candidates must be a list")
    accepted = False
    killed_after_acceptance = False
    rewarded = False
    chains = []
    if len(candidates) == 1:
        candidate = candidates[0]
        activation = candidate["activation_sequence"]
        sequences([activation], registry["opening_sequence"])
        quest = candidate["quest"]
        kind = quest["quest"]["kind"].get("Slay")
        accepted = (
            quest["quest_id"] not in registry["preexisting_quest_ids"] and quest["resolution"] is None
            and kind == {"target": registry["target_actor"], "slayer": registry["player"]["actor"]}
            and quest["quest"]["arbiter"] == registry["giver_actor"]
        )
        slay = candidate["slay"]
        killed = sequences(slay["death_sequences"], activation)
        damaged = sequences(slay["contribution_sequences"], activation)
        target_uid = combat_registry["targets"][0]["binding"]["uid"]
        initial_target = next(row["control_target"] for row in initial["nearby_entities"] if row["uid"] == target_uid)
        killed_after_acceptance = (
            slay["native_target_death"] is True and slay["player_contribution"] is True
            and bool(killed) and bool(damaged) and max(damaged) < min(killed)
            and initial_target in slay["client_uid_lifecycle_links"]
        )
        reward = candidate["reward"]
        chains = reward["chains"]
        if reward["resolution"] is True and reward["actual_reward_inserted"] is True and len(chains) == 1:
            chain = chains[0]
            settled, created = chain["settlement_sequence"], chain["creation_sequence"]
            sequences([settled, created], activation)
            removed = sequences(chain["removal_sequences"], created)
            inserted = sequences(chain["insertion_sequences"], created)
            identity = lambda row: {key: value for key, value in row.items() if key != "res"}
            rewarded = (
                isinstance(chain["transaction_id"], str)
                and chain["transaction_id"].startswith(registry["nonce"] + ":")
                and chain["quest_id"] == quest["quest_id"]
                and identity(chain["native_quest_before"]) == identity(quest["quest"])
                and identity(chain["native_quest_at_settlement"]) == identity(quest["quest"])
                and bool(killed) and max(killed) < settled < created
                and bool(removed) and bool(inserted) and min(removed) < min(inserted)
                and chain["item"] == {"Simple": "common.items.utility.coins"}
                and type(chain["amount"]) is int and chain["amount"] >= min_reward
            )
    checks = result["checks"] + [
        {"kind": "native_slay_acceptance", "matching_quests": len(candidates), "passed": accepted},
        {"kind": "native_post_acceptance_kill", "passed": killed_after_acceptance},
        {"kind": "native_contract_reward", "minimum_coins": min_reward, "passed": rewarded},
        {"kind": "contract_player_never_died", "passed": not deaths},
    ]
    return {
        "success": all(row["passed"] for row in checks), "checks": checks, "reward_chains": chains,
        "semantics": result["semantics"] + " A new native Slay quest must bind this player, giver and target. "
                     "Combat must follow activation. The pinned server-private contract helper joins exact "
                     "settlement, reward statement, sender removal and player insertion, including actor, "
                     "UID, server-generation, item and transaction identities. Neither inventory delta, "
                     "quest disappearance nor a tool receipt alone proves delivery. Physical VM acceptance "
                     "is admitted through native quest creation without requiring ST action receipts.",
    }


def evaluate_contract(before: Path, after: Path, *, min_reward: int = 1000, **state) -> dict:
    return contract_checks(*load_pair(before, after), min_reward=min_reward, **state)
