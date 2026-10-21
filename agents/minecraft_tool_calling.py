"""Minecraft bindings for the native baseline; no administrative game access."""

from dataclasses import asdict
from io import BytesIO
from itertools import groupby
import json

from agents.tool_calling_agent import Observation, Tool
from core.backends.x11.actions import BUTTONS, KEYS
from game.minecraft.structured_tools.interface import StructuredInterface, tool_schemas
from game.minecraft.visual_motor.interface import MotorInterface, validate_actions


MinecraftInterface = MotorInterface | StructuredInterface
GAME_INSTRUCTIONS = (
    "Minecraft is a first-person 3D survival game. Breaking blocks produces drops, "
    "which must be picked up by moving close. Inventory possession is different from "
    "breaking a block. Resources used for crafting are consumed. The server keeps "
    "running while you reason. Use only the provided controls and observations."
)
VM_INSTRUCTIONS = GAME_INSTRUCTIONS + (
    "\nYou receive only the actual game image and motor feedback. WASD moves, Space "
    "jumps, left_shift sneaks, left_ctrl sprints, E opens/closes inventory, 1-9 selects "
    "a hotbar slot, Q drops an item. Relative mouse motion changes view: positive dx "
    "turns right and positive dy looks down. Left mouse mines/attacks while held; "
    "right mouse uses/places. Aim the crosshair at blocks to mine them. Opening a menu "
    "does not pause this server. Held inputs persist during reasoning unless released. "
    "A wait is real elapsed time, not a world pause. A batch allows 1-64 commands and "
    "at most 10000 milliseconds of total explicit waits. Release inputs before finishing."
)
ST_INSTRUCTIONS = GAME_INSTRUCTIONS + (
    "\nYou receive the fixed native ST projection: position, health, inventory, nearby "
    "entities and a radius-15 block cube without line-of-sight filtering. Unloaded cells "
    "are unknown, not air. nearby_blocks.data_rle contains [palette_index, repeat_count] "
    "pairs encoding the complete flattened cube, x fastest, then y, then z, starting "
    "at minp. Expanding runs reconstructs every original cell. Inventory slots 1-9 are "
    "hotbar. GoToPositionTool takes a standable block coordinate. DigTool only aims at "
    "and breaks a reachable block; it does not navigate or guarantee pickup. A normal "
    "tool refusal is reported as success=false; use the result and next observation. "
    "Observations arrive automatically after each tool batch."
)


async def observe_minecraft(interface: MinecraftInterface) -> Observation:
    if isinstance(interface, MotorInterface):
        frame = await interface.observe()
        image = BytesIO()
        frame.image.save(image, format="PNG")
        return [
            {"type": "text", "text": json.dumps({
                "frame_id": frame.frame_id, "capture_started_at_ns": frame.capture_started_at_ns,
                "captured_at_ns": frame.captured_at_ns,
            })},
            {"type": "image", "data": image.getvalue(), "mime_type": "image/png"},
        ]
    state = await interface.observe()
    cube = dict(state["nearby_blocks"])
    data = cube.pop("data")
    if not isinstance(data, list) or any(type(value) is not int for value in data):
        raise ValueError("Expected palette-index block data")
    cube["format"] = "palette_cube_rle"
    cube["data_rle"] = [[value, sum(1 for _ in run)] for value, run in groupby(data)]
    cube["axis_order"] = "x_fastest_then_y_then_z"
    return json.dumps({**state, "nearby_blocks": cube}, separators=(",", ":"))


async def _motor_action(interface: MinecraftInterface, arguments: dict[str, object]) -> str:
    if not isinstance(interface, MotorInterface):
        raise TypeError("Motor tools require a MotorInterface")
    if set(arguments) != {"commands"} or not isinstance(arguments["commands"], list):
        raise ValueError("action requires a commands array")
    commands: list[dict[str, object]] = []
    for command in arguments["commands"]:
        if not isinstance(command, dict):
            raise ValueError("Each motor command must be an object")
        commands.append(command)
    validate_actions(commands)
    return json.dumps([asdict(result) for result in await interface.act(commands)])


def minecraft_tools(track: str) -> list[Tool[MinecraftInterface]]:
    if track == "structured_tool":
        result: list[Tool[MinecraftInterface]] = []
        for schema in tool_schemas():
            name = schema["name"]
            if name == "GetObservationTool":
                continue

            async def execute(
                interface: MinecraftInterface, arguments: dict[str, object], tool_name: str = name,
            ) -> str:
                if not isinstance(interface, StructuredInterface):
                    raise TypeError("ST tools require a StructuredInterface")
                return json.dumps(await interface.call_tool(tool_name, arguments), separators=(",", ":"))

            result.append(Tool(name, schema["description"], schema["parameters"], execute))
        return result
    if track != "visual_motor":
        raise ValueError("track must be visual_motor or structured_tool")
    key = {"type": "string", "enum": list(KEYS)}
    button = {"type": "string", "enum": list(BUTTONS)}
    delta = {"type": "integer", "minimum": -32768, "maximum": 32767}
    coordinate = {"type": "integer", "minimum": 0, "maximum": 32767}
    parameters: dict[str, dict[str, object]] = {
        "key_down": {"key": key}, "key_up": {"key": key},
        "mouse_down": {"button": button}, "mouse_up": {"button": button},
        "mouse_move_relative": {"dx": delta, "dy": delta},
        "mouse_move_to": {"x": coordinate, "y": coordinate},
        "mouse_scroll": {"steps": {"type": "integer", "minimum": -20, "maximum": 20}},
        "wait": {"milliseconds": {"type": "integer", "minimum": 0, "maximum": 10000}},
        "release_all": {},
    }
    variants = [{
        "type": "object", "properties": {
            "name": {"type": "string", "enum": [name]},
            "arguments": {"type": "object", "properties": properties,
                          "required": list(properties), "additionalProperties": False},
        }, "required": ["name", "arguments"], "additionalProperties": False,
    } for name, properties in parameters.items()]
    return [Tool(
        "action", "Execute bounded keyboard/mouse commands sequentially. Held controls persist.",
        {"type": "object", "properties": {
            "commands": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"anyOf": variants}},
        }, "required": ["commands"], "additionalProperties": False},
        _motor_action,
    )]
