"""Opt-in preflight for a source-proven ignored native consumable input."""

SCHEMA = "combo-consumable-preflight-v1"


async def use_item(actor, action, arguments: dict) -> dict:
    basis = await actor.request("observe", origin="agent")
    item = next((row["item"] for row in basis["inventory"]["items"]
                 if row["slot"] == arguments.get("slot")), None)
    if (basis.get("character_state") == "ComboMelee2"
            and item is not None and item.get("consumable") is not None):
        return {
            "action_type": "use_item", "status": "refused",
            "detail": {
                "code": "consumable_input_ignored_during_combo",
                "source": "adapter_precondition",
                "admission_version": SCHEMA,
                "sent": False,
            },
        }
    return await action(actor, origin="agent", require_completed=False, basis=basis, **arguments)
