"""Explicit file-based experiment loading; no search paths or implicit overrides."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re

import yaml


class ConfigError(ValueError):
    """The requested evaluation plan is invalid or unsupported."""


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ConfigError("YAML keys must be unique strings; merge keys are not supported")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ConfigError(f"{label} must be a mapping with string keys")
    return dict(value)


def fields(data: dict[str, object], allowed: set[str], required: set[str], label: str) -> None:
    if data.keys() - allowed or required - data.keys():
        raise ConfigError(
            f"{label}: unknown fields {sorted(data.keys() - allowed)}, "
            f"missing fields {sorted(required - data.keys())}"
        )


def text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be nonempty text")
    return value


def identifier(value: object, label: str) -> str:
    value = text(value, label)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ConfigError(f"{label} must be a filesystem-safe identifier")
    return value


def positive(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{label} must be finite and positive")
    return float(value)


def integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{label} must be a positive integer")
    return value


def strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be a list")
    return tuple(text(item, label) for item in value)


def resolve(reference: str, declaring_file: Path) -> Path:
    path = Path(reference).expanduser()
    return (path if path.is_absolute() else declaring_file.parent / path).resolve()


@dataclass(frozen=True)
class Source:
    path: str
    sha256: str
    content: str


def read(path: Path) -> tuple[dict[str, object], Source]:
    path = path.resolve()
    raw = path.read_bytes()
    content = raw.decode("utf-8")
    try:
        data = mapping(yaml.load(content, Loader=UniqueLoader), str(path))
        json.dumps(data, allow_nan=False)
    except (yaml.YAMLError, TypeError, ValueError, RecursionError) as error:
        raise ConfigError(f"Invalid YAML configuration {path}: {error}") from error
    return data, Source(str(path), hashlib.sha256(raw).hexdigest(), content)


@dataclass(frozen=True)
class ParticipantConfig:
    id: str
    player_state: dict[str, object]


CAPABILITIES = frozenset({
    "spatial_interaction", "planning_resources", "realtime_execution",
    "information_adaptation", "peer_cooperation", "within_episode_learning",
})


@dataclass(frozen=True)
class CapabilityConfig:
    primary: tuple[str, ...]
    secondary: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskConfig:
    id: str
    game: str
    task_type: str
    task: str
    time_limit_seconds: float
    fixture: dict[str, object]
    evaluator: str
    evaluator_parameters: dict[str, object]
    tools: tuple[str, ...] | None
    source: Source
    participants: tuple[ParticipantConfig, ...] = ()
    capabilities: CapabilityConfig | None = None

    def resolved(self) -> dict:
        result = asdict(self)
        if not self.participants:
            result.pop("participants")
        if self.capabilities is None:
            result.pop("capabilities")
        return result


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str
    reasoning_effort: str | None = None
    max_output_tokens: int = 4096
    max_attempts: int = 3
    timeout_seconds: float = 120
    base_url: str = "http://127.0.0.1:8001/v1"
    temperature: float = 0
    enable_thinking: bool = False


@dataclass(frozen=True)
class AgentConfig:
    id: str
    name: str
    model: ModelConfig
    observation_history: int = 1

    def resolved(self) -> dict:
        result = asdict(self)
        if self.observation_history == 1:
            result.pop("observation_history")
        inactive = ("reasoning_effort",) if self.model.provider == "vllm" else (
            "base_url", "temperature", "enable_thinking",
        )
        for name in inactive:
            result["model"].pop(name)
        return result


@dataclass(frozen=True)
class ExperimentConfig:
    id: str
    game: str
    tasks: tuple[TaskConfig, ...]
    repetitions: int
    agents: tuple[AgentConfig, ...]
    source: Source

    def resolved(self) -> dict:
        result = asdict(self)
        result["agents"] = [agent.resolved() for agent in self.agents]
        result["tasks"] = [task.resolved() for task in self.tasks]
        return result


def load_task(path: Path) -> TaskConfig:
    data, source = read(path)
    required = {"id", "game", "task_type", "task", "time_limit_seconds", "fixture", "evaluator"}
    fields(data, required | {"tools", "participants", "capabilities"}, required, "task")
    capabilities = None
    if "capabilities" in data:
        row = mapping(data["capabilities"], "capabilities")
        fields(row, {"primary", "secondary"}, {"primary"}, "capabilities")
        primary = strings(row["primary"], "capabilities.primary")
        secondary = strings(row.get("secondary", []), "capabilities.secondary")
        selected = primary + secondary
        if not primary or len(set(selected)) != len(selected) or set(selected) - CAPABILITIES:
            raise ConfigError("Capabilities require nonempty primary and unique known dimensions across both lists")
        capabilities = CapabilityConfig(primary, secondary)
    mode = text(data["task_type"], "task_type")
    if mode not in ("visual_motor", "structured_tool"):
        raise ConfigError("task_type must be visual_motor or structured_tool")
    tools = strings(data["tools"], "tools") if "tools" in data else None
    if tools is not None and (mode != "structured_tool" or not tools or len(set(tools)) != len(tools)):
        raise ConfigError("tools must be a nonempty, unique ST allowlist, or omitted")
    fixture = mapping(data["fixture"], "fixture")
    game = text(data["game"], "game")
    if "world_path" in fixture:
        fixture["world_path"] = str(resolve(text(fixture["world_path"], "world_path"), Path(source.path)))
    evaluator = mapping(data["evaluator"], "evaluator")
    fields(evaluator, {"name", "parameters"}, {"name", "parameters"}, "evaluator")
    participants = []
    if "participants" in data:
        if not isinstance(data["participants"], list) or not data["participants"]:
            raise ConfigError("participants must be a nonempty list")
        for entry in data["participants"]:
            row = mapping(entry, "participant")
            fields(row, {"id", "player_state"}, {"id", "player_state"}, "participant")
            name = identifier(row["id"], "participant id")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}", name):
                raise ConfigError("Participant IDs must be native player names: 1-16 ASCII letters/digits/underscores")
            participants.append(ParticipantConfig(name, mapping(row["player_state"], "participant player_state")))
        if len({p.id.casefold() for p in participants}) != len(participants):
            raise ConfigError("Participant IDs must be unique ignoring case")
        if "player_state" in fixture:
            raise ConfigError("Declare player_state either in fixture or in participants, not both")
        if evaluator["name"] != "team":
            raise ConfigError("Explicit participants require a team evaluator, including a one-member team")
    return TaskConfig(
        identifier(data["id"], "task id"), game, mode, text(data["task"], "task"),
        positive(data["time_limit_seconds"], "time_limit_seconds"), fixture,
        text(evaluator["name"], "evaluator name"), mapping(evaluator["parameters"], "evaluator parameters"),
        tools, source, tuple(participants), capabilities,
    )


def load_model(value: object) -> ModelConfig:
    model = mapping(value, "model")
    fields(model, set(ModelConfig.__dataclass_fields__), {"provider", "name"}, "model")
    provider = text(model["provider"], "provider")
    if provider not in ("github_copilot", "openai", "vllm"):
        raise ConfigError(f"Unsupported provider: {provider}")
    reasoning = text(model["reasoning_effort"], "reasoning_effort") if "reasoning_effort" in model else None
    if provider != "vllm" and {"base_url", "temperature", "enable_thinking"} & model.keys():
        raise ConfigError("base_url, temperature and enable_thinking are vLLM-only settings")
    if provider == "vllm" and reasoning is not None:
        raise ConfigError("vLLM uses enable_thinking, not reasoning_effort")
    temperature = model.get("temperature", 0)
    if (not isinstance(temperature, (int, float)) or isinstance(temperature, bool)
            or not math.isfinite(temperature) or temperature < 0):
        raise ConfigError("temperature must be finite and nonnegative")
    thinking = model.get("enable_thinking", False)
    if type(thinking) is not bool:
        raise ConfigError("enable_thinking must be boolean")
    return ModelConfig(
        provider, text(model["name"], "model name"), reasoning,
        integer(model.get("max_output_tokens", 4096), "max_output_tokens"),
        integer(model.get("max_attempts", 3), "max_attempts"),
        positive(model.get("timeout_seconds", 120), "timeout_seconds"),
        text(model.get("base_url", "http://127.0.0.1:8001/v1"), "base_url"), float(temperature), thinking,
    )


def load_experiment(path: Path) -> ExperimentConfig:
    data, source = read(path)
    required = {"id", "game", "tasks", "repetitions", "agents"}
    fields(data, required, required, "experiment")
    if not isinstance(data["agents"], list) or not data["agents"]:
        raise ConfigError("agents must be a nonempty list")
    agents = []
    agent_ids = set()
    for value in data["agents"]:
        agent = mapping(value, "agent")
        fields(agent, {"id", "name", "model", "observation_history"}, {"id", "name", "model"}, "agent")
        agent_id = identifier(agent["id"], "agent id")
        if agent_id in agent_ids:
            raise ConfigError(f"Duplicate agent id: {agent_id}")
        agent_ids.add(agent_id)
        name = text(agent["name"], "agent name")
        if "observation_history" in agent and name != "tool_calling":
            raise ConfigError("observation_history is supported only by tool_calling")
        agents.append(AgentConfig(
            agent_id, name, load_model(agent["model"]),
            integer(agent.get("observation_history", 1), "observation_history"),
        ))
    raw_tasks = data["tasks"]
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ConfigError("tasks must be a nonempty list of explicit file references")
    tasks = []
    seen = set()
    game = text(data["game"], "game")
    for entry in raw_tasks:
        reference = mapping(entry, "task reference")
        fields(reference, {"path"}, {"path"}, "task reference")
        task = load_task(resolve(text(reference["path"], "task path"), Path(source.path)))
        key = (task.game, task.id, task.task_type)
        if task.game != game or key in seen:
            raise ConfigError(f"Conflicting or duplicate task identity: {key}")
        seen.add(key)
        tasks.append(task)
    return ExperimentConfig(
        identifier(data["id"], "experiment id"), game, tuple(tasks),
        integer(data["repetitions"], "repetitions"), tuple(agents), source,
    )
