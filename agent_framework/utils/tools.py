"""Shared public observation and tool bindings for Agent implementations."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar


InterfaceT = TypeVar("InterfaceT")
Observation = str | list[dict[str, object]]


@dataclass(frozen=True)
class Tool(Generic[InterfaceT]):
    """A schema and handler using only the restricted interface supplied to run."""

    name: str
    description: str
    parameters: dict[str, object]
    execute: Callable[[InterfaceT, dict[str, object]], Awaitable[str]]

    def schema(self) -> dict[str, object]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}
