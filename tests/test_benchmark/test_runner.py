"""Execution-only regressions for async retirement, output isolation and failure cleanup."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time

import pytest

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from benchmark.config import ConfigError, load_experiment
from game.bindings import Controls, GameBinding
from benchmark.runner import run_bounded, run_episode, run_experiment
from game.base_game import BaseGame


ROOT = Path(__file__).resolve().parents[2]


def test_bounded_retirement_on_deadline_cancel_and_gate_failure():
    class WaitingAgent(BaseAgent[object]):
        def __init__(self, events):
            self.events = events
            self.stopped = asyncio.Event()

        async def run(self, context):
            self.events.append("run")
            await self.stopped.wait()
            self.events.append("retired")
            return AgentExit(AgentExitReason.STOPPED)

        async def stop(self, reason):
            self.events.append(reason)
            self.stopped.set()

        async def close(self):
            raise AssertionError("The Episode owner, not run_bounded, owns resource cleanup")

    async def check():
        for mode in ("deadline", "expired", "cancel", "gate_error"):
            events = []
            agent = WaitingAgent(events)
            now = time.monotonic_ns()
            context = AgentContext("test", "wait", object(), now, now + 10_000_000)
            if mode == "expired":
                context = replace(context, started_at_ns=now - 10, deadline_at_ns=now - 1)

            async def end():
                events.append("end")
                if mode == "gate_error":
                    raise RuntimeError("gate failed")

            work = asyncio.create_task(run_bounded(agent, context, end))
            if mode == "cancel":
                await asyncio.sleep(0)
                work.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await work
                assert StopReason.OPERATOR_CANCEL in events
            elif mode == "gate_error":
                with pytest.raises(ExceptionGroup, match="retirement"):
                    await work
            else:
                outcome, timeout = await work
                assert timeout and outcome.reason == AgentExitReason.STOPPED
            if mode == "expired":
                assert "run" not in events
            else:
                assert events.index("end") < events.index("retired")
            assert agent.stopped.is_set()
        pending = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        assert not pending

    asyncio.run(check())


def test_failed_admission_persists_and_never_overwrites(tmp_path):
    config = tmp_path / "invalid.yaml"
    config.write_text("id: incomplete\n")
    output = tmp_path / "run"
    with pytest.raises(ConfigError):
        asyncio.run(run_experiment(config, output))
    summary = (output / "summary.json").read_bytes()
    assert json.loads(summary)["status"] == "admission_error"
    with pytest.raises(FileExistsError):
        asyncio.run(run_experiment(config, output))
    assert (output / "summary.json").read_bytes() == summary


@pytest.mark.parametrize("fail_first", [False, True])
def test_agent_task_repetition_matrix_is_serial_and_separately_summarized(tmp_path, monkeypatch, fail_first):
    config = load_experiment(ROOT / "config/veloren/experiments/visual_motor_all.yaml")
    first = config.agents[0]
    second = replace(first, id="second", model=replace(first.model, name="another-model"))
    tasks = (config.tasks[0], replace(config.tasks[0], task_type="structured_tool"))
    config = replace(config, tasks=tasks, repetitions=2, agents=(first, second))
    monkeypatch.setattr("benchmark.runner.load_experiment", lambda path: config)
    monkeypatch.setattr("benchmark.runner.validate_experiment", lambda config: None)
    monkeypatch.setattr("benchmark.runner.provenance", lambda: {"offline": True})
    active = 0
    calls = []

    async def episode(selected, task, root, row, **kwargs):
        nonlocal active
        assert active == 0
        active += 1
        assert root == output / selected.id / f"{task.id}--{task.task_type}" / f"episode_{row['repetition']}"
        assert root == output / row["output_path"]
        root.mkdir(parents=True)
        calls.append((selected.id, task.id, task.task_type, row["repetition"]))
        assert row["agent"]["model"]["name"] == selected.model.name
        await asyncio.sleep(0)
        row.update(status="error" if fail_first else "completed",
                   measurement="unavailable" if fail_first else "valid",
                   task_outcome="unknown" if fail_first else "success")
        active -= 1

    monkeypatch.setattr("benchmark.runner.run_episode", episode)
    output = tmp_path / "run"
    summary = asyncio.run(run_experiment(Path(config.source.path), output))
    expected = [(agent.id, task.id, task.task_type, repetition)
                for agent in config.agents for task in tasks for repetition in (1, 2)]
    assert calls == (expected[:1] if fail_first else expected)
    assert len(summary["episodes"]) == len({row["episode_id"] for row in summary["episodes"]}) == 8
    assert len({row["output_path"] for row in summary["episodes"]}) == 8
    for row in summary["episodes"]:
        assert (output / row["output_path"]).is_dir() == (row["status"] != "not_run")
    assert len(summary["groups"]) == 4
    assert {group["agent_id"] for group in summary["groups"]} == {first.id, second.id}
    assert all(group["scheduled"] == 2 for group in summary["groups"])
    assert summary["status"] == ("error" if fail_first else "completed")
    if fail_first:
        assert [row["status"] for row in summary["episodes"]] == ["error"] + ["not_run"] * 7
    assert json.loads((output / "summary.json").read_text()) == summary


def test_episode_faults_preserve_evidence_and_cleanup(tmp_path, monkeypatch):
    config = load_experiment(ROOT / "config/veloren/experiments/visual_motor_all.yaml")
    for fault in ("execution", "measurement", "cleanup"):
        events = []

        async def observe() -> str:
            return "public"

        async def execute(name, arguments) -> str:
            raise AssertionError("No tools should be called by this fault probe")

        controls = Controls(observe, execute)

        class Game(BaseGame[Controls]):
            async def start(self):
                events.append("start")

            async def begin(self):
                events.append("begin")

            async def end(self):
                events.append("end")

            def get_agent_interface(self):
                return controls

            def get_instructions(self):
                return "public instructions"

            async def save_snapshot(self, destination):
                destination.mkdir()
                events.append(destination.name)
                return destination

            async def close(self):
                events.append("game_close")
                if fault == "cleanup":
                    raise RuntimeError("cleanup probe")

        class Agent(BaseAgent[Controls]):
            async def run(self, context):
                assert context.task == config.tasks[0].task
                assert context.interface is not game
                if fault == "execution":
                    raise RuntimeError("execution probe")
                return AgentExit(AgentExitReason.RETURNED)

            async def stop(self, reason):
                events.append("stop")

            async def close(self):
                events.append("agent_close")

        class Client:
            async def close(self):
                events.append("client_close")

        def evaluate(before, after):
            if fault == "measurement":
                raise ValueError("measurement probe")
            return {"success": False}

        game = Game()
        binding = GameBinding(game, lambda: (controls, []), evaluate, lambda before: None)
        monkeypatch.setattr("benchmark.runner.make_game", lambda *args, **kwargs: binding)
        monkeypatch.setattr("benchmark.runner.make_client", lambda *args: Client())
        monkeypatch.setattr("benchmark.runner.make_agent", lambda *args: Agent())
        output = tmp_path / fault
        result = asyncio.run(run_episode(
            config.agents[0], config.tasks[0], output, {"episode_id": fault},
            headless=True, recording=False, recording_fps=10,
        ))
        assert result["status"] == "error"
        assert (output / "after").is_dir()
        assert events.index("end") < events.index("after") < events.index("game_close")
        assert events[-1] == "client_close" and "agent_close" in events
        assert result["errors"] and json.loads((output / "result.json").read_text()) == result
        if fault == "measurement":
            assert result["measurement"] == "invalid" and result["task_outcome"] == "unknown"
        elif fault == "cleanup":
            assert result["measurement"] == "valid" and result["task_outcome"] == "failure"
