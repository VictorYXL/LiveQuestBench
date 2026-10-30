"""Canonical matrix, dependency admission and paired support-task regressions."""

import asyncio
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from benchmark.config import CAPABILITIES, load_experiment, load_task
from benchmark.factory import make_game
from game.veloren import structured_tools
from game.veloren.evaluators.endpoints import state_checks
from game.veloren.fixture import solid_voxels
from game.veloren.fixtures.covered_support_forks_solid import build_solid_candidate
from game.veloren.support_forks import prepare_episode_fixture


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("game", ["minecraft", "veloren"])
def test_complete_paired_catalog_and_real_factory_admission(game, tmp_path):
    tracks = {}
    for folder, track in (("structured_tools", "structured_tool"), ("visual_motor", "visual_motor")):
        paths = sorted((ROOT / "config" / game / "tasks" / folder).glob("*.yaml"))
        tasks = [load_task(path) for path in paths]
        assert len(tasks) == 30
        assert len({task.id for task in tasks}) == 30
        counts = Counter()
        for task in tasks:
            assert task.game == game and task.task_type == track
            assert task.capabilities is not None and len(task.capabilities.primary) == 1
            counts.update(task.capabilities.primary)
            assert not re.search(r"_v\d+|_prototype|_c\d+$", task.id)
            assert Path(task.source.path).stem == task.id
            assert not re.search(
                r"DEVELOPMENTAL|Version\d+|not an admitted benchmark task|This v\d+ condition",
                task.task,
            )
            binding = make_game(
                task, tmp_path / folder / task.id,
                headless=True, recording=False, recording_fps=10,
            )
            assert binding.game.phase == "new"
        assert counts == Counter({capability: 5 for capability in CAPABILITIES})
        full = load_experiment(ROOT / "config" / game / "experiments" / f"full_{folder}.yaml")
        assert {task.source.path for task in full.tasks} == {task.source.path for task in tasks}
        assert len(full.tasks) == 30 and full.repetitions == 1
        tracks[track] = {task.id: task for task in tasks}
    assert tracks["structured_tool"].keys() == tracks["visual_motor"].keys()
    visual_profiles = {"camera_observation", "route_observation", "scene_observation"}
    for task_id, first in tracks["structured_tool"].items():
        second = tracks["visual_motor"][task_id]
        assert first.capabilities == second.capabilities
        assert first.time_limit_seconds == second.time_limit_seconds
        assert (first.evaluator, first.evaluator_parameters) == (
            second.evaluator, second.evaluator_parameters,
        )
        assert {key: value for key, value in first.fixture.items() if key not in visual_profiles} == {
            key: value for key, value in second.fixture.items() if key not in visual_profiles
        }


@pytest.mark.parametrize("seed", [0, 1])
def test_support_tracks_share_mapping_and_enforce_exact_contract(seed):
    tasks = {
        folder: load_task(ROOT / f"config/veloren/tasks/{folder}/covered_support_forks.yaml")
        for folder in ("structured_tools", "visual_motor")
    }
    fixtures = []
    for task in tasks.values():
        with patch("game.veloren.support_forks.secrets.randbits", return_value=seed):
            fixture = prepare_episode_fixture(task)
        expected, private = build_solid_candidate(
            Path(task.fixture["world_path"]), seed, task.task_type,
        )
        assert fixture == expected["fixture"]
        voxels = solid_voxels(fixture)
        # Both opposite-facing galleries must retain the same relative support side.
        left = private["side"] == "left"
        assert ((18705, 10806, 501) in voxels) == left
        assert ((18713, 10806, 501) in voxels) != left
        assert ((18706, 10830, 500) in voxels) == left
        assert ((18714, 10830, 500) in voxels) != left
        assert ((18742, 10828, 500) in voxels) == left
        assert ((18734, 10828, 500) in voxels) != left
        fixtures.append(voxels)
        with pytest.raises(ValueError, match="public contract"):
            prepare_episode_fixture(replace(task, time_limit_seconds=task.time_limit_seconds + 1))
        with pytest.raises(ValueError, match="public contract"):
            prepare_episode_fixture(replace(task, evaluator_parameters={
                **task.evaluator_parameters, "min_health": 0,
            }))
    assert fixtures[0] == fixtures[1]
    with pytest.raises(ValueError, match="public contract"):
        prepare_episode_fixture(replace(tasks["structured_tools"], tools=("MoveTool",)))
    assert "scene_observation" not in tasks["structured_tools"].fixture
    assert tasks["visual_motor"].fixture["scene_observation"] == "native-solid-scene/1"


def test_support_structured_controls_relay_only_declared_tools_and_public_state(tmp_path):
    task = load_task(ROOT / "config/veloren/tasks/structured_tools/covered_support_forks.yaml")
    binding = make_game(task, tmp_path, headless=True, recording=False, recording_fps=10)
    calls = []

    async def observe():
        raw = {name: None for name in structured_tools.FIELDS}
        raw.update(
            energy={"current": 50, "maximum": 100, "fraction": 0.5},
            private_mapping={"side": "right"}, fixture=task.fixture, seed=123,
        )
        return structured_tools.project(raw, energy=True)

    async def execute(name, arguments):
        calls.append(structured_tools.validate_tool(name, arguments))
        return {"status": "completed"}

    binding.game._interface = structured_tools.StructuredInterface(observe, execute)
    binding.game.phase = "ready"
    controls, tools = binding.controls()
    assert {tool.name for tool in tools} == set(task.tools)

    async def run():
        public = json.loads(await controls.observe())
        assert {"private_mapping", "fixture", "seed"}.isdisjoint(public)
        assert public["energy"]["current"] == 50
        await controls.execute("InspectTerrainTool", {"x": 18705, "y": 10806, "z": 501})
        await controls.execute("MoveTool", {"direction": "forward", "duration_ticks": 5})
        await controls.execute("StopTool", {})
        with pytest.raises(ValueError, match="not"):
            await controls.execute("CraftTool", {"recipe": "anything", "amount": 1})

    asyncio.run(run())
    assert calls == [
        ("inspect_terrain", {"position": [18705, 10806, 501]}),
        ("move_forward", {"duration_ticks": 5}), ("stop", {}),
    ]


def test_support_public_health_floor_matches_endpoint_boundary():
    for folder in ("structured_tools", "visual_motor"):
        task = load_task(ROOT / f"config/veloren/tasks/{folder}/covered_support_forks.yaml")
        assert "at least one health" in task.task
        for health, expected in ((0.5, False), (1.0, True)):
            final = {
                "survival": {"health": {"current": health}},
                "position": task.evaluator_parameters["position"]["target"],
                "velocity": [0, 0, 0], "on_ground": True,
            }
            assert state_checks({}, final, **task.evaluator_parameters)["success"] is expected
