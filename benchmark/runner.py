"""Serial, benchmark-owned Episode boundaries around native Agent loops."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback
from uuid import uuid4
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
RECOVERY_INSTRUCTIONS = (
    "\nAn unsuccessful action or attempt does not automatically end the episode."
    " If the objective remains achievable, use the remaining time to recover, revise your approach,"
    " and try again. Retries do not reset the world, restore spent resources, or extend the deadline."
    " Before finishing, check the required objectives against your available observations."
    " End when your objectives are complete, no useful attempt fits the remaining time,"
    " or you have evidence that completion is no longer possible."
)


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
    headless: bool, recording: bool, recording_fps: int, record_chat: bool = True,
) -> dict:
    root.mkdir(parents=True)
    results = root / "results"
    results.mkdir()
    log = EpisodeLog(root, record_chat=record_chat)
    binding = None
    agent: BaseAgent[Controls] | None = None
    client: BaseLLMClient | None = None
    stage = "initialization"
    cancelled = False
    begun = False
    result.update(status="running", measurement="unavailable", task_outcome="unknown", errors=[])
    write_json(results / "result.json", result)

    def record_error(error: BaseException, failed_stage: str) -> None:
        result["errors"].append({
            "stage": failed_stage, "type": type(error).__name__, "message": str(error),
            "traceback": "".join(traceback.format_exception(error)),
        })
        print(f"{result['episode_id']} [{failed_stage}]: {type(error).__name__}: {error}", file=sys.stderr)

    try:
        binding = make_game(task, root / "game", headless=headless, recording=recording,
                            recording_fps=recording_fps, recording_path=root / "recording" / "video.mp4")
        client = make_client(agent_config.model, log.request)
        result["model_history_policy"] = client.history_policy
        client.on_query = log.query if record_chat else None
        await binding.game.start()
        before = await binding.game.save_snapshot(root / "before")
        binding.verify_initial(before)
        if task.participants:
            from benchmark.team import TeamAgent
            from game.team import TeamGame
            assert isinstance(binding.game, TeamGame)

            async def no_shared_access(*args):
                raise PermissionError("Only role-scoped team controls are available")

            public = Controls(no_shared_access, no_shared_access)
            result["team_profile"] = "native-peer-team-v1"
            result["participants"] = [role.id for role in task.participants]
            agent = TeamAgent(agent_config, binding.game, root, log, record_chat=record_chat)
        else:
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
        instructions += RECOVERY_INSTRUCTIONS
        instructions += (
            "\nDo not select Quit Game, disconnect, or close the game window, even after completing the task."
            " Quitting the game is not task completion; an Agent-initiated quit counts as failure."
            " Leave the game running so the benchmark can evaluate the final state."
        )
        instructions += (
            "\nWhen finished, call final_answer with your answer."
            if agent_config.name == "smolagents" else
            "\nWhen finished, return a nonempty final response without tool calls to end your Agent turn."
        )
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
        write_json(results / "evaluation.json", evaluation)
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
        if (binding is not None and binding.metrics is not None
                and (root / "before").is_dir() and (root / "after").is_dir()):
            try:
                result["metrics"] = await asyncio.to_thread(
                    binding.metrics, root / "before", root / "after",
                )
                write_json(results / "metrics.json", result["metrics"])
            except Exception as error:
                record_error(error, "metrics")
                result["measurement"] = "invalid"
        if agent is not None:
            try:
                await asyncio.wait_for(agent.close(), timeout=60 if task.participants else 30)
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
        try:
            log.event("end", status=result["status"], errors=result["errors"],
                      agent_exit=result.get("agent_exit"), deadline_reached=result.get("deadline_reached"))
        except Exception as error:
            record_error(error, "chat_recording")
            if not cancelled:
                result["status"] = "error"
        write_json(results / "result.json", result)
    if cancelled:
        raise asyncio.CancelledError
    return result


@contextmanager
def output_lock(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    for name in (".runner.lock", "runs"):
        if (output / name).is_symlink():
            raise ValueError(f"Output control path must not be a symlink: {output / name}")
    with (output / ".runner.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"Another benchmark is using {output}") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def prepare_episode(output: Path, row: dict) -> bool:
    """Reuse completed measurements; remove only the exact incomplete episode."""
    root = output / row["output_path"]
    if any(path.is_symlink() for path in (root, root.parent, root.parent.parent, root / "results")):
        raise ValueError(f"Episode paths must not contain symlinks: {root}")
    if not root.exists():
        return False
    if not root.is_dir():
        raise ValueError(f"Episode path is not a directory: {root}")
    results = root / "results"
    if results.exists() and not results.is_dir():
        raise ValueError(f"Episode results path is not a directory: {results}")
    if not results.exists():
        results = root
    result_path = results / "result.json"
    previous = None
    if result_path.exists():
        try:
            previous = json.loads(result_path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(f"Unreadable result; inspect before deleting {root}") from error
        if not isinstance(previous, dict):
            raise ValueError(f"Invalid result in {root}")
        if previous.get("configuration_sha256") != row["configuration_sha256"]:
            raise ValueError(f"Episode configuration changed or lacks a fingerprint; use a new output or Agent ID: {root}")
        if previous.get("episode_id") != row["episode_id"]:
            raise ValueError(f"Episode identity conflict: {root}")
    evaluation_path = results / "evaluation.json"
    if previous and previous.get("status") == "completed" and previous.get("measurement") == "valid":
        if not evaluation_path.is_file():
            raise ValueError(f"Completed result lacks evaluation.json: {root}")
        evaluation = json.loads(evaluation_path.read_text())
        if (not isinstance(evaluation, dict) or type(evaluation.get("success")) is not bool
                or previous.get("task_outcome") != ("success" if evaluation["success"] else "failure")
                or previous.get("errors") or not previous.get("finished_at_ns")):
            raise ValueError(f"Inconsistent completed measurement: {root}")
        if "metrics" in previous:
            metrics_path = results / "metrics.json"
            if not metrics_path.is_file() or json.loads(metrics_path.read_text()) != previous["metrics"]:
                raise ValueError(f"Inconsistent completed metrics: {root}")
        print(f"Skipping completed {row['episode_id']}", flush=True)
        row.update(previous)
        return True
    print(f"Removing incomplete Episode before retry: {root}", flush=True)
    shutil.rmtree(root)
    return False


async def run_experiment(
    config: Path, output: Path, *, headless: bool = True, recording: bool = True, recording_fps: int = 10,
    record_chat: bool = True,
) -> dict:
    output = output.resolve()
    with output_lock(output):
        return await _run_experiment(
            config, output, headless=headless, recording=recording, recording_fps=recording_fps,
            record_chat=record_chat,
        )


async def _run_experiment(
    config: Path, output: Path, *, headless: bool = True, recording: bool = True, recording_fps: int = 10,
    record_chat: bool = True,
) -> dict:
    if type(record_chat) is not bool:
        raise ValueError("record_chat must be a boolean")
    if type(recording_fps) is not int or not 1 <= recording_fps <= 60:
        raise ValueError("recording_fps must be an integer in [1, 60]")
    output = output.resolve()
    launch_id = uuid4().hex
    launch_root = output / "runs" / launch_id
    launch_root.mkdir(parents=True)
    rows: list[dict] = []
    summary: dict = {"status": "validating", "groups": [], "episodes": rows}
    admitted = False
    def save_summary() -> None:
        write_json(launch_root / "summary.json", summary)
        write_json(output / "summary.json", summary)

    summary["launch_id"] = launch_id
    save_summary()
    try:
        experiment = load_experiment(config)
        summary["experiment_id"] = experiment.id
        write_json(output / "config.json", experiment.resolved())
        write_json(launch_root / "config.json", experiment.resolved())
        validate_experiment(experiment)
        admitted = True
        source = provenance()
        write_json(output / "provenance.json", source)
        write_json(launch_root / "provenance.json", source)
        launch = {
            "headless": headless, "recording": recording, "recording_fps": recording_fps,
            "record_chat": record_chat,
            "config": str(config.resolve()), "output": str(output),
        }
        write_json(output / "launch.json", launch)
        write_json(launch_root / "launch.json", launch)
        for agent_config in experiment.agents:
            for task in experiment.tasks:
                for repetition in range(1, experiment.repetitions + 1):
                    episode_id = (
                        f"{agent_config.id}.{task.game}.{task.id}.{task.task_type}.{repetition:04d}"
                    )
                    episode_path = Path(agent_config.id) / f"{task.id}.{task.task_type}" / f"episode_{repetition}"
                    task_settings = task.resolved()
                    task_settings.pop("source")
                    configuration = {
                        "task": task_settings, "agent": agent_config.resolved(),
                        "headless": headless, "recording": recording, "recording_fps": recording_fps,
                        "record_chat": record_chat,
                    }
                    fingerprint = hashlib.sha256(
                        json.dumps(configuration, sort_keys=True, allow_nan=False).encode()
                    ).hexdigest()
                    rows.append({
                        "episode_id": episode_id, "agent_id": agent_config.id, "agent": agent_config.resolved(),
                        "output_path": episode_path.as_posix(),
                        "configuration_sha256": fingerprint, "launch_id": launch_id,
                        "game": task.game, "task_id": task.id, "task_type": task.task_type,
                        "repetition": repetition, "status": "not_run", "measurement": "unavailable",
                        "task_outcome": "unknown",
                    })
        for row in rows:
            if prepare_episode(output, row):
                continue
            agent_config = next(agent for agent in experiment.agents if agent.id == row["agent_id"])
            task = next(task for task in experiment.tasks
                        if task.id == row["task_id"] and task.task_type == row["task_type"])
            print(f"Running {row['episode_id']}", flush=True)
            row["status"] = "running"
            summary = {"launch_id": launch_id, "experiment_id": experiment.id, "status": "running", **summarize(rows)}
            save_summary()
            await run_episode(agent_config, task, output / row["output_path"], row,
                              headless=headless, recording=recording, recording_fps=recording_fps,
                              record_chat=record_chat)
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
        save_summary()
    return summary
