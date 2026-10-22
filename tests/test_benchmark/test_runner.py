"""Execution-only regressions for async retirement, output isolation and failure cleanup."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time

import pytest

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.llm_client.base_client import BaseLLMClient, LLMResponse, Message
from benchmark.config import ConfigError, load_experiment
from benchmark.results import EpisodeLog
from game.bindings import Controls, GameBinding
from benchmark.runner import output_lock, prepare_episode, run_bounded, run_episode, run_experiment
from game.base_game import BaseGame


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("enabled", [True, False])
def test_chat_recording_preserves_inputs_retries_and_cancellation(tmp_path, enabled):
    log = EpisodeLog(tmp_path, record_chat=enabled)
    image = b"\x89PNG\r\n\x1a\nrecording-probe"
    message = Message("user", [{"type": "text", "text": "Inspect this frame"},
                               {"type": "image", "mime_type": "image/png", "data": image}])

    class Client(BaseLLMClient):
        calls = 0

        async def _request_impl(self, messages, **kwargs):
            self.calls += 1
            assert messages[0] is message and message.content[1]["data"] is image
            if self.calls == 1:
                raise TimeoutError("retry probe")
            if self.calls == 3:
                raise asyncio.CancelledError()
            return LLMResponse(content="Observed", finish_reason="stop", usage={"total_tokens": 3})

        async def close(self):
            pass

    async def run():
        client = Client(max_attempts=2, retry_backoff=0, on_request=log.request)
        client.on_query = log.query if enabled else None
        log.message(message)
        log.event("observation", observation=message.content)
        response = await client.chat([message], tools=[], tool_choice="auto")
        log.message(Message("assistant", response.content))
        with pytest.raises(asyncio.CancelledError):
            await client.chat([message])
        log.event("tool_error", call_id=1, name="probe", error_type="RuntimeError", message="tool failure detail")
        log.event("end", status="cancelled")
        await client.close()

    asyncio.run(run())
    assert log.accounting()["request_attempts"] == 3
    assert log.accounting()["successful_attempts"] == 1
    assert not (tmp_path / "trace.jsonl").exists()
    if not enabled:
        assert not (tmp_path / "recording").exists()
        return
    directory = tmp_path / "recording/chat"
    rows = [json.loads(line) for line in (directory / "query.jsonl").read_text().splitlines()]
    assert [(row["query_id"], row["attempt"], row["event"]) for row in rows] == [
        (1, 1, "prompt"), (1, 1, "error"), (1, 2, "prompt"), (1, 2, "response"),
        (2, 1, "prompt"), (2, 1, "error"),
    ]
    assert rows[-1]["request"]["error_type"] == "CancelledError"
    assert rows[3]["response"]["content"] == "Observed"
    images = list((directory / "images").iterdir())
    assert len(images) == 1 and images[0].read_bytes() == image
    marker = "{image: images/" + images[0].name + "}"
    for name in ("agent.jsonl", "agent.log", "query.jsonl", "query.log"):
        assert marker in (directory / name).read_text()
    agent = [json.loads(line) for line in (directory / "agent.jsonl").read_text().splitlines()]
    assert [row["event"] for row in agent] == ["message", "observation", "message", "tool_error", "end"]
    assert "tool failure detail" in (directory / "agent.log").read_text()


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


def test_failed_admission_preserves_each_launch(tmp_path):
    config = tmp_path / "invalid.yaml"
    config.write_text("id: incomplete\n")
    output = tmp_path / "run"
    with pytest.raises(ConfigError):
        asyncio.run(run_experiment(config, output))
    summary = (output / "summary.json").read_bytes()
    assert json.loads(summary)["status"] == "admission_error"
    with pytest.raises(ConfigError):
        asyncio.run(run_experiment(config, output))
    summaries = list((output / "runs").glob("*/summary.json"))
    assert len(summaries) == 2
    assert summary in [path.read_bytes() for path in summaries]


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
        assert root == output / selected.id / f"{task.id}.{task.task_type}" / f"episode_{row['repetition']}"
        assert row["episode_id"] == (
            f"{selected.id}.{task.game}.{task.id}.{task.task_type}.{row['repetition']:04d}"
        )
        assert root == output / row["output_path"]
        (root / "results").mkdir(parents=True)
        calls.append((selected.id, task.id, task.task_type, row["repetition"]))
        assert row["agent"]["model"]["name"] == selected.model.name
        await asyncio.sleep(0)
        row.update(status="error" if fail_first else "completed",
                   measurement="unavailable" if fail_first else "valid",
                   task_outcome="unknown" if fail_first else "failure",
                   errors=[], finished_at_ns=1)
        (root / "results/result.json").write_text(json.dumps(row))
        if not fail_first:
            (root / "results/evaluation.json").write_text('{"success": false}')
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
    calls.clear()
    resumed = asyncio.run(run_experiment(Path(config.source.path), output))
    assert calls == (expected[:1] if fail_first else [])
    assert resumed["status"] == summary["status"]
    assert len(list((output / "runs").glob("*/config.json"))) == 2
    if not fail_first:
        extra = replace(first, id="additional")
        config = replace(config, id="another-experiment", agents=(extra,), tasks=(tasks[0],), repetitions=1)
        added = asyncio.run(run_experiment(Path(config.source.path), output))
        assert calls == [(extra.id, tasks[0].id, tasks[0].task_type, 1)]
        assert added["experiment_id"] == "another-experiment"
        assert len(list(output.glob("*/*/episode_*/results/result.json"))) == 9
        assert len(list((output / "runs").glob("*/summary.json"))) == 3
        legacy = output / added["episodes"][0]["output_path"]
        for name in ("result.json", "evaluation.json"):
            (legacy / "results" / name).rename(legacy / name)
        (legacy / "results").rmdir()
        calls.clear()
        asyncio.run(run_experiment(Path(config.source.path), output))
        assert calls == []


def test_resume_protects_conflicts_and_active_output(tmp_path):
    row = {"output_path": "agent/task.visual_motor/episode_1", "episode_id": "one",
           "configuration_sha256": "current"}
    root = tmp_path / row["output_path"]
    root.mkdir(parents=True)
    (root / "unfinished.txt").write_text("interrupted before result")
    assert prepare_episode(tmp_path, row) is False
    assert not root.exists()
    root.mkdir()
    (root / "result.json").write_text(json.dumps({**row, "configuration_sha256": "other"}))
    with pytest.raises(ValueError, match="configuration changed"):
        prepare_episode(tmp_path, row)
    assert root.exists()
    with output_lock(tmp_path):
        with pytest.raises(RuntimeError, match="Another benchmark"):
            with output_lock(tmp_path):
                pytest.fail("Concurrent output writer admitted")
    with output_lock(tmp_path):
        pass


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
        assert result["errors"] and json.loads((output / "results/result.json").read_text()) == result
        if fault == "measurement":
            assert result["measurement"] == "invalid" and result["task_outcome"] == "unknown"
        elif fault == "cleanup":
            assert result["measurement"] == "valid" and result["task_outcome"] == "failure"
            assert json.loads((output / "results/evaluation.json").read_text()) == {"success": False}
