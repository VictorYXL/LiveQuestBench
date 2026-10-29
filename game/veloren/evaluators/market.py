"""Accepted native inventory bundles and a new identity-bound completed market trade."""

from pathlib import Path

from game.veloren.evaluators.endpoints import load_pair, state_checks, validate_state
from game.veloren.market import COINS
from game.veloren.market_trades import trade_receipts


def validate_market(*, bundles, coin_reserve, position, min_health=1):
    if (not isinstance(bundles, list) or len(bundles) != 2
            or type(coin_reserve) is not int or coin_reserve < 1):
        raise ValueError("Market requires two accepted bundles and a positive coin reserve")
    for bundle in bundles:
        if not isinstance(bundle, dict) or len(bundle) < 2:
            raise ValueError("Each market bundle requires multiple products")
        validate_state(inventory=[{"item": item, "min_count": amount, "min_delta": amount}
                                  for item, amount in bundle.items()], position=position, min_health=min_health)


def market_checks(initial, final, *, bundles, coin_reserve, position, min_health=1):
    validate_market(bundles=bundles, coin_reserve=coin_reserve, position=position, min_health=min_health)
    first, last = (r["private_market_evidence"] for r in (initial, final))
    if ({key: value for key, value in first.items() if key != "trade_history"}
            != {key: value for key, value in last.items() if key != "trade_history"}
            or first["schema"] not in ("livequest-native-market/1", "livequest-native-market/2")
            or len(first["merchants"]) != 3
            or len({r["uid"] for r in first["merchants"]}) != 3
            or initial["last_trade_result"] is not None):
        raise ValueError("Native market identities changed or opening already has a completed trade")
    trades = (trade_receipts(initial, final) if first["schema"] == "livequest-native-market/2"
              else [final["last_trade_result"]])
    traded = False
    for trade in trades:
        parties = trade.get("parties", []) if isinstance(trade, dict) else []
        traded |= (
            isinstance(trade, dict) and trade.get("schema_version") == "1.0"
            and trade.get("source") == "server_finished_trade"
            and trade.get("committed") is True and trade.get("result") == "Completed"
            and len(parties) == 2 and initial["control_actor"] in parties
            and any(target in parties for target in first["merchants"])
        )
    result = state_checks(initial, final, inventory=[{"item": COINS, "min_count": coin_reserve}],
                          position=position, min_health=min_health)
    alternatives = [
        state_checks(initial, final, inventory=[
            {"item": item, "min_count": amount, "min_delta": amount}
            for item, amount in bundle.items()], min_health=min_health)
        for bundle in bundles
    ]
    result["checks"].extend([
        {"kind": "new_completed_market_trade", "passed": traded},
        {"kind": "accepted_market_bundle", "passed": any(r["success"] for r in alternatives)},
    ])
    result["success"] = all(r["passed"] for r in result["checks"])
    result["bundle_checks"] = alternatives
    result["semantics"] += (
        " At least one new native completed trade must bind this player and an initialized merchant. "
        "A qualifying bundle is held simultaneously with the reserve and return. "
        "Individual item provenance and plan revision are not inferred from terminal holdings."
    )
    return result


def evaluate_market(before: Path, after: Path, **parameters):
    return market_checks(*load_pair(before, after), **parameters)
