"""Private preparation of an existing native merchant, without changing its AI or prices."""

import asyncio
import math
import re


def observed_merchant(observation: dict, uid: int) -> dict:
    matches = [row for row in observation["nearby_entities"] if row["uid"] == uid]
    if len(matches) != 1 or matches[0]["health"]["current"] <= 0 or matches[0]["health"]["dead"]:
        raise RuntimeError("Prepared native merchant is not alive and ordinarily observable")
    return matches[0]


def bind_merchant(observation: dict, prepared: dict) -> dict:
    merchant = observed_merchant(observation, prepared["uid"])
    return {**prepared, "player_target": merchant["control_target"]}


def verify_merchant(observation: dict, prepared: dict) -> None:
    merchant = observed_merchant(observation, prepared["uid"])
    if merchant["control_target"] != prepared["player_target"]:
        raise RuntimeError("Prepared merchant lifecycle changed in the player's client")


def quoted_stack(rows: list[dict], identifier: str) -> dict:
    matches = [row for row in rows if row["id"] == {"Simple": identifier}]
    if not matches:
        raise RuntimeError(f"Native trade has no quoted stack: {identifier}")
    return min(matches, key=lambda row: (-row["amount"], row["slot"]))


def purchase_funded(inventory: dict, spec: dict, *, product_value: float,
                    payment_value: float, coin_value: float) -> bool:
    coins = "common.items.utility.coins"
    opening_coins = inventory.get(coins, 0)
    if spec["payment_item"] == coins:
        budget = opening_coins * coin_value
        reserve = max(spec["payment_reserve"], spec["coin_reserve"])
    else:
        spendable = inventory[spec["payment_item"]] - spec["payment_reserve"]
        budget = spendable * payment_value + opening_coins * coin_value
        reserve = spec["coin_reserve"]
    return budget >= spec["stock_amount"] * product_value + reserve * coin_value


def nearby_merchants(observation: dict) -> list[dict]:
    return [row for row in observation["nearby_entities"]
            if isinstance(row.get("name_text"), str) and "(Merchant)" in row["name_text"]
            and row["health"]["current"] > 0 and not row["health"]["dead"]]


async def approach_merchant(admin, commands: list[dict]) -> tuple[dict, dict]:
    target = None
    try:
        async with asyncio.timeout(60):
            while True:
                observed = await admin.request("observe")
                if observed["current_site"]["loaded_chunk"] is True:
                    candidates = nearby_merchants(observed)
                    if target is None and candidates:
                        target = min(candidates, key=lambda row: row["distance"])["control_target"]
                    if target is not None:
                        npc = observed_merchant(observed, target["uid"])
                        if npc["control_target"] != target:
                            raise RuntimeError("Prepared merchant lifecycle changed during approach")
                        if npc["distance"] < 3:
                            return observed, target
                        # RT-sim merchants keep walking after the initial teleport.
                        await native_command_text(admin, commands, "goto", *npc["position"])
                await asyncio.sleep(.1)
    except TimeoutError as error:
        raise RuntimeError("native setup did not establish loaded merchant trade range within60s") from error


async def native_command_text(admin, commands: list[dict], name: str, *arguments) -> str:
    from scripts.rpg_benchmark import setup

    receipt = await setup.action(admin, "server_command", name=name, args=[str(arg) for arg in arguments])
    await asyncio.sleep(.2)
    events = await admin.request("events")
    commands.append({"name": name, "arguments": arguments, "receipt": receipt, "events": events})
    if any(row.get("data", {}).get("kind") == "command_error" for row in events):
        raise RuntimeError(f"Native resident preparation command failed: {name}")
    return "\n".join(row["data"]["content"]["Plain"] for row in events
                     if row.get("data", {}).get("kind") == "command_info"
                     and "Plain" in row["data"].get("content", {}))


