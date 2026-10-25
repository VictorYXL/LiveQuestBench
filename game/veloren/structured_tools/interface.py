"""Versioned fixed native Veloren skills and explicitly projected public state."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import logging
import math

from agent_framework.utils.tools import Tool


PROFILE_ID = "veloren-native-fixed-tools-v2"
logger = logging.getLogger(__name__)
FIELDS = (
    "session_id", "tick", "position", "velocity", "on_ground", "survival", "inventory",
    "nearby_entities", "known_recipes", "nearby_interactable_sprites",
)
SPECS = {
    "RespawnTool": (
        "Request ordinary native respawn only when dead, and wait for observed revival. "
        "Uses the native waypoint or server spawn; no teleport to task start, equipment grant, "
        "enemy reset or new time budget. Existing no-death goals still fail after death.",
        "respawn", {},
    ),
    "MoveTool": ("Move in a camera-relative direction for bounded native client updates, not fixed seconds.",
                 "move", {"direction": {"type": "string", "enum": ["forward", "backward", "left", "right"]},
                          "duration_ticks": {"type": "integer", "minimum": 1, "maximum": 120}}),
    "TurnTool": ("Turn the native view horizontally by degrees.", "turn",
                 {"degrees": {"type": "number", "minimum": -180, "maximum": 180}}),
    "JumpTool": ("Request a native jump; terrain and stamina still constrain its effect.", "jump", {}),
    "PickupTool": ("Try to pick up the nearest in-range item. Does not navigate.", "pickup", {}),
    "UseItemTool": ("Use an item in an observed native inventory slot.", "use_item",
                    {"slot": {"type": "integer", "minimum": 0, "maximum": 4294967295}}),
    "CraftTool": ("Attempt a known native recipe; materials and station requirements still apply.", "craft",
                  {"recipe": {"type": "string", "minLength": 1, "maxLength": 128},
                   "amount": {"type": "integer", "minimum": 1, "maximum": 10}}),
    "EquipTool": ("Equip an observed inventory item into a native equipment slot.", "equip",
                  {"slot": {"type": "integer", "minimum": 0, "maximum": 4294967295},
                   "equip_slot": {"type": "string", "enum": ["chest"], "maxLength": 32}}),
}
BASE_TOOLS = tuple(SPECS)
SPECS.update({
    "LookTool": ("Aim once at an observed native XYZ point. Does not track a target or navigate.",
                 "look_at", {axis: {"type": "number", "minimum": -1000000, "maximum": 1000000}
                             for axis in ("x", "y", "z")}),
    "AttackTool": ("Hold primary or secondary attack for bounded client updates, then release. "
                   "Uses current aim: no target selection, auto-aim, approach, healing or combat loop.",
                   "attack", {"channel": {"type": "string", "enum": ["primary", "secondary"]},
                              "duration_ticks": {"type": "integer", "minimum": 1, "maximum": 60}}),
    "WieldTool": ("Draw or sheathe your equipped weapon; does not equip or obtain a weapon.",
                  "toggle_wield", {"wield": {"type": "boolean"}}),
    "BlockTool": ("Hold the native block input for bounded updates, then release; costs and weapon rules apply.",
                  "block", {"duration_ticks": {"type": "integer", "minimum": 1, "maximum": 60}}),
    "RollTool": ("Request a native dodge roll for bounded updates; energy and terrain constrain it.",
                 "roll", {"duration_ticks": {"type": "integer", "minimum": 1, "maximum": 30}}),
    "StopTool": ("Release native movement and ability inputs without undoing effects.", "stop", {}),
})
COMBAT_TOOLS = tuple(SPECS)
SPECS["StrikeTool"] = (
    "Aim once at a supplied XYZ point, then hold primary attack for bounded client updates. "
    "Requires a drawn weapon; no target lookup, tracking, movement, healing or combat loop.",
    "aimed_attack", {
        **{axis: {"type": "number", "minimum": -1000000, "maximum": 1000000} for axis in ("x", "y", "z")},
        "duration_ticks": {"type": "integer", "minimum": 1, "maximum": 60},
    },
)
EXPEDITION_TOOLS = tuple(SPECS)
SPECS["GlideTool"] = (
    "Draw or stow the equipped native glider. Drawing on the ground is not flight. "
    "No automatic takeoff, steering, landing or navigation; ordinary physics continue.",
    "glide", {"enabled": {"type": "boolean"}},
)
TARGET_FIELDS = {
    "uid": {"type": "integer", "minimum": 1, "maximum": 2**64 - 1},
    "lifecycle": {"type": "string", "minLength": 1, "maxLength": 128},
}
DIALOGUE_FIELDS = {
    "sender_uid": TARGET_FIELDS["uid"],
    "dialogue_id": {"type": "string", "minLength": 1, "maxLength": 20},
    "tag": {"type": "integer", "minimum": 0, "maximum": 2**32 - 1},
}
TRADE_FIELDS = {
    "trade_id": {"type": "integer", "minimum": 0, "maximum": 2**64 - 1},
    "counterparty_uid": TARGET_FIELDS["uid"],
    "phase": {"type": "string", "enum": ["Mutate", "Review", "Complete"]},
}
SPECS.update({
    "TalkTool": ("Ask a currently observed nearby resident to talk. No automatic response selection.",
                 "context_interact", TARGET_FIELDS),
    "InviteTradeTool": ("Invite a currently observed nearby NPC to trade. Does not negotiate or buy.",
                        "social_action", TARGET_FIELDS),
    "DialogueResponseTool": (
        "Choose one offered response from the current native question. Copy its decimal-string dialogue_id "
        "exactly; this submits a response, not confirmation of a quest or reward.",
        "dialogue_action", {**DIALOGUE_FIELDS,
                            "response_id": {"type": "integer", "minimum": 0, "maximum": 65535}},
    ),
    "DialogueAckTool": (
        "Acknowledge the current native statement so dialogue may advance. Copy its decimal-string dialogue_id.",
        "dialogue_action", DIALOGUE_FIELDS,
    ),
    "TradeOfferTool": (
        "Add or remove an exact quantity from an observed party's inventory slot in the current trade. "
        "ours selects your side. No automatic item choice, pricing, balancing or acceptance.",
        "trade_action", {**TRADE_FIELDS,
                         "operation": {"type": "string", "enum": ["add_item", "remove_item"]},
                         "slot": {"type": "integer", "minimum": 0, "maximum": 2**32 - 1},
                         "quantity": {"type": "integer", "minimum": 1, "maximum": 2**32 - 1},
                         "ours": {"type": "boolean"}},
    ),
    "TradeFinishTool": (
        "Accept the current native trade phase, or decline the trade. Acceptance can advance to Review "
        "without completing the exchange; inspect the server result and actual inventory afterwards.",
        "trade_action", {**TRADE_FIELDS,
                         "operation": {"type": "string", "enum": ["accept", "decline"]}},
    ),
    "UnlockSwordSkillTool": (
        "Learn one named native Sword skill using your points. Native costs and prerequisites apply; "
        "no point grants, automatic prerequisite purchases or refunds.",
        "unlock_skill", {"skill_name": {"type": "string", "minLength": 1, "maxLength": 64}},
    ),
    "ConfigureAbilityTool": (
        "Assign one currently eligible main-weapon auxiliary ability index to a zero-based hotbar slot. "
        "Does not unlock, draw or activate the ability.",
        "configure_auxiliary_ability", {
            "slot": {"type": "integer", "minimum": 0, "maximum": 4},
            "mainhand_index": {"type": "integer", "minimum": 0, "maximum": 127},
        },
    ),
    "AuxiliaryAttackTool": (
        "Hold one configured native auxiliary slot for bounded client updates, then release. "
        "Uses current aim and ordinary weapon/energy rules; no targeting, tracking or movement.",
        "attack_auxiliary", {
            "slot": {"type": "integer", "minimum": 0, "maximum": 4},
            "duration_ticks": {"type": "integer", "minimum": 1, "maximum": 60},
        },
    ),
    "PetStayTool": (
        "Ask one currently observed, nearby owned pet to stay or follow using the native pet command. "
        "Ordinary range and ownership rules apply. A submission is not state confirmation; "
        "inspect pet_staying. Does not teleport, heal, shield or choose a route.",
        "companion_action", {**TARGET_FIELDS, "stay": {"type": "boolean"}},
    ),
})


@dataclass(frozen=True)
class StructuredInterface:
    observe: Callable[[], Awaitable[dict]]
    call_tool: Callable[[str, dict], Awaitable[dict]]


def public_dialogue(row: dict | None) -> dict | None:
    if row is None:
        return None
    identifier = row["dialogue_id"]
    if type(identifier) is not int or not 0 <= identifier < 2**64:
        raise ValueError("Invalid native dialogue identifier")
    result = {key: row[key] for key in (
        "sender_uid", "sender", "received_client_tick", "kind", "tag", "text", "marker",
    ) if key in row}
    result["dialogue_id"] = str(identifier)
    if "responses" in row:
        result["responses"] = [{key: response[key] for key in ("response_id", "text")}
                               for response in row["responses"]]
    return result


def public_trade(row: dict | None) -> dict | None:
    if row is None:
        return None
    result = {key: row[key] for key in (
        "trade_id", "parties", "self_party_index", "phase", "offers", "accept_flags",
        "offer_site_values", "price_scope", "effect_scope",
    )}
    result["inventories"] = [
        None if items is None else [
            {key: item[key] for key in ("slot", "id", "amount", "kind", "unit_site_value")}
            for item in items
        ] for items in row["inventories"]
    ]
    return result


def project(observation: dict, *, rpg: bool = False, skills: bool = False) -> dict:
    missing = set(FIELDS) - observation.keys()
    if missing:
        raise ValueError(f"Native observation lacks required fields: {sorted(missing)}")
    result = {"profile": PROFILE_ID, "coordinate_frame": "native x/y horizontal, z up",
              **{name: observation[name] for name in FIELDS}}
    if skills:
        result.update(skill_tree=observation["skill_tree"], auxiliary_abilities=observation["auxiliary_abilities"])
    if rpg:
        result.update(
            profile="veloren-native-settlement-tools",
            dialogue=public_dialogue(observation["dialogue"]),
            dialogue_markers=[public_dialogue(row) for row in observation["dialogue_markers"]],
            pending_trade=public_trade(observation["social_and_trade"]["pending_trade"]),
            last_trade_result=observation["last_trade_result"],
        )
    return result


def validate_tool(name: str, arguments: dict) -> tuple[str, dict]:
    if name not in SPECS:
        raise ValueError(f"Unknown Veloren tool: {name}")
    _, native, fields = SPECS[name]
    if not isinstance(arguments, dict) or set(arguments) != set(fields):
        raise ValueError(f"{name} requires exactly {sorted(fields)}")
    for field, spec in fields.items():
        value = arguments[field]
        if spec["type"] == "string":
            if not isinstance(value, str) or not spec.get("minLength", 1) <= len(value) <= spec.get("maxLength", 128):
                raise ValueError(f"Invalid {field}")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError(f"Unsupported {field}")
        elif spec["type"] == "boolean":
            if type(value) is not bool:
                raise ValueError(f"Invalid {field}")
        else:
            valid_type = type(value) is int if spec["type"] == "integer" else type(value) in (int, float)
            if not valid_type or not math.isfinite(value) or not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError(f"Invalid {field}")
    converted = dict(arguments)
    if native == "move":
        native = "move_" + converted.pop("direction")
    elif native == "attack":
        native = "attack_" + converted.pop("channel")
    elif native == "look_at":
        converted = {"position": [converted[axis] for axis in ("x", "y", "z")]}
    elif name == "UnlockSwordSkillTool":
        converted = {"skill": {"Sword": converted["skill_name"]}}
    elif name == "ConfigureAbilityTool":
        converted = {"slot": converted["slot"], "ability": {"MainWeapon": converted["mainhand_index"]}}
    elif name == "PetStayTool":
        converted = {"operation": "pet_stay", "stay": converted.pop("stay"), "target": converted}
    elif name in ("TalkTool", "InviteTradeTool"):
        converted = {"operation": "talk" if name == "TalkTool" else "invite_trade",
                     "target": converted}
    elif name in ("DialogueResponseTool", "DialogueAckTool"):
        identifier = converted["dialogue_id"]
        if not identifier.isascii() or not identifier.isdecimal() or int(identifier) >= 2**64:
            raise ValueError("dialogue_id must be an unsigned 64-bit decimal string")
        converted["dialogue_id"] = int(identifier)
        converted["operation"] = "respond" if name == "DialogueResponseTool" else "ack"
    return native, converted


async def agent_observation(interface: StructuredInterface) -> str:
    return json.dumps(await interface.observe(), allow_nan=False)


def agent_tools() -> list[Tool[StructuredInterface]]:
    tools = []
    for name, (description, _, fields) in SPECS.items():
        async def execute(interface: StructuredInterface, arguments: dict[str, object], tool_name=name) -> str:
            try:
                validate_tool(tool_name, arguments)
            except ValueError as error:
                logger.warning("ST tool %s rejected before execution: %s", tool_name, error)
                return json.dumps({
                    "success": False, "error": "invalid_tool_arguments",
                    "message": str(error), "executed": False,
                })
            return json.dumps(await interface.call_tool(tool_name, arguments), allow_nan=False)
        tools.append(Tool(name, description, {
            "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False,
        }, execute))
    return tools
