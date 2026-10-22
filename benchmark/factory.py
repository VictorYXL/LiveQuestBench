"""Explicit game, Agent and model selection without dynamic configuration imports."""

from collections.abc import Callable, Sequence
import os
from pathlib import Path

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.agents.deepseek_harness import DeepSeekHarnessAgent
from agent_framework.agents.gamingagent import GamingAgent
from agent_framework.agents.hermes import HermesAgent
from agent_framework.agents.orak import OrakAgent
from agent_framework.agents.smolagents import SmolagentsAgent
from agent_framework.agents.tool_calling_agent import ToolCallingAgent
from agent_framework.llm_client.base_client import BaseLLMClient, Message, RequestEvent
from agent_framework.llm_client.github_copilot_client import GitHubCopilotClient
from agent_framework.llm_client.openai_client import OpenAIClient
from agent_framework.llm_client.vllm_client import VLLMClient
from agent_framework.utils.tools import Observation, Tool
from benchmark.config import ConfigError, ExperimentConfig, ModelConfig, TaskConfig
from game.bindings import Controls, GameBinding


NATIVE_AGENTS = {
    "deepseek": DeepSeekHarnessAgent, "hermes": HermesAgent, "orak": OrakAgent,
    "smolagents": SmolagentsAgent, "gamingagent": GamingAgent,
}


def make_game(task: TaskConfig, output: Path, *, headless: bool, recording: bool, recording_fps: int) -> GameBinding:
    if task.game == "minecraft":
        from game.minecraft.binding import create_binding
    elif task.game == "veloren":
        from game.veloren.binding import create_binding
    else:
        raise ConfigError(f"Unknown game: {task.game}")
    return create_binding(
        fixture=task.fixture, task_type=task.task_type, evaluator=task.evaluator,
        parameters=task.evaluator_parameters, tools=task.tools, output_dir=output,
        headless=headless, recording=recording, recording_fps=recording_fps,
    )


def validate_experiment(experiment: ExperimentConfig) -> None:
    if experiment.agent not in ("tool_calling", *NATIVE_AGENTS):
        raise ConfigError(f"Unknown Agent: {experiment.agent}")
    if experiment.agent in NATIVE_AGENTS and (
        experiment.model.provider == "vllm" or experiment.model.reasoning_effort is None
    ):
        raise ConfigError("Native process profiles currently require a Responses provider and explicit reasoning_effort")
    if experiment.agent in NATIVE_AGENTS:
        NATIVE_AGENTS[experiment.agent].source_root()
    for task in experiment.tasks:
        make_game(task, Path("unused-preflight"), headless=True, recording=False, recording_fps=10)


def make_client(model: ModelConfig, on_request: Callable[[RequestEvent], None]) -> BaseLLMClient:
    if model.provider == "github_copilot":
        token_file = os.environ.get("LIVEQUEST_COPILOT_TOKEN_FILE")
        return GitHubCopilotClient(
            model.name, token_file=Path(token_file) if token_file else None,
            max_output_tokens=model.max_output_tokens, reasoning_effort=model.reasoning_effort,
            timeout=model.timeout_seconds, max_attempts=model.max_attempts, on_request=on_request,
        )
    if model.provider == "openai":
        return OpenAIClient(
            model.name, max_output_tokens=model.max_output_tokens, reasoning_effort=model.reasoning_effort,
            timeout=model.timeout_seconds, max_attempts=model.max_attempts, on_request=on_request,
        )
    if model.provider != "vllm":
        raise ConfigError(f"Unknown provider: {model.provider}")
    return VLLMClient(
        model.name, base_url=model.base_url, max_output_tokens=model.max_output_tokens,
        temperature=model.temperature, enable_thinking=model.enable_thinking,
        timeout=model.timeout_seconds, max_attempts=model.max_attempts, on_request=on_request,
    )


async def observation(controls: Controls) -> Observation:
    return await controls.observe()


def make_agent(
    experiment: ExperimentConfig, client: BaseLLMClient, tools: Sequence[Tool[Controls]],
    output: Path, on_message: Callable[[Message], None],
) -> BaseAgent[Controls]:
    if experiment.agent == "tool_calling":
        return ToolCallingAgent(client, tools=tools, observe=observation, on_message=on_message)
    assert experiment.model.reasoning_effort is not None
    return NATIVE_AGENTS[experiment.agent](
        client, output_dir=output, tools=tools, observe=observation, on_message=on_message,
        model=experiment.model.name, reasoning_effort=experiment.model.reasoning_effort,
        max_output_tokens=experiment.model.max_output_tokens,
    )