async def final_quote_trade(admin, target: dict, transactions: list[dict]) -> tuple[dict, int]:
    from scripts.rpg_benchmark import setup

    def merchant(row):
        found = observed_merchant(row, target["uid"])
        if found["control_target"] != target:
            raise RuntimeError("Prepared merchant lifecycle changed before final quote")
        return found

    try:
        async with asyncio.timeout(30):
            for attempt in range(2):
                ready = await setup.wait_observation(
                    admin, lambda row: row["social_and_trade"]["pending_trade"] is None
                    and not row["social_and_trade"]["outgoing_invitee_uids"],
                    "merchant quote invitation ready", timeout=10,
                )
                found = merchant(ready)
                repositioned = found["distance"] >= 3
                if repositioned:
                    await setup.goto(admin, admin, found["position"], settle=False)
                    ready = await setup.wait_observation(
                        admin, lambda row: merchant(row)["distance"] < 3,
                        "same merchant quote range", timeout=10,
                    )
                previous = ready["last_trade_result"]
                actor = ready["control_actor"]
                receipt = await setup.action(
                    admin, "social_action", operation="invite_trade", target=target, basis=ready,
                )
                transactions.append({
                    "operation": "quote_invite", "attempt": attempt + 1, "target": target,
                    "repositioned_administrator": repositioned,
                    "action_id": receipt.get("action_id"),
                })

                def declined(row):
                    result = row["last_trade_result"]
                    return (result is not None and result != previous
                            and result["result"] == "Declined"
                            and target in result["parties"] and actor in result["parties"]
                            and result["trade"]["phase"] == "Mutate"
                            and result["trade"]["offers"] == [[], []])

                # A new empty trade can be declined between observe calls after a sale.
                row = await setup.wait_observation(
                    admin, lambda row: row["social_and_trade"]["pending_trade"] is not None
                    or declined(row), "native merchant trade", timeout=30,
                )
                trade = row["social_and_trade"]["pending_trade"]
                if trade is not None:
                    own = trade["self_party_index"]
                    if trade["parties"][1 - own] != target["uid"]:
                        raise RuntimeError("Native merchant trade has the wrong counterparty")
                    merchant(row)
                    return trade, own
                transactions.append({"operation": "quote_declined", "result": row["last_trade_result"]})
    except TimeoutError as error:
        raise RuntimeError("native setup did not establish native merchant trade within30s") from error
    raise RuntimeError("native setup did not establish native merchant trade after two invitations")


