"""Game-owned public controls and private scoring bindings for an Episode."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from agent_framework.utils.tools import Observation, Tool
from game.base_game import BaseGame


InterfaceT = TypeVar("InterfaceT")


@dataclass(frozen=True)
class Controls:
    observe: Callable[[], Awaitable[Observation]]
    execute: Callable[[str, dict[str, object]], Awaitable[str]]


def validate_tools(tools: Sequence[Tool[InterfaceT]], allowed: tuple[str, ...] | None) -> None:
    if allowed is not None:
        if not allowed or len(set(allowed)) != len(allowed):
            raise ValueError("Tool allowlists must be nonempty and unique")
        unknown = set(allowed) - {tool.name for tool in tools}
        if unknown:
            raise ValueError(f"Unknown tools: {sorted(unknown)}")


def bind_controls(
    interface: InterfaceT, observe: Callable[[InterfaceT], Awaitable[Observation]],
    tools: Sequence[Tool[InterfaceT]], allowed: tuple[str, ...] | None,
) -> tuple[Controls, list[Tool[Controls]]]:
    validate_tools(tools, allowed)
    selected = {tool.name: tool for tool in tools if allowed is None or tool.name in allowed}

    async def observation() -> Observation:
        return await observe(interface)

    async def execute(name: str, arguments: dict[str, object]) -> str:
        if name not in selected:
            raise ValueError(f"Tool not admitted for this task: {name}")
        return await selected[name].execute(interface, arguments)

    public = Controls(observation, execute)
    bound = []
    for tool in selected.values():
        async def call(controls: Controls, arguments: dict[str, object], name: str = tool.name) -> str:
            return await controls.execute(name, arguments)
        bound.append(Tool(tool.name, tool.description, tool.parameters, call))
    return public, bound


@dataclass(frozen=True)
class GameBinding:
    game: BaseGame[object]
    controls: Callable[[], tuple[Controls, list[Tool[Controls]]]]
    evaluate: Callable[[Path, Path], dict]
    verify_initial: Callable[[Path], None]
    metrics: Callable[[Path, Path], dict] | None = None
