"""Original native supply collection, including conservative mixed-stack lineage."""

from pathlib import Path

from game.veloren.evaluators.endpoints import finite, load_pair, state_checks, validate_state


PICKUP_EVENTS = frozenset({
    "item_drop_created", "item_pickup_applied", "item_drop_expired",
    "item_drop_merged", "item_drop_merged_on_creation",
})


def _quantity(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative native quantity")
    return value


def _asset(value):
    return value.get("Simple") if isinstance(value, dict) and set(value) == {"Simple"} else None


def pickup_snapshot(rows, supplies, actor, clock, registry=None):
    events = [row for row in rows if row["event"] in PICKUP_EVENTS]
    identity = {"uid": actor["uid"], "server_entity": actor["server_entity"]}
    if registry is None:
        sources = []
        for supply in supplies:
            births = [row for row in events if row["event"] == "item_drop_created"
                      and row["data"]["source_uid"] == supply["uid"]]
            if len(births) != 1:
                raise ValueError("Original supply lacks unique native creation evidence")
            birth = births[0]
            data = birth["data"]
            if (_asset(data["item"]) != supply["item"] or data["amount"] != supply["amount"]
                    or finite(data["spawned_at"], "spawned_at")
                    + finite(data["lifetime_seconds"], "lifetime_seconds") - finite(clock, "clock") < 15):
                raise ValueError("Original native supply differs or lacks opening lifetime slack")
            for event in events:
                if event["sequence"] > birth["sequence"] and supply["uid"] in (
                    event["data"].get("source_uid"), event["data"].get("target_uid"),
                ):
                    raise ValueError("Original supply changed before public admission")
            sources.append({
                "uid": supply["uid"], "entity": data["source_entity"],
                "item": supply["item"], "amount": supply["amount"],
                "created_sequence": birth["sequence"], "spawned_at": data["spawned_at"],
                "lifetime_seconds": data["lifetime_seconds"],
            })
        if len({source["uid"] for source in sources}) != len(sources):
            raise ValueError("Original supply identities must be distinct")
        registry = {
            "run_id": rows[0]["data"]["run_id"], "nonce": rows[0]["data"]["nonce"],
            "opening_sequence": rows[-1]["sequence"], "actor": identity, "sources": sources,
        }
    if (registry["run_id"] != rows[0]["data"]["run_id"]
            or registry["nonce"] != rows[0]["data"]["nonce"] or registry["actor"] != identity):
        raise ValueError("Native pickup world or player identity changed")
    return {
        "schema": "livequest-source-pickups/1", "registry": registry,
        "through_sequence": rows[-1]["sequence"],
        "events": [row for row in events if row["sequence"] > registry["opening_sequence"]],
    }


def collection_checks(initial, final, collectors=None):
    first, last = (state["private_pickup_evidence"] for state in (initial, final))
    registry = first["registry"]
    if (first["schema"] != "livequest-source-pickups/1" or last["schema"] != first["schema"]
            or registry != last["registry"] or not registry["nonce"] or not registry["run_id"]
            or first["events"] or first["through_sequence"] != registry["opening_sequence"]
            or last["through_sequence"] < first["through_sequence"]):
        raise ValueError("Invalid native supply registry or boundary")
    actors = [registry["actor"]] if collectors is None else collectors
    owners = {(row["uid"], row["server_entity"]) for row in actors}
    sources = {row["uid"]: row for row in registry["sources"]}
    buckets = {
        uid: {"entity": row["entity"], "item": row["item"], "amount": row["amount"],
              "remaining_upper": {uid: row["amount"]}}
        for uid, row in sources.items()
    }
    retired, receipts, expiries = set(), [], []
    lost_upper = {uid: 0 for uid in sources}
    collected = {uid: 0 for uid in sources}
    previous = first["through_sequence"]
    items = {row["item"] for row in sources.values()}

    def bucket(uid, entity, item, amount):
        amount = _quantity(amount, "ground amount")
        if uid in retired:
            raise ValueError("Native supply event reuses a retired identity")
        if uid not in buckets:
            buckets[uid] = {"entity": entity, "item": item, "amount": amount, "remaining_upper": {}}
        value = buckets[uid]
        if (value["entity"], value["item"], value["amount"]) != (entity, item, amount):
            raise ValueError("Native supply generation, asset or quantity discontinuity")
        return value

    for event in last["events"]:
        if ((event["schema"], event["version"], event["private"]) != ("rpg-native-oracle", "1.1", True)
                or event["event"] not in PICKUP_EVENTS
                or not previous < event["sequence"] <= last["through_sequence"]):
            raise ValueError("Invalid native supply event chronology")
        previous = event["sequence"]
        data, kind = event["data"], event["event"]
        finite(data["server_time"], "native supply time")
        item = _asset(data["item"])
        if item not in items:
            if data.get("source_uid") in buckets or data.get("target_uid") in buckets:
                raise ValueError("Native supply asset changed")
            continue
        uid = data.get("source_uid")
        if kind == "item_drop_created":
            if uid in buckets or uid in retired:
                raise ValueError("Duplicate native ground identity")
            bucket(uid, data["source_entity"], item, data["amount"])
        elif kind == "item_drop_merged_on_creation":
            target = bucket(data["target_uid"], data["target_entity"], item, data["target_amount_before"])
            amount = _quantity(data["incoming_amount"], "incoming amount")
            if data["target_amount_after"] != target["amount"] + amount:
                raise ValueError("Native creation merge violates quantity conservation")
            target["amount"] += amount
        else:
            before = data["source_amount_before"] if kind == "item_pickup_applied" else (
                data["source_amount"] if kind == "item_drop_merged" else data["amount"])
            source = bucket(uid, data["source_entity"], item, before)
            if kind == "item_drop_merged":
                target_uid = data["target_uid"]
                if target_uid == uid:
                    raise ValueError("Native supply cannot merge into itself")
                target = bucket(target_uid, data["target_entity"], item, data["target_amount_before"])
                if data["target_amount_after"] != source["amount"] + target["amount"]:
                    raise ValueError("Native merge violates quantity conservation")
                target["amount"] += source["amount"]
                for original, upper in source["remaining_upper"].items():
                    target["remaining_upper"][original] = target["remaining_upper"].get(original, 0) + upper
                del buckets[uid]
                retired.add(uid)
            elif kind == "item_pickup_applied":
                amount = _quantity(data["amount"], "collected amount")
                after = _quantity(data["source_amount_after"], "remaining amount")
                if not amount or amount + after != source["amount"]:
                    raise ValueError("Native pickup violates quantity conservation")
                owned = (data["collector_uid"], data["collector_entity"]) in owners
                for original, upper in source["remaining_upper"].items():
                    if not owned:
                        lost_upper[original] += min(amount, upper)
                    source["remaining_upper"][original] = min(upper, after)
                source["amount"] = after
                receipts.append(event)
                if not after:
                    del buckets[uid]
                    retired.add(uid)
            elif kind == "item_drop_expired":
                if data["server_time"] <= data["spawned_at"] + data["lifetime_seconds"]:
                    raise ValueError("Native timeout precedes its declared lifetime")
                for original, upper in source["remaining_upper"].items():
                    lost_upper[original] += upper
                del buckets[uid]
                retired.add(uid)
                expiries.append(event)
        # A partial mixed pickup cannot identify individual units. Bound the total
        # original stock still outside the admitted players, rather than inventing FIFO.
        for original, source in sources.items():
            outside = lost_upper[original] + sum(
                value["remaining_upper"].get(original, 0) for value in buckets.values())
            collected[original] = max(collected[original], source["amount"] - outside)
    return {
        "checks": [{
            "kind": "original_supply_collection", "uid": uid, "item": row["item"],
            "required": row["amount"], "guaranteed_collected": collected[uid],
            "passed": collected[uid] >= row["amount"],
        } for uid, row in sources.items()],
        "native_pickup_events": receipts, "native_expiry_events": expiries,
        "semantics": "Successful native insertion and original ground-source lineage, not requests or "
                     "fungible endpoint possession. Mixed partial transfers are conservative; native "
                     "timeouts, not disappearance or a custom timer, retire uncollected ground stock.",
    }


def validate_supplies(*, supplies, **state):
    if (not isinstance(supplies, list) or not supplies
            or any(set(row) != {"item", "amount"} for row in supplies)
            or len({row["item"] for row in supplies}) != len(supplies)):
        raise ValueError("Supply goal requires distinct native item definitions and amounts")
    inventory = []
    for row in supplies:
        if _quantity(row["amount"], "required amount") == 0:
            raise ValueError("Required supply amount must be positive")
        inventory.append({"item": row["item"], "min_count": row["amount"]})
    validate_state(inventory=inventory, **state)


def team_collection_checks(initial, final, *, supplies):
    validate_supplies(supplies=supplies)
    if initial.keys() != final.keys():
        raise ValueError("Native supply team roster changed")
    owners = [role for role, state in initial.items() if "private_pickup_evidence" in state]
    if len(owners) != 1:
        raise ValueError("Native team supply requires one shared-world source registry")
    owner = owners[0]
    registry = initial[owner]["private_pickup_evidence"]["registry"]
    declared = [{"item": row["item"], "amount": row["amount"]} for row in registry["sources"]]
    if declared != supplies:
        raise ValueError("Team supply goal differs from native source registry")
    collectors = []
    for role, state in initial.items():
        actor = state["private_death_evidence"]["registry"]
        if (actor != final[role]["private_death_evidence"]["registry"]
                or actor["run_id"] != registry["run_id"] or actor["nonce"] != registry["nonce"]
                or actor["uid"] != state["self_identity"]["uid"]
                or actor["identity"] != state["self_identity"]
                or actor["identity"] != final[role]["self_identity"]):
            raise ValueError("Native supply collector is not an unchanged peer in the original world")
        collectors.append({"uid": actor["uid"], "server_entity": actor["server_entity"]})
    result = collection_checks(initial[owner], final[owner], collectors)
    result["success"] = all(check["passed"] for check in result["checks"])
    return result


def evaluate_supplies(before: Path, after: Path, *, supplies, **state):
    validate_supplies(supplies=supplies, **state)
    initial, final = load_pair(before, after)
    declared = [{"item": row["item"], "amount": row["amount"]}
                for row in initial["private_pickup_evidence"]["registry"]["sources"]]
    if declared != supplies:
        raise ValueError("Supply goal differs from native original source registry")
    result = state_checks(initial, final, inventory=[
        {"item": row["item"], "min_count": row["amount"]} for row in supplies], **state)
    causal = collection_checks(initial, final)
    result["checks"] += causal.pop("checks")
    result.update(causal)
    result["success"] = all(check["passed"] for check in result["checks"])
    return result
