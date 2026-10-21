"""Orak's native zeroshot pipeline and runner with fixed public game tools."""

from pathlib import Path
from typing import TypeVar

from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.utils.source import load_source


InterfaceT = TypeVar("InterfaceT")


class OrakAgent(ProcessAgent[InterfaceT]):
    name = "orak"
    directory = Path(__file__).parent
    source = load_source(directory)
    required_runtime = ".venv/bin/python"

    def _worker_command(self) -> list[str]:
        return [str(self.root / self.required_runtime), str(self.directory / "worker.py"), str(self.root)]
