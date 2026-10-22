"""DeepSeek's native plugin-based Agent behind the shared lifecycle bridge."""

from pathlib import Path
import shutil
from typing import TypeVar

from agent_framework.agents.process_agent import IntegrationUnavailable, ProcessAgent
from agent_framework.utils.source import load_source


InterfaceT = TypeVar("InterfaceT")


class DeepSeekHarnessAgent(ProcessAgent[InterfaceT]):
    name = "deepseek_harness"
    directory = Path(__file__).parent
    source = load_source(directory)
    required_runtime = "packages/core/agent-loop/lib/index.js"

    def _worker_command(self) -> list[str]:
        node = shutil.which("node")
        if node is None:
            raise IntegrationUnavailable("Node.js is required for the DeepSeek native loop")
        return [node, str(self.directory / "worker.mjs"), str(self.root)]
