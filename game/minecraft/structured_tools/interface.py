"""Fixed Minecraft ST profile over ordinary native-client player operations."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from itertools import groupby
import json
import logging
import math
import time

from game.minecraft.runtime.bridge import BridgeError, NativeBridge
from agent_framework.utils.tools import Tool


PROFILE_ID = "minecraft-1.20.4-st-native"
logger = logging.getLogger(__name__)
NUMBER = {"type": "number", "minimum": -30000000, "maximum": 30000000}
POSITION = {"x": NUMBER, "y": {"type": "number", "minimum": -2048, "maximum": 2048}, "z": NUMBER}
ITEM = {"type": "string", "minLength": 1}
SLOT = {"type": "integer", "minimum": 1, "maximum": 9}
COUNT = {"type": "integer", "minimum": 1, "maximum": 64}
STATION = {"type": "string", "enum": ["inventory", "crafting_table"]}


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False,
    }}


SCHEMAS = [
    tool("GetObservationTool", "Read local state: radius-15 block cube without line-of-sight filtering, inventory and nearby entities.", {}, []),
    tool("MoveTool", "Move in a relative direction for a bounded duration; releases movement afterward.", {
        "direction": {"type": "string", "enum": ["forward", "backward", "left", "right"]},
        "duration": {"type": "number", "minimum": 0, "maximum": 10},
    }, ["direction", "duration"]),
    tool("LookAtPositionTool", "Turn toward a world point.", POSITION, ["x", "y", "z"]),
    tool("SelectTool", "Select hotbar slot 1-9.", {"slot": SLOT}, ["slot"]),
    tool("StopTool", "Release controls. Does not roll back effects.", {}, []),
    tool("RespawnTool", "When dead, request one ordinary native respawn and wait up to 10 seconds for "
         "alive confirmation. Refused while alive. Native spawn, item loss and world rules apply; "
         "does not reset the episode, enemies or clock.", {}, []),
    tool("JumpTool", "Perform a short jump pulse.", {"duration": {"type": "number", "minimum": 0, "maximum": 10}}, []),
    tool("GoToPositionTool", "Walk to the center of a loaded standable target block within 64 blocks, using bounded grid search (4096 expansions), steps/jumps of one block; no digging, building or parkour.", POSITION, ["x", "y", "z"]),
    tool("DigTool", "Aim at and dig one reachable block. Does not navigate, select equipment or guarantee pickup.", POSITION, ["x", "y", "z"]),
    tool("PlaceTool", "Place the held block against a reachable support block face.", {
        **POSITION, "face": {"type": "string", "enum": ["top", "bottom", "north", "south", "east", "west"]},
    }, ["x", "y", "z", "face"]),
    tool("QueryCraftRecipeTool", "List native recipes and material availability for an output.", {
        "output_item": ITEM, "station": STATION,
    }, ["output_item"]),
    tool("CraftItemTool", "Execute a recipe count (not target inventory count). Table crafts require aiming at an existing table; no automatic station setup.", {
        "output_item": ITEM, "station": STATION, "count": COUNT,
        "recipe_index": {"type": "integer", "minimum": 0},
    }, ["output_item"]),
    tool("SmeltItemTool", "Smelt using an aimed-at empty furnace, carried input and supported fuel. Partial contents remain on cancellation; no automatic station setup.", {
        "output_item": ITEM, "count": COUNT, "recipe_index": {"type": "integer", "minimum": 0},
    }, ["output_item"]),
]
BASE_TOOLS = tuple(schema["name"] for schema in SCHEMAS if schema["name"] != "GetObservationTool")
SCHEMAS.extend([
    tool("InspectContainerTool", "Open the reachable chest under your aim and read its native slots. "
         "No navigation, remote contents, automatic pickup or task-item selection.", {}, []),
    tool("TakeContainerItemTool", "Shift-click one observed chest slot into your inventory. "
         "Requires the chest screen opened by InspectContainerTool; may transfer only part if inventory is full.",
         {"slot": {"type": "integer", "minimum": 0, "maximum": 53}}, ["slot"]),
    tool("StrikeTool", "Aim once at a supplied world point and submit one ordinary melee attack. "
         "Native reach and occlusion apply; no enemy tracking, movement, repetition or cooldown wait.",
         POSITION, ["x", "y", "z"]),
    tool("AttackTool", "Submit one ordinary attack at the current crosshair, then release. "
         "No auto-aim, movement, cooldown wait or kill guarantee.", {}, []),
    tool("UseHeldItemTool", "Hold ordinary use on the selected item, then release. "
         "Native food, shield or bow rules apply; does not select items or choose when to heal.", {
             "duration": {"type": "number", "minimum": 0.05, "maximum": 5},
         }, ["duration"]),
])


EXPEDITION_TOOLS = tuple(schema["name"] for schema in SCHEMAS if schema["name"] != "GetObservationTool")
SCHEMAS.extend([
    tool("InspectMerchantTool", "Open the living merchant under your aim within three blocks, or refresh "
         "the already open native merchant screen. Return current offers, payment slots, cursor and session-bound quotes; "
         "no navigation, remote stock lookup or exchange.", {}, []),
    tool("TradeTool", "Select an observed offer and commit exactly one native exchange. "
         "Requires its current quote and an empty hotbar destination slot 1-9. "
         "Native UI fills payment slots; no price negotiation, repeated buying, movement or auto-equipping. "
         "Stale quotes are refused; partial effects remain if interrupted.", {
             "offer_index": {"type": "integer", "minimum": 0},
             "quote": ITEM, "slot": SLOT,
         }, ["offer_index", "quote", "slot"]),
])
TRADING_TOOLS = tuple(schema["name"] for schema in SCHEMAS if schema["name"] != "GetObservationTool")
SCHEMAS.extend([
    tool("InspectVitalsTool", "Read only your native air supply and active effects: air ticks, maximum air, "
         "whether your eyes are underwater, and effect IDs, amplifiers and remaining native ticks. "
         "Ordinary native time continues; no breathing refill, potion use, movement or safe-route advice.", {}, []),
    tool("InspectFurnaceTool", "Open the reachable furnace under your aim, or read the already open furnace. "
         "Read native window slots (0=input, 1=fuel, 2=output, 3-38=player inventory), cursor and UI progress. "
         "No material choice, insertion, waiting for cooking or collection.", {}, []),
    tool("FurnaceClickTool", "Submit one ordinary click in the open furnace window and return native UI readback. "
         "Pickup uses left/right clicks for full stacks or individual items; quick_move is shift-click. "
         "No automatic input/fuel choice or transfer guarantee. Partial effects and cursor contents persist.", {
             "slot": {"type": "integer", "minimum": 0, "maximum": 38},
             "button": {"type": "string", "enum": ["left", "right"]},
             "operation": {"type": "string", "enum": ["pickup", "quick_move"]},
         }, ["slot", "button", "operation"]),
])


@dataclass(frozen=True)
class StructuredInterface:
    observe: Callable[[], Awaitable[dict]]
    call_tool: Callable[[str, dict], Awaitable[dict]]
    tool_schemas: Callable[[], list[dict]]


async def agent_observation(interface: StructuredInterface) -> str:
    state = await interface.observe()
    cube = dict(state["nearby_blocks"])
    data = cube.pop("data")
    if not isinstance(data, list) or any(type(value) is not int for value in data):
        raise ValueError("Expected palette-index block data")
    cube["format"] = "palette_cube_rle"
    cube["data_rle"] = [[value, sum(1 for _ in run)] for value, run in groupby(data)]
    cube["axis_order"] = "x_fastest_then_y_then_z"
    return json.dumps({**state, "nearby_blocks": cube}, separators=(",", ":"))


def agent_tools() -> list[Tool[StructuredInterface]]:
    result: list[Tool[StructuredInterface]] = []
    for schema in tool_schemas():
        name = schema["name"]
        if name == "GetObservationTool":
            continue

        async def execute(
            interface: StructuredInterface, arguments: dict[str, object], tool_name: str = name,
        ) -> str:
            try:
                validate_tool(tool_name, arguments)
            except ValueError as error:
                logger.warning("ST tool %s rejected before execution: %s", tool_name, error)
                return json.dumps({
                    "success": False, "error": "invalid_tool_arguments",
                    "message": str(error), "executed": False,
                })
            return json.dumps(await interface.call_tool(tool_name, arguments), separators=(",", ":"))

        result.append(Tool(name, schema["description"], schema["parameters"], execute))
    return result


def tool_schemas() -> list[dict]:
    return deepcopy(SCHEMAS)


def validate_tool(name: str, arguments: dict) -> None:
    schema = next((item["parameters"] for item in SCHEMAS if item["name"] == name), None)
    if schema is None:
        raise ValueError(f"Unknown ST tool: {name}")
    if not isinstance(arguments, dict) or set(arguments) - schema["properties"].keys() or set(schema["required"]) - arguments.keys():
        raise ValueError(f"Invalid arguments for {name}")
    for key, value in arguments.items():
        field = schema["properties"][key]
        kind = field["type"]
        if kind in ("number", "integer"):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
            if kind == "integer" and type(value) is not int:
                raise ValueError(f"{key} must be an integer")
            if value < field.get("minimum", -math.inf) or value > field.get("maximum", math.inf):
                raise ValueError(f"{key} is out of range")
        elif not isinstance(value, str) or len(value) < field.get("minLength", 0):
            raise ValueError(f"{key} must be a valid string")
        if "enum" in field and value not in field["enum"]:
            raise ValueError(f"Unsupported {key}: {value}")


async def observe(bridge: NativeBridge) -> dict:
    started = time.monotonic_ns()
    data = await bridge.request("observe", {})
    fields = ("agent_id", "position", "health", "hunger", "inventory", "wielded_item",
              "wield_index", "look_direction", "block_under", "aimed_node_coords",
              "nearby_entities", "nearby_blocks")
    if set(fields) - data.keys():
        raise BridgeError(f"Incomplete structured observation: missing {sorted(set(fields) - data.keys())}")
    return {"profile": PROFILE_ID, "capture_started_at_ns": started,
            "captured_at_ns": time.monotonic_ns(), **{key: data[key] for key in fields}}


async def execute_tool(bridge: NativeBridge, name: str, arguments: dict) -> dict:
    validate_tool(name, arguments)
    if name == "GetObservationTool":
        return await observe(bridge)
    if name == "QueryCraftRecipeTool":
        return await bridge.request("recipes", arguments)
    if name == "InspectVitalsTool":
        return check_action(await bridge.request("vitals", {}))
    action = {
        "MoveTool": "move_" + arguments.get("direction", ""),
        "LookAtPositionTool": "look", "SelectTool": "select", "StopTool": "stop", "RespawnTool": "respawn",
        "JumpTool": "jump", "GoToPositionTool": "go_to_position",
        "StrikeTool": "strike",
        "InspectContainerTool": "container_inspect", "TakeContainerItemTool": "container_take",
        "InspectMerchantTool": "merchant_inspect", "TradeTool": "merchant_trade",
        "DigTool": "dig_block", "PlaceTool": "place",
        "CraftItemTool": "craft", "SmeltItemTool": "smelt",
        "InspectFurnaceTool": "furnace_inspect", "FurnaceClickTool": "furnace_click",
        "AttackTool": "attack", "UseHeldItemTool": "use_held",
    }[name]
    params = {key: value for key, value in arguments.items() if key != "direction"}
    if name == "DigTool":
        aimed = await bridge.request("action", {"name": "aim_block", "loop": "closed_loop", "parameters": params})
        if aimed.get("success") is not True:
            return check_action(aimed)
    loop = "closed_loop" if name in ("GoToPositionTool", "DigTool", "PlaceTool") else "open_loop"
    result = await bridge.request("action", {"name": action, "loop": loop, "parameters": params}, timeout=60)
    return check_action(result)


def check_action(result: dict) -> dict:
    if type(result.get("success")) is not bool:
        raise BridgeError("Malformed ST action result")
    kind = result.get("payload", {}).get("failure_kind")
    if kind in ("timeout", "not_connected", "cancelled", "busy"):
        raise BridgeError(f"ST participant failure: {kind}; {result.get('message')}")
    return result
