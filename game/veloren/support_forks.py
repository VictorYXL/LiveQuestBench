"""Materialize one private covered-support instance for either public track."""

from pathlib import Path
import secrets

from benchmark.config import TaskConfig
from game.veloren.fixtures.covered_support_forks_solid import TASK_ID, build_solid_candidate


def prepare_episode_fixture(task: TaskConfig) -> dict:
    if "world_path" not in task.fixture:
        raise ValueError("Covered support requires its complete fixture")
    world = Path(task.fixture["world_path"])
    expected = [build_solid_candidate(world, seed, task.task_type)[0] for seed in (0, 1)]
    if not any(
        task.id == row["id"] and task.game == row["game"]
        and task.task_type == row["task_type"] and task.task == row["task"]
        and task.time_limit_seconds == row["time_limit_seconds"]
        and task.fixture == row["fixture"]
        and task.evaluator == row["evaluator"]["name"]
        and task.evaluator_parameters == row["evaluator"]["parameters"]
        and task.tools == (tuple(row["tools"]) if "tools" in row else None)
        and not task.participants and task.capabilities is not None
        and task.capabilities.primary == tuple(row["capabilities"]["primary"])
        and task.capabilities.secondary == tuple(row["capabilities"]["secondary"])
        for row in expected
    ):
        raise ValueError("Covered-support public contract, geometry, resources, score and profiles must match")
    instance, _ = build_solid_candidate(world, secrets.randbits(64), task.task_type)
    if instance not in expected:
        raise ValueError("Generated covered-support instance must belong to the two declared mappings")
    return instance["fixture"]
