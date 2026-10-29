"""Exact native Message acceptance, parties, successful resolution and payment."""

from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state


def validate_message(*, min_health: float = 1) -> None:
    validate_state(min_health=min_health)


def message_checks(initial: dict, final: dict, *, min_health: float = 1) -> dict:
    validate_message(min_health=min_health)
    first, last = (row["private_message_evidence"] for row in (initial, final))
    registry = first["registry"]
    if (registry != last["registry"] or registry["schema"] != "livequest-message-contract/1"
            or not registry["nonce"] or not registry["run_id"]
            or first["through_sequence"] != registry["opening_sequence"]
            or last["through_sequence"] < first["through_sequence"]
            or first["ordinary_acceptance_sequences"] or first["candidates"]
            or registry["player"]["uid"] != initial["self_identity"]["uid"]):
        raise ValueError("Invalid or preaccepted native Message opening")
    player, giver, recipient = (registry[key] for key in ("player", "giver", "recipient"))
    if len({party["uid"] for party in (player, giver, recipient)}) != 3:
        raise ValueError("Message requires distinct native source, recipient and messenger")
    accepted = last["ordinary_acceptance_sequences"]
    if any(type(seq) is not int or not registry["opening_sequence"] < seq <= last["through_sequence"]
           for seq in accepted):
        raise ValueError("Message acceptance is outside the measured boundary")
    candidates = last["candidates"]
    matching = []
    for candidate in candidates:
        quest = candidate["quest"]
        instance = quest["quest"]["kind"].get("Courier", {}).get("instance", {})
        if (quest["quest_id"] not in registry["preexisting_quest_ids"]
                and instance.get("kind") == "Message" and instance.get("messenger") == player["actor"]
                and instance.get("source_actor") == giver["actor"]
                and instance.get("target_actor") == recipient["actor"]
                and quest["quest"]["arbiter"] == recipient["actor"]
                and any(sequence < candidate["activation_sequence"] for sequence in accepted)):
            matching.append(candidate)
    unique = len(matching) == 1 and len(candidates) == 1
    reward = matching[0]["reward"] if unique else {}
    result = state_checks(initial, final, min_health=min_health)
    result["checks"].extend([
        {"kind": "ordinary_native_message_acceptance", "sequences": accepted, "passed": unique},
        {"kind": "native_message_resolution", "passed": reward.get("resolution") is True},
        {"kind": "actual_native_reward_inserted", "passed": reward.get("actual_reward_inserted") is True},
    ])
    result["success"] = all(check["passed"] for check in result["checks"])
    result["semantics"] += (
        " A unique new Courier/Message contract follows the exact ordinary acceptance response. "
        "Native source, recipient, messenger and recipient-arbiter must match. Native resolution "
        "and causally linked reward insertion are required; talking twice or receiving unrelated "
        "coins is insufficient. No continuous-survival or tactical-efficiency claim."
    )
    return result


def evaluate_message(before: Path, after: Path, **parameters) -> dict:
    return message_checks(*load_pair(before, after), **parameters)
