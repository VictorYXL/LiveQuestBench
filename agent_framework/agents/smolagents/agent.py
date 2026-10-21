"""Hugging Face's native ToolCallingAgent, not its generated-code Agent."""

from pathlib import Path
from typing import TypeVar

from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.utils.source import load_source
from agent_framework.utils.tools import Tool


InterfaceT = TypeVar("InterfaceT")


class SmolagentsAgent(ProcessAgent[InterfaceT]):
    name = "smolagents"
    directory = Path(__file__).parent
    source = load_source(directory)
    required_runtime = ".venv/bin/python"

    def _additional_tools(self) -> list[Tool[InterfaceT]]:
        async def final_answer(interface: InterfaceT, arguments: dict[str, object]) -> str:
            if set(arguments) != {"answer"} or not isinstance(arguments["answer"], str):
                raise ValueError("final_answer requires a string answer")
            return arguments["answer"]

        return [Tool(
            "final_answer", "Provides a final answer to the given problem.",
            {"type": "object", "properties": {"answer": {
                "type": "string", "description": "The final answer to the problem",
            }}, "required": ["answer"], "additionalProperties": False},
            final_answer,
        )]

    def _worker_command(self) -> list[str]:
        return [str(self.root / self.required_runtime), str(self.directory / "worker.py"), str(self.root)]