async def initialize_merchant(admin, actor, fixture: dict) -> dict:
    from scripts.rpg_benchmark import setup

    spec = fixture["merchant"]
    commands = []
    transactions = []

    async def command(name, *arguments):
        return await native_command_text(admin, commands, name, *arguments)

    listing = await command("rtsim_npc", "merchant", 1)
    identifiers = re.findall(r"\((\d+)\)", listing)
    if len(identifiers) != 1:
        raise RuntimeError("Native merchant lookup did not identify exactly one existing resident")
    await command("rtsim_info", identifiers[0])
    await command("rtsim_tp", identifiers[0])
    observed, target = await approach_merchant(admin, commands)
    if "native_site" in fixture and observed["current_site"]["location_name"] != fixture["native_site"]:
        raise RuntimeError("Nearest native merchant is not in the declared settlement")

    async def invite():
        await setup.action(admin, "social_action", operation="invite_trade", target=target)
        row = await setup.wait_observation(admin, lambda row: row["social_and_trade"]["pending_trade"] is not None,
                                           "native merchant trade", timeout=30)
        trade = row["social_and_trade"]["pending_trade"]
        own = trade["self_party_index"]
        if trade["parties"][1 - own] != target["uid"]:
            raise RuntimeError("Native merchant trade has the wrong counterparty")
        return trade, own

    async def trade_action(trade, operation, **arguments):
        result = await setup.action(
            admin, "trade_action", operation=operation, trade_id=trade["trade_id"],
            counterparty_uid=target["uid"], phase=trade["phase"], **arguments,
        )
        transactions.append({"operation": operation, "arguments": arguments, "receipt": result})

    async def decline(trade):
        await trade_action(trade, "decline")
        await setup.wait_observation(admin, lambda row: row["social_and_trade"]["pending_trade"] is None,
                                     "merchant preparation trade closed")

    def value(row):
        quote = row["unit_site_value"]
        if type(quote) not in (int, float) or not math.isfinite(quote) or quote <= 0:
            raise RuntimeError("Native merchant does not provide a positive finite item valuation")
        return quote

    trade, own = await invite()
    initial_stock = trade
    available = sum(row["amount"] for row in trade["inventories"][1 - own]
                    if row["id"] == {"Simple": spec["stock_item"]})
    await decline(trade)
    if available < spec["stock_amount"]:
        amount = spec["stock_amount"] - available
        await setup.gift(admin, admin, spec["stock_item"], amount)
        trade, own = await invite()
        product = quoted_stack(trade["inventories"][own], spec["stock_item"])
        coins = quoted_stack(trade["inventories"][1 - own], "common.items.utility.coins")
        payment = math.floor(value(product) * amount / value(coins))
        if not 1 <= payment <= coins["amount"]:
            raise RuntimeError("Native merchant cannot fund the ordinary stock-provisioning sale")
        await trade_action(trade, "add_item", slot=product["slot"], quantity=amount, ours=True)
        await trade_action(trade, "add_item", slot=coins["slot"], quantity=payment, ours=False)
        await trade_action(trade, "accept")
        reviewed = await setup.wait_observation(
            admin, lambda row: (row["social_and_trade"]["pending_trade"] or {}).get("phase") == "Review",
            "stock sale review",
        )
        await trade_action(reviewed["social_and_trade"]["pending_trade"], "accept")
        committed = await setup.wait_observation(
            admin, lambda row: row["last_trade_result"] is not None and row["last_trade_result"]["committed"]
            and row["social_and_trade"]["pending_trade"] is None, "native stock sale committed",
        )
        transactions.append({"committed": committed["last_trade_result"]})
    inventory = await admin.request("observe")
    if not any(row["item"]["id"] == {"Simple": spec["payment_item"]} for row in inventory["inventory"]["items"]):
        await setup.gift(admin, admin, spec["payment_item"], 1)
    trade, own = await final_quote_trade(admin, target, transactions)
    product = quoted_stack(trade["inventories"][1 - own], spec["stock_item"])
    coins = quoted_stack(trade["inventories"][1 - own], "common.items.utility.coins")
    payment = quoted_stack(trade["inventories"][own], spec["payment_item"])
    spendable = fixture["player_state"]["inventory"][spec["payment_item"]] - spec["payment_reserve"]
    if (product["amount"] < spec["stock_amount"] or coins["amount"] < spec["coin_reserve"]
            or not purchase_funded(fixture["player_state"]["inventory"], spec,
                                   product_value=value(product), payment_value=value(payment),
                                   coin_value=value(coins))
            or coins["amount"] * value(coins) < spendable * value(payment)):
        raise RuntimeError("Native stock, prices or liquidity do not support the declared purchase and reserves")
    qualified_stock = trade
    await decline(trade)
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    await command("sudo", f"uid@{target['uid']}", "goto", *spec["position"])
    placed = await setup.wait_observation(
        actor, lambda row: any(npc["uid"] == target["uid"]
                               and math.dist(npc["position"], spec["position"]) < 8
                               for npc in row["nearby_entities"]), "native merchant destination in the player's client",
    )
    prepared = {"uid": target["uid"], "administrator_target": target,
                "source_site_observed": observed["current_site"],
                "lookup_rtsim_uid": int(identifiers[0]), "initial_stock": initial_stock,
                "qualified_stock": qualified_stock, "commands": commands, "transactions": transactions,
                "scope": "Existing native resident; finite stock via ordinary trade when needed; "
                         "initial placement only; unchanged health, AI, native prices and gameplay rules."}
    prepared["placement_readback"] = observed_merchant(placed, prepared["uid"])
    return prepared
