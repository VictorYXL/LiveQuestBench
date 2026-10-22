"""Hermes' native conversation Agent behind the shared lifecycle bridge."""

from pathlib import Path
import shutil
from typing import TypeVar

from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.utils.source import load_source


InterfaceT = TypeVar("InterfaceT")


class HermesAgent(ProcessAgent[InterfaceT]):
    name = "hermes_agent"
    directory = Path(__file__).parent
    source = load_source(directory)
    required_runtime = ".venv/bin/python"

    def _prepare_home(self, home: Path) -> None:
        shutil.copyfile(self.directory / "config.yaml", home / "config.yaml")

    def _worker_command(self) -> list[str]:
        return [str(self.root / self.required_runtime), str(self.directory / "worker.py"), str(self.root)]
