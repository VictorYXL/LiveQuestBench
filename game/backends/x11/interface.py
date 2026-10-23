"""Public VM operations: pixels and bounded OS input, without game administration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from io import BytesIO
import json
import logging
import time

from game.backends.x11.actions import ActionError, ActionResult, BUTTONS, KEYS, WindowActions
from game.backends.x11.capture import CapturedFrame
from agent_framework.utils.tools import Observation, Tool


MAX_COMMANDS = 64
MAX_WAIT_MS = 10000
logger = logging.getLogger(__name__)
_COMMAND_FIELDS = {
    "key_down": ("key",), "key_up": ("key",),
    "mouse_down": ("button",), "mouse_up": ("button",),
    "mouse_move_relative": ("dx", "dy"), "mouse_move_to": ("x", "y"),
    "mouse_scroll": ("steps",), "wait": ("milliseconds",), "release_all": (),
}
_CHOICES = {"key": KEYS, "button": BUTTONS}
_RANGES = {
    "dx": (-32768, 32767), "dy": (-32768, 32767),
    "x": (0, 32767), "y": (0, 32767), "steps": (-20, 20),
    "milliseconds": (0, MAX_WAIT_MS),
}


@dataclass(frozen=True)
class MotorInterface:
    observe: Callable[[], Awaitable[CapturedFrame]]
    act: Callable[[list[dict[str, object]]], Awaitable[list[ActionResult]]]


async def agent_observation(interface: MotorInterface) -> Observation:
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


async def _agent_action(interface: MotorInterface, arguments: dict[str, object]) -> str:
    try:
        if set(arguments) != {"commands"} or not isinstance(arguments["commands"], list):
            raise ActionError("action requires a commands array")
        commands: list[dict[str, object]] = []
        for command in arguments["commands"]:
            if not isinstance(command, dict):
                raise ActionError("Each motor command must be an object")
            commands.append(command)
        validate_actions(commands)
    except ActionError as error:
        logger.warning("Motor batch rejected before execution: %s", error)
        return json.dumps({
            "success": False, "error": "invalid_action_arguments", "message": str(error),
            "executed_commands": 0,
            "held_controls": "unchanged; previously held controls may still be active",
        })
    return json.dumps([asdict(result) for result in await interface.act(commands)])


def agent_tools() -> list[Tool[MotorInterface]]:
    schema = action_tool_schema()
    name, description, parameters = schema["name"], schema["description"], schema["parameters"]
    assert isinstance(name, str) and isinstance(description, str) and isinstance(parameters, dict)
    return [Tool(name, description, parameters, _agent_action)]


def action_tool_schema() -> dict[str, object]:
    """Describe the same command vocabulary and limits used by validation."""
    parameters: dict[str, dict[str, object]] = {
        name: {"type": "string", "enum": list(values)}
        for name, values in _CHOICES.items()
    }
    parameters.update({
        name: {"type": "integer", "minimum": low, "maximum": high}
        for name, (low, high) in _RANGES.items()
    })
    variants = [{
        "type": "object", "properties": {
            "name": {"type": "string", "enum": [name]},
            "arguments": {
                "type": "object", "properties": {field: dict(parameters[field]) for field in fields},
                "required": list(fields), "additionalProperties": False,
            },
        }, "required": ["name", "arguments"], "additionalProperties": False,
    } for name, fields in _COMMAND_FIELDS.items()]
    return {
        "name": "action",
        "description": (
            "Execute bounded keyboard/mouse commands sequentially. "
            f"The sum of ALL wait milliseconds in this call must be <= {MAX_WAIT_MS}, "
            "not just each individual wait. This bounds explicit waits, not total key-hold time. "
            "Held controls persist across calls and model reasoning until explicitly released "
            "or stopped by the environment. Invalid arguments reject the entire batch before "
            "execution and return invalid_action_arguments with executed_commands=0; previously "
            "held controls are unchanged. Correct the arguments before submitting another call. "
            "Relative mouse movement is clipped to the window edges; applied_delta reports "
            "the submitted (dx, dy). Use mouse_move_to to reposition a free UI cursor."
        ),
        "parameters": {
            "type": "object", "properties": {
                "commands": {"type": "array", "minItems": 1, "maxItems": MAX_COMMANDS,
                             "items": {"anyOf": variants}},
            }, "required": ["commands"], "additionalProperties": False,
        },
    }


def validate_actions(commands: list[dict[str, object]]) -> list[tuple[str, dict[str, object]]]:
    if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_COMMANDS:
        raise ActionError(f"Provide between 1 and {MAX_COMMANDS} motor commands")
    result = []
    wait_total = 0
    for command in commands:
        if not isinstance(command, dict) or set(command) != {"name", "arguments"}:
            raise ActionError("Motor commands require name and arguments")
        name, arguments = command["name"], command["arguments"]
        if not isinstance(name, str) or name not in _COMMAND_FIELDS:
            raise ActionError("Unsupported motor command")
        if not isinstance(arguments, dict) or set(arguments) != set(_COMMAND_FIELDS[name]):
            raise ActionError(f"Invalid arguments for {name}")
        for key, value in arguments.items():
            if key in _CHOICES:
                if not isinstance(value, str) or value not in _CHOICES[key]:
                    raise ActionError(f"Unsupported {key}")
            else:
                if type(value) is not int:
                    raise ActionError(f"{key} must be an integer")
                low, high = _RANGES[key]
                if not low <= value <= high:
                    raise ActionError(f"{key} must be in [{low}, {high}]")
                if key == "milliseconds":
                    wait_total += value
        result.append((name, dict(arguments)))
    if wait_total > MAX_WAIT_MS:
        raise ActionError(
            f"Total wait is {wait_total} milliseconds; a motor batch may wait for at most "
            f"{MAX_WAIT_MS} milliseconds"
        )
    return result


async def execute_actions(
    session: WindowActions, commands: list[dict[str, object]], stopped: asyncio.Event,
) -> list[ActionResult]:
    results = []
    try:
        sequence = validate_actions(commands)
        for name, arguments in sequence:
            if stopped.is_set():
                raise ActionError("Game has ended; motor execution stopped")
            session.check_ready()
            if name == "wait":
                started = time.monotonic_ns()
                milliseconds = arguments["milliseconds"]
                assert isinstance(milliseconds, int)
                try:
                    await asyncio.wait_for(stopped.wait(), milliseconds / 1000)
                except TimeoutError:
                    pass
                if stopped.is_set():
                    raise ActionError("Game ended during wait")
                session.check_ready()
                results.append(ActionResult(name, started, time.monotonic_ns()))
            else:
                operation = getattr(session, name)
                results.append(operation(**arguments))
        return results
    except BaseException:
        session.release_all()
        raise
