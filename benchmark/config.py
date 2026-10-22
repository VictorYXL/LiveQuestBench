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


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str
    reasoning_effort: str | None = None
    max_output_tokens: int = 4096
    max_attempts: int = 1
    timeout_seconds: float = 120
    base_url: str = "http://127.0.0.1:8001/v1"
    temperature: float = 0
    enable_thinking: bool = False


@dataclass(frozen=True)
class ExperimentConfig:
    id: str
    game: str
    tasks: tuple[TaskConfig, ...]
    repetitions: int
    agent: str
    model: ModelConfig
    source: Source

    def resolved(self) -> dict:
        result = asdict(self)
        inactive = ("reasoning_effort",) if self.model.provider == "vllm" else (
            "base_url", "temperature", "enable_thinking",
        )
        for name in inactive:
            result["model"].pop(name)
        return result


def load_task(path: Path) -> TaskConfig:
    data, source = read(path)
    required = {"id", "game", "task_type", "task", "time_limit_seconds", "fixture", "evaluator"}
    fields(data, required | {"tools"}, required, "task")
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
    return TaskConfig(
        identifier(data["id"], "task id"), game, mode, text(data["task"], "task"),
        positive(data["time_limit_seconds"], "time_limit_seconds"), fixture,
        text(evaluator["name"], "evaluator name"), mapping(evaluator["parameters"], "evaluator parameters"),
        tools, source,
    )


def load_experiment(path: Path) -> ExperimentConfig:
    data, source = read(path)
    required = {"id", "game", "tasks", "repetitions", "agent", "model"}
    fields(data, required, required, "experiment")
    agent = mapping(data["agent"], "agent")
    fields(agent, {"name"}, {"name"}, "agent")
    model = mapping(data["model"], "model")
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
    selected = ModelConfig(
        provider, text(model["name"], "model name"), reasoning,
        integer(model.get("max_output_tokens", 4096), "max_output_tokens"),
        integer(model.get("max_attempts", 1), "max_attempts"),
        positive(model.get("timeout_seconds", 120), "timeout_seconds"),
        text(model.get("base_url", "http://127.0.0.1:8001/v1"), "base_url"), float(temperature), thinking,
    )
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
        integer(data["repetitions"], "repetitions"), text(agent["name"], "agent name"), selected, source,
    )
