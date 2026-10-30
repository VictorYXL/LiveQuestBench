"""Materialize one private instance of the exact reviewed L05 v2 contract."""

from pathlib import Path
import secrets

from benchmark.config import TaskConfig
from game.veloren.fixtures.covered_support_forks_solid import build_solid_candidate


TASK_ID = "covered_support_forks_local_solid_v2"


def prepare_episode_fixture(task: TaskConfig) -> dict:
    if "world_path" not in task.fixture:
        raise ValueError("L05 v2 requires its complete reviewed fixture")
    world = Path(task.fixture["world_path"])
    expected = [build_solid_candidate(world, seed)[0] for seed in (0, 1)]
    if not any(
        task.id == row["id"] and task.game == row["game"]
        and task.task_type == row["task_type"] and task.task == row["task"]
        and task.time_limit_seconds == row["time_limit_seconds"]
        and task.fixture == row["fixture"]
        and task.evaluator == row["evaluator"]["name"]
        and task.evaluator_parameters == row["evaluator"]["parameters"]
        and task.tools is None and not task.participants and task.capabilities is None
        for row in expected
    ):
        raise ValueError("L05 v2 public contract, geometry, resources, score and profiles must match review")
    instance, _ = build_solid_candidate(world, secrets.randbits(64))
    if instance not in expected:
        raise ValueError("Generated L05 v2 instance must belong to the two reviewed mappings")
    return instance["fixture"]
