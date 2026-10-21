"""Public VM operations: pixels and bounded OS input, without game administration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import time

from core.backends.x11.actions import ActionError, ActionResult, BUTTONS, KEYS, WindowActions
from game.minecraft.visual_motor.capture import CapturedFrame


@dataclass(frozen=True)
class MotorInterface:
    observe: Callable[[], Awaitable[CapturedFrame]]
    act: Callable[[list[dict[str, object]]], Awaitable[list[ActionResult]]]


def validate_actions(commands: list[dict[str, object]]) -> list[tuple[str, dict[str, object]]]:
    if not isinstance(commands, list) or not 1 <= len(commands) <= 64:
        raise ActionError("Provide between 1 and 64 motor commands")
    fields = {
        "key_down": {"key"}, "key_up": {"key"}, "mouse_down": {"button"}, "mouse_up": {"button"},
        "mouse_move_relative": {"dx", "dy"}, "mouse_move_to": {"x", "y"},
        "mouse_scroll": {"steps"}, "wait": {"milliseconds"}, "release_all": set(),
    }
    result = []
    wait_total = 0
    for command in commands:
        if not isinstance(command, dict) or set(command) != {"name", "arguments"}:
            raise ActionError("Motor commands require name and arguments")
        name, arguments = command["name"], command["arguments"]
        if not isinstance(name, str) or name not in fields:
            raise ActionError("Unsupported motor command")
        if not isinstance(arguments, dict) or set(arguments) != fields[name]:
            raise ActionError(f"Invalid arguments for {name}")
        for key, value in arguments.items():
            if key in ("key", "button"):
                if not isinstance(value, str) or value not in (KEYS if key == "key" else BUTTONS):
                    raise ActionError(f"Unsupported {key}")
            else:
                if type(value) is not int:
                    raise ActionError(f"{key} must be an integer")
                low, high = {
                    "dx": (-32768, 32767), "dy": (-32768, 32767),
                    "x": (0, 32767), "y": (0, 32767), "steps": (-20, 20),
                    "milliseconds": (0, 10000),
                }[key]
                if not low <= value <= high:
                    raise ActionError(f"{key} must be in [{low}, {high}]")
                if key == "milliseconds":
                    wait_total += value
        result.append((name, dict(arguments)))
    if wait_total > 10000:
        raise ActionError("A motor batch may wait for at most 10000 milliseconds")
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
