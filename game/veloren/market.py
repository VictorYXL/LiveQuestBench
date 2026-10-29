"""Finite native market preparation using existing residents and ordinary trades."""

import asyncio
import math
import re

from game.veloren.native_bindings import NativeBindingCursor
from game.veloren.settlement import native_command_text, quoted_stack

COINS = "common.items.utility.coins"


async def _locate_merchant(command, reader, identifier):
    async with asyncio.timeout(60):
        for attempt in range(120):
            if attempt % 30 == 0:
                await command("rtsim_tp", identifier)
            bindings = [row for row in reader.poll() if row.get("rtsim_uid") == int(identifier)]
            if len(bindings) > 1:
                raise RuntimeError("Selected native merchant has ambiguous loaded identities")
            if bindings and bindings[0].get("alive") is True:
                return bindings[0]["uid"]
            await asyncio.sleep(.2)
    raise RuntimeError("A selected native merchant did not load within bounded preparation")


def validate_market(fixture, occupied, standing):
    market = fixture["market"]
    if (not isinstance(market, dict) or set(market) != {"merchants", "bundles", "coin_reserve"}
            or "platform" not in fixture
            or any(key in fixture for key in ("merchant", "contract", "encounters", "companion"))
            or not isinstance(market["merchants"], list)
            or len(market["merchants"]) != 3):
        raise ValueError("A market requires three distinct ordinary merchants and no injected encounters")
    if type(market["coin_reserve"]) is not int or market["coin_reserve"] < 1:
        raise ValueError("Market coin reserve must be positive")
    names = set()
    stocked = set()
    for spec in market["merchants"]:
        if (not isinstance(spec, dict) or set(spec) != {"role", "position", "stock"}
                or not isinstance(spec["role"], str) or not spec["role"] or spec["role"] in names):
            raise ValueError("Market merchant roles must be unique")
        names.add(spec["role"])
        if (not isinstance(spec["position"], list) or len(spec["position"]) != 3
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in spec["position"])):
            raise ValueError("Market merchant position must contain native XYZ")
        standing(spec["position"], occupied, "Market merchant")
        if not isinstance(spec["stock"], dict) or not spec["stock"]:
            raise ValueError("Each market merchant needs finite declared stock")
        for item, amount in spec["stock"].items():
            if (not isinstance(item, str) or not re.fullmatch(r"common\.items\.[a-z0-9_.]+", item)
                    or type(amount) is not int or not 1 <= amount <= 20 or item in stocked):
                raise ValueError("Goal products must have one finite native market source")
            stocked.add(item)
    if not isinstance(market["bundles"], list) or len(market["bundles"]) != 2:
        raise ValueError("Market requires two accepted bundles")
    for bundle in market["bundles"]:
        if (not isinstance(bundle, dict) or len(bundle) < 2 or set(bundle) - stocked
                or any(type(n) is not int or n < 1 for n in bundle.values())):
            raise ValueError("Accepted market bundle is not supported by declared stock")
        if any(set(bundle) <= set(spec["stock"]) for spec in market["merchants"]):
            raise ValueError("No complete bundle may be stocked by just one merchant")
    if any(fixture["player_state"]["inventory"].get(item, 0) for item in stocked):
        raise ValueError("Market goals must not be supplied initially")


def bundle_costs(bundles, offers):
    return [sum(offers[item]["coin_price"] * amount for item, amount in bundle.items())
            for bundle in bundles]


