"""Minecraft VM uses the shared bounded X11 pixel/motor interface."""

from game.backends.x11.interface import (
    MotorInterface, action_tool_schema, agent_observation, agent_tools,
    execute_actions, validate_actions,
)

__all__ = [
    "MotorInterface", "action_tool_schema", "agent_observation", "agent_tools",
    "execute_actions", "validate_actions",
]
