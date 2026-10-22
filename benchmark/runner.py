"""Serial, benchmark-owned Episode boundaries around native Agent loops."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
import sys
import time
import traceback
from typing import TypeVar

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.llm_client.base_client import BaseLLMClient
from benchmark.config import AgentConfig, TaskConfig, load_experiment
from benchmark.factory import make_agent, make_client, make_game, validate_experiment
from benchmark.results import EpisodeLog, provenance, summarize, write_json
from game.base_game import AgentAccessClosed
from game.bindings import Controls


InterfaceT = TypeVar("InterfaceT")


async def run_bounded(
    agent: BaseAgent[InterfaceT], public: AgentContext[InterfaceT],
    end_game: Callable[[], Awaitable[None]], stop_after_tool: asyncio.Event | None = None,
) -> tuple[AgentExit, bool]:
    """Revoke the game gate before stopping/joining the native loop, including errors."""
    timed_out = time.monotonic_ns() >= public.deadline_at_ns
    running = None if timed_out else asyncio.create_task(agent.run(public))
    signal = asyncio.create_task(stop_after_tool.wait()) if stop_after_tool is not None else None
    operator_stop = cancelled = False
    errors: list[Exception] = []
    try:
        if running is not None:
            done, _ = await asyncio.wait(
                {running, signal} if signal is not None else {running},
                timeout=max(0, (public.deadline_at_ns - time.monotonic_ns()) / 1e9),
                return_when=asyncio.FIRST_COMPLETED,
            )
            timed_out = not done
            operator_stop = signal is not None and signal in done
    except asyncio.CancelledError:
        cancelled = True
    finally:
        if signal is not None:
            signal.cancel()
            await asyncio.gather(signal, return_exceptions=True)
        try:
            await asyncio.wait_for(end_game(), timeout=30)
        except Exception as error:
            errors.append(error)
        try:
            if timed_out or operator_stop or cancelled or errors or (running is not None and not running.done()):
                reason = (StopReason.OPERATOR_CANCEL if cancelled or operator_stop else
                          StopReason.DEADLINE if timed_out else StopReason.INFRASTRUCTURE_ERROR)
                await asyncio.wait_for(agent.stop(reason), timeout=10)
        except Exception as error:
            errors.append(error)
        try:
            if running is None:
                outcome = AgentExit(AgentExitReason.STOPPED, native_reason="deadline_before_agent_run")
            else:
                outcomes = await asyncio.wait_for(asyncio.gather(running, return_exceptions=True), timeout=10)
                outcome = outcomes[0]
        except TimeoutError as error:
            errors.append(error)
            outcome = error
        finally:
            if running is not None and not running.done():
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
    expected_stop = timed_out or operator_stop or cancelled
    if isinstance(outcome, (asyncio.CancelledError, AgentAccessClosed)) and expected_stop:
        outcome = AgentExit(AgentExitReason.STOPPED, native_reason="benchmark_game_gate_closed")
    if isinstance(outcome, asyncio.CancelledError):
        outcome = RuntimeError("Agent cancelled without a benchmark stop request")
    if isinstance(outcome, Exception) and all(outcome is not error for error in errors):
        errors.append(outcome)
    if errors:
        if cancelled:
            raise asyncio.CancelledError from ExceptionGroup("Episode retirement failed", errors)
        raise ExceptionGroup("Episode execution or retirement failed", errors)
    if cancelled:
        raise asyncio.CancelledError
    if not isinstance(outcome, AgentExit):
        raise TypeError("Agent must return AgentExit")
    if outcome.reason == AgentExitReason.STOPPED and not expected_stop:
        raise RuntimeError("Agent reported stopped without a benchmark stop request")
    return outcome, timed_out


def logged_controls(public: Controls, log: EpisodeLog) -> Controls:
    async def observe():
        log.observations += 1
        started = time.monotonic_ns()
        value = await public.observe()
        log.event("observation", started_at_ns=started, value=value)
        return value

    async def execute(name: str, arguments: dict[str, object]) -> str:
        log.tool_calls += 1
        call_id = log.tool_calls
        log.event("tool_start", call_id=call_id, name=name, arguments=arguments)
        try:
            value = await public.execute(name, arguments)
        except (Exception, asyncio.CancelledError) as error:
            log.event("tool_error", call_id=call_id, error_type=type(error).__name__, message=str(error))
            raise
        log.event("tool_end", call_id=call_id, result=value)
        return value

    return Controls(observe, execute)


async def run_episode(
    agent_config: AgentConfig, task: TaskConfig, root: Path, result: dict, *,
    headless: bool, recording: bool, recording_fps: int,
) -> dict:
    root.mkdir(parents=True)
    log = EpisodeLog(root)
    binding = None
    agent: BaseAgent[Controls] | None = None
    client: BaseLLMClient | None = None
    stage = "initialization"
    cancelled = False
    begun = False
    result.update(status="running", measurement="unavailable", task_outcome="unknown", errors=[])
    write_json(root / "result.json", result)

    def record_error(error: BaseException, failed_stage: str) -> None:
        result["errors"].append({
            "stage": failed_stage, "type": type(error).__name__, "message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
        })
        print(f"{result['episode_id']} [{failed_stage}]: {type(error).__name__}: {error}", file=sys.stderr)

    try:
        binding = make_game(task, root / "game", headless=headless, recording=recording, recording_fps=recording_fps)
        client = make_client(agent_config.model, log.request)
        await binding.game.start()
        before = await binding.game.save_snapshot(root / "before")
        binding.verify_initial(before)
        public, tools = binding.controls()
        public = logged_controls(public, log)
        result["tools"] = [tool.schema() for tool in tools]
        agent = make_agent(agent_config, client, tools, root / "agent", log.message)
        if isinstance(agent, ProcessAgent):
            result["agent_source"] = agent.source
        stage = "execution"
        started = time.monotonic_ns()
        deadline = started + int(task.time_limit_seconds * 1e9)
        result.update(started_at_ns=started, deadline_at_ns=deadline)
        instructions = binding.game.get_instructions()
        instructions += "\nOnly the supplied tool schemas are available for this task."
        context = AgentContext(result["episode_id"], task.task, public, started, deadline, instructions)
        await asyncio.wait_for(binding.game.begin(), timeout=min(30, task.time_limit_seconds))
        begun = True

        async def end() -> None:
            result["end_requested_at_ns"] = time.monotonic_ns()
            await binding.game.end()
            result["ended_at_ns"] = time.monotonic_ns()

        exit_info, timed_out = await run_bounded(agent, context, end)
        result.update(agent_exit=asdict(exit_info), deadline_reached=timed_out)
        stage = "measurement"
        after = await binding.game.save_snapshot(root / "after")
        evaluation = await asyncio.to_thread(binding.evaluate, before, after)
        if type(evaluation.get("success")) is not bool:
            raise ValueError("Evaluator must return a boolean success field")
        write_json(root / "evaluation.json", evaluation)
        result.update(status="completed", measurement="valid",
                      task_outcome="success" if evaluation["success"] else "failure")
    except asyncio.CancelledError as error:
        cancelled = True
        result["status"] = "cancelled"
        record_error(error, stage)
    except Exception as error:
        result["status"] = "error"
        if stage == "measurement":
            result["measurement"] = "invalid"
        record_error(error, stage)
    finally:
        if binding is not None and begun and "end_requested_at_ns" not in result:
            try:
                result["end_requested_at_ns"] = time.monotonic_ns()
                await asyncio.wait_for(binding.game.end(), timeout=30)
                result["ended_at_ns"] = time.monotonic_ns()
            except Exception as error:
                record_error(error, "end")
        if binding is not None and stage == "execution" and "ended_at_ns" in result:
            try:
                await binding.game.save_snapshot(root / "after")
            except Exception as error:
                record_error(error, "final_evidence")
        if agent is not None:
            try:
                await asyncio.wait_for(agent.close(), timeout=30)
            except Exception as error:
                record_error(error, "agent_cleanup")
            if isinstance(agent, ProcessAgent):
                result["native_agent"] = {"admitted": agent.admitted, "forced_termination": agent.forced_termination}
        if binding is not None:
            try:
                await asyncio.wait_for(binding.game.close(), timeout=60)
            except Exception as error:
                record_error(error, "game_cleanup")
        if client is not None:
            try:
                await client.close()
            except Exception as error:
                record_error(error, "client_cleanup")
        if result["errors"] and not cancelled:
            result["status"] = "error"
        result["finished_at_ns"] = time.monotonic_ns()
        if "ended_at_ns" in result:
            result["timing"] = {
                "active_wall_seconds": (result["ended_at_ns"] - result["started_at_ns"]) / 1e9,
                "end_acknowledgement_seconds": (result["ended_at_ns"] - result["end_requested_at_ns"]) / 1e9,
                "deadline_request_lateness_seconds": max(0, result["end_requested_at_ns"] - result["deadline_at_ns"]) / 1e9,
            }
        result["accounting"] = log.accounting()
        write_json(root / "result.json", result)
    if cancelled:
        raise asyncio.CancelledError
    return result


async def run_experiment(
    config: Path, output: Path, *, headless: bool = True, recording: bool = False, recording_fps: int = 10,
) -> dict:
    if type(recording_fps) is not int or not 1 <= recording_fps <= 60:
        raise ValueError("recording_fps must be an integer in [1, 60]")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict] = []
    summary: dict = {"status": "validating", "groups": [], "episodes": rows}
    admitted = False
    write_json(output / "summary.json", summary)
    try:
        experiment = load_experiment(config)
        write_json(output / "config.json", experiment.resolved())
        validate_experiment(experiment)
        admitted = True
        write_json(output / "provenance.json", provenance())
        write_json(output / "launch.json", {
            "headless": headless, "recording": recording, "recording_fps": recording_fps,
            "config": str(config.resolve()), "output": str(output),
        })
        for agent_config in experiment.agents:
            for task in experiment.tasks:
                for repetition in range(1, experiment.repetitions + 1):
                    episode_id = (
                        f"{agent_config.id}--{task.game}--{task.id}--{task.task_type}--{repetition:04d}"
                    )
                    episode_path = Path(agent_config.id) / f"{task.id}--{task.task_type}" / f"episode_{repetition}"
                    rows.append({
                        "episode_id": episode_id, "agent_id": agent_config.id, "agent": agent_config.resolved(),
                        "output_path": episode_path.as_posix(),
                        "game": task.game, "task_id": task.id, "task_type": task.task_type,
                        "repetition": repetition, "status": "not_run", "measurement": "unavailable",
                        "task_outcome": "unknown",
                    })
        for row in rows:
            agent_config = next(agent for agent in experiment.agents if agent.id == row["agent_id"])
            task = next(task for task in experiment.tasks
                        if task.id == row["task_id"] and task.task_type == row["task_type"])
            print(f"Running {row['episode_id']}", flush=True)
            row["status"] = "running"
            summary = {"experiment_id": experiment.id, "status": "running", **summarize(rows)}
            write_json(output / "summary.json", summary)
            await run_episode(agent_config, task, output / row["output_path"], row,
                              headless=headless, recording=recording, recording_fps=recording_fps)
            if row["status"] != "completed":
                break
        summary.update(status="completed" if all(row["status"] == "completed" for row in rows) else "error")
    except asyncio.CancelledError:
        summary["status"] = "cancelled"
        raise
    except Exception as error:
        summary.update(status="error" if admitted else "admission_error", error={
            "type": type(error).__name__, "message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
        })
        raise
    finally:
        summary.update(summarize(rows))
        write_json(output / "summary.json", summary)
    return summary