async def initialize_market(admin, actor, fixture):
    from scripts.rpg_benchmark import setup

    market = fixture["market"]
    commands, transactions, residents, offers = [], [], [], {}
    oracle = admin.out / "private-native-oracle.ndjson"
    reader = NativeBindingCursor(oracle, admin.out.name)
    products = {item for spec in market["merchants"] for item in spec["stock"]}

    async def command(name, *arguments):
        return await native_command_text(admin, commands, name, *arguments)

    # Eligibility includes current native activity, so apply the declared setup time first.
    # The fixture still restores that same declared time at player admission.
    await command("time", fixture["time_of_day"])
    listing = await command("rtsim_npc", "merchant,sell wares", 3)
    identifiers = re.findall(r"\((\d+)\)", listing)
    if len(identifiers) != 3 or len(set(identifiers)) != 3:
        raise RuntimeError("Three distinct existing native merchants are unavailable")
    await setup.gift(admin, admin, COINS, 50000)
    for identifier, spec in zip(identifiers, market["merchants"]):
        uid = await _locate_merchant(command, reader, identifier)
        if uid in {r["uid"] for r in residents}:
            raise RuntimeError("Native merchant identities are not distinct")
        await command("sudo", f"uid@{uid}", "goto", *spec["position"])
        await setup.goto(admin, admin, [spec["position"][0] - 2, *spec["position"][1:]])
        placed = await setup.wait_observation(
            admin, lambda r: any(e["uid"] == uid for e in r["nearby_entities"]),
            "market merchant visible after initial relocation")
        target = next(e["control_target"] for e in placed["nearby_entities"] if e["uid"] == uid)

        async def invite():
            nonlocal target
            observed = await admin.request("observe")
            merchant = next((e for e in observed["nearby_entities"] if e["uid"] == target["uid"]), None)
            if merchant is None:
                raise RuntimeError("The initialized merchant left the bounded preparation area")
            target = merchant["control_target"]
            if merchant["distance"] > 3:
                # Native collision can displace the administrator from the merchant's exact center.
                await setup.goto(
                    admin, admin, merchant["position"], horizontal_tolerance=1.0)
            await setup.action(admin, "social_action", operation="invite_trade", target=target)
            row = await setup.wait_observation(
                admin, lambda r: r["social_and_trade"]["pending_trade"] is not None,
                "ordinary market preparation trade", timeout=30)
            trade = row["social_and_trade"]["pending_trade"]
            ours = trade["self_party_index"]
            if trade["parties"][1 - ours] != target["uid"]:
                raise RuntimeError("Market preparation has the wrong counterparty")
            return trade, ours

        async def act(trade, operation, **arguments):
            receipt = await setup.action(
                admin, "trade_action", operation=operation, trade_id=trade["trade_id"],
                counterparty_uid=target["uid"], phase=trade["phase"], **arguments)
            transactions.append({"merchant_uid": target["uid"], "operation": operation,
                                 "arguments": arguments, "receipt": receipt})

        async def close(trade):
            await act(trade, "decline")
            await setup.wait_observation(admin, lambda r: r["social_and_trade"]["pending_trade"] is None,
                                         "market preparation trade closed")

        async def commit(trade):
            await act(trade, "accept")
            row = await setup.wait_observation(
                admin, lambda r: (r["social_and_trade"]["pending_trade"] or {}).get("phase") == "Review",
                "native market trade review")
            await act(row["social_and_trade"]["pending_trade"], "accept")
            row = await setup.wait_observation(
                admin, lambda r: r["social_and_trade"]["pending_trade"] is None
                and (r.get("last_trade_result") or {}).get("committed") is True,
                "native market trade committed")
            transactions.append({"merchant_uid": target["uid"], "completed": row["last_trade_result"]})

        # Remove only competing goal products; unrelated native goods remain untouched.
        for _ in range(32):
            trade, ours = await invite()
            surplus = next((r for r in trade["inventories"][1 - ours]
                            if r["id"].get("Simple") in products
                            and r["id"]["Simple"] not in spec["stock"]), None)
            if surplus is None:
                await close(trade)
                break
            money = quoted_stack(trade["inventories"][ours], COINS)
            price = math.ceil(surplus["unit_site_value"] * surplus["amount"] / money["unit_site_value"])
            if price < 1 or price > money["amount"]:
                raise RuntimeError("Finite preparation funds cannot clear competing native products")
            await act(trade, "add_item", slot=surplus["slot"], quantity=surplus["amount"], ours=False)
            await act(trade, "add_item", slot=money["slot"], quantity=price, ours=True)
            await commit(trade)
        else:
            raise RuntimeError("Bounded removal of competing market products did not finish")

        for identifier_item, amount in spec["stock"].items():
            trade, ours = await invite()
            available = sum(r["amount"] for r in trade["inventories"][1 - ours]
                            if r["id"] == {"Simple": identifier_item})
            await close(trade)
            if available < amount:
                needed = amount - available
                await setup.gift(admin, admin, identifier_item, needed)
                trade, ours = await invite()
                product = quoted_stack(trade["inventories"][ours], identifier_item)
                money = quoted_stack(trade["inventories"][1 - ours], COINS)
                payment = math.floor(product["unit_site_value"] * needed / money["unit_site_value"])
                if payment < 1 or payment > money["amount"]:
                    raise RuntimeError("Native merchant cannot fund finite stock provisioning")
                await act(trade, "add_item", slot=product["slot"], quantity=needed, ours=True)
                await act(trade, "add_item", slot=money["slot"], quantity=payment, ours=False)
                await commit(trade)
        trade, ours = await invite()
        money = quoted_stack(trade["inventories"][ours], COINS)
        for identifier_item, amount in spec["stock"].items():
            product = quoted_stack(trade["inventories"][1 - ours], identifier_item)
            if product["amount"] < amount:
                raise RuntimeError("Prepared native market stock is insufficient")
            offers[identifier_item] = {
                "merchant_uid": target["uid"], "amount": product["amount"],
                "coin_price": product["unit_site_value"] / money["unit_site_value"],
            }
        residents.append({"role": spec["role"], "uid": target["uid"],
                          "rtsim_uid": int(identifier), "qualified_stock": trade})
        await close(trade)

    costs = bundle_costs(market["bundles"], offers)
    budget = fixture["player_state"]["inventory"].get(COINS, 0) - market["coin_reserve"]
    if any(not math.isfinite(c) or c <= 0 for c in costs) or min(costs) + 2 > budget:
        raise RuntimeError(f"No native-priced accepted bundle fits the finite coin budget: {costs}, {budget}")
    for resident, spec in zip(residents, market["merchants"]):
        await command("sudo", f"uid@{resident['uid']}", "goto", *spec["position"])
    await setup.goto(admin, actor, fixture["player_state"]["position"])
    row = await setup.wait_observation(
        actor, lambda r: all(any(e["uid"] == resident["uid"] for e in r["nearby_entities"])
                            for resident in residents),
        "all three ordinary market residents visible before readiness")
    for resident in residents:
        matches = [e for e in row["nearby_entities"] if e["uid"] == resident["uid"]]
        if len(matches) != 1 or matches[0]["health"]["dead"]:
            raise RuntimeError("Prepared market participant is missing or dead")
        resident["player_target"] = matches[0]["control_target"]
    return {"merchants": residents, "offers": offers, "bundle_coin_costs": costs,
            "commands": commands, "transactions": transactions,
            "scope": "Existing unprotected native residents; initial ordinary trades and placement only. "
                     "Prices, AI and native restocking rules are unchanged."}
