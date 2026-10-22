"""GamingAgent's native perception-memory-reasoning harness and episode runner."""

from pathlib import Path
from typing import TypeVar

from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.utils.source import load_source


InterfaceT = TypeVar("InterfaceT")


class GamingAgent(ProcessAgent[InterfaceT]):
    name = "gamingagent"
    directory = Path(__file__).parent
    source = load_source(directory)
    required_runtime = ".venv/bin/python"
    native_observations = True

    def _worker_command(self) -> list[str]:
        return [str(self.root / self.required_runtime), str(self.directory / "worker.py"), str(self.root)]
