"""Versioned fixed native Veloren skills and explicitly projected public state."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import math

from agent_framework.utils.tools import Tool


PROFILE_ID = "veloren-native-fixed-tools-v2"
FIELDS = (
    "session_id", "tick", "position", "velocity", "on_ground", "survival", "inventory",
    "nearby_entities", "known_recipes", "nearby_interactable_sprites",
)
SPECS = {
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


@dataclass(frozen=True)
class StructuredInterface:
    observe: Callable[[], Awaitable[dict]]
    call_tool: Callable[[str, dict], Awaitable[dict]]


def project(observation: dict) -> dict:
    missing = set(FIELDS) - observation.keys()
    if missing:
        raise ValueError(f"Native observation lacks required fields: {sorted(missing)}")
    return {"profile": PROFILE_ID, "coordinate_frame": "native x/y horizontal, z up",
            **{name: observation[name] for name in FIELDS}}


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
        else:
            valid_type = type(value) is int if spec["type"] == "integer" else type(value) in (int, float)
            if not valid_type or not math.isfinite(value) or not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError(f"Invalid {field}")
    converted = dict(arguments)
    if native == "move":
        native = "move_" + converted.pop("direction")
    return native, converted


async def agent_observation(interface: StructuredInterface) -> str:
    return json.dumps(await interface.observe(), allow_nan=False)


def agent_tools() -> list[Tool[StructuredInterface]]:
    tools = []
    for name, (description, _, fields) in SPECS.items():
        async def execute(interface: StructuredInterface, arguments: dict[str, object], tool_name=name) -> str:
            validate_tool(tool_name, arguments)
            return json.dumps(await interface.call_tool(tool_name, arguments), allow_nan=False)
        tools.append(Tool(name, description, {
            "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False,
        }, execute))
    return tools
