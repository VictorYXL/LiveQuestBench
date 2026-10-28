"""Real model/native Veloren acceptance, independent of small-task success."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import time
from typing import TypeVar
from uuid import uuid4

import pytest

from agent_framework.agents.base_agent import AgentContext, AgentExitReason, StopReason
from agent_framework.agents.process_agent import IntegrationUnavailable, ProcessAgent
from agent_framework.agents.tool_calling_agent import ToolCallingAgent
from agent_framework.llm_client.base_client import Message, RequestEvent
from agent_framework.utils.tools import Observation, Tool
from game.base_game import AgentAccessClosed
from tests.test_agent.support import NATIVE_AGENTS, run_bounded


InterfaceT = TypeVar("InterfaceT")


@pytest.mark.live
@pytest.mark.game
@pytest.mark.parametrize("agent_name,track,interrupt", [
    pytest.param(name, track, False, id=f"{name}-{track}")
    for name in ["tool_calling", *NATIVE_AGENTS]
    for track in ("visual_motor", "structured_tool")
] + [
    pytest.param(name, "structured_tool", True, id=f"{name}-stop-structured_tool")
    for name in ("deepseek_harness", "gamingagent")
])
def test_veloren_move_and_stop(
    agent_name: str, track: str, interrupt: bool, headless: bool, recording: bool, veloren_fixture: dict,
) -> None:
    if os.environ.get("LIVEQUEST_VELOREN_TEST") != "1" or os.environ.get("LIVEQUEST_LIVE_COPILOT") != "1":
        pytest.skip("Set LIVEQUEST_VELOREN_TEST=1 and LIVEQUEST_LIVE_COPILOT=1")
    pytest.importorskip("PIL")
    pytest.importorskip("Xlib")
    from agent_framework.llm_client.github_copilot_client import GitHubCopilotClient
    from game.veloren.game import VelorenGame
    from game.veloren.evaluators.endpoints import evaluate_displacement
    from game.veloren.structured_tools import interface as st_api
    from game.veloren.visual_motor import interface as vm_api

    if agent_name in NATIVE_AGENTS:
        try:
            NATIVE_AGENTS[agent_name].source_root()
        except IntegrationUnavailable as error:
            pytest.skip(str(error))
    token_file = os.environ.get("LIVEQUEST_COPILOT_TOKEN_FILE")
    if not os.environ.get("COPILOT_GITHUB_TOKEN") and not token_file:
        pytest.fail("Configure COPILOT_GITHUB_TOKEN or LIVEQUEST_COPILOT_TOKEN_FILE explicitly")
    root = Path(__file__).resolve().parents[2] / "output/test"
    output = root / f"veloren-{agent_name}-{track}-{uuid4().hex}"
    events: list[RequestEvent] = []
    interactions: list[dict[str, object]] = []
    report = {
        "status": "execution_error", "integration_status": "not_verified",
        "agent": agent_name, "track": track, "provider": "github_copilot", "model": "gpt-6-astra",
        "reasoning_effort": "low", "max_output_tokens": 4096, "max_attempts": 1, "budget_seconds": 180,
        "fixture": "veloren-movement-platform", "headless": headless, "recording": recording,
        "interrupt_after_first_game_tool": interrupt,
        "upstream": NATIVE_AGENTS[agent_name].source if agent_name in NATIVE_AGENTS else None,
        "task": "Move at least 2 horizontal metres away from your starting position while staying alive, "
                "then release movement controls and finish with a text answer. "
                "You start on a small elevated stone platform. Use a short movement burst, not a long walk.",
    }
    image_count = 0

    def record(message: Message) -> None:
        nonlocal image_count
        entry = asdict(message)
        if isinstance(message.content, list):
            blocks = []
            for block in message.content:
                if block.get("type") == "image":
                    data = block["data"]
                    assert isinstance(data, bytes)
                    name = f"observation-{image_count:04d}.png"
                    (output / name).write_bytes(data)
                    blocks.append({key: value for key, value in block.items() if key != "data"} | {"path": name})
                    image_count += 1
                else:
                    blocks.append(block)
            entry["content"] = blocks
        with (output / "messages.jsonl").open("a") as stream:
            stream.write(json.dumps({"at_ns": time.monotonic_ns(), **entry}) + "\n")

    async def scenario() -> None:
        first_tool = asyncio.Event()
        client = GitHubCopilotClient(
            "gpt-6-astra", token_file=Path(token_file) if token_file else None, reasoning_effort="low",
            max_output_tokens=4096, timeout=180, on_request=events.append,
        )
        game = VelorenGame(output_dir=output, fixture=veloren_fixture, track=track, headless=headless, recording=recording)

        def build_agent(tools: Sequence[Tool[InterfaceT]], observe: Callable[[InterfaceT], Awaitable[Observation]]):
            tracked = []
            for tool in tools:
                async def execute(interface: InterfaceT, arguments: dict[str, object], original=tool) -> str:
                    result = await original.execute(interface, arguments)
                    interactions.append({"name": original.name, "arguments": arguments, "result": result,
                                         "completed_at_ns": time.monotonic_ns()})
                    first_tool.set()
                    return result
                tracked.append(Tool(tool.name, tool.description, tool.parameters, execute))
            return (ToolCallingAgent(client, tools=tracked, observe=observe, on_message=record)
                    if agent_name == "tool_calling" else NATIVE_AGENTS[agent_name](
                        client, output_dir=output / "external", tools=tracked, observe=observe,
                        on_message=record, model="gpt-6-astra", reasoning_effort="low", max_output_tokens=4096,
                    ))

        agent = (build_agent(vm_api.agent_tools(), vm_api.agent_observation) if track == "visual_motor"
                 else build_agent(st_api.agent_tools(), st_api.agent_observation))
        try:
            metadata = next((model for model in await client.list_models() if model.get("id") == "gpt-6-astra"), None)
            assert metadata is not None, "Required model is unavailable; substitution is not permitted"
            report["model_metadata"] = metadata
            await game.start()
            before = await game.save_snapshot(output / "before")
            interface = game.get_agent_interface()
            await game.begin()
            started = time.monotonic_ns()
            public = AgentContext(output.name, report["task"], interface, started, started + 180_000_000_000,
                                  game.get_instructions())
            outcome, timed_out = await run_bounded(agent, public, game.end, first_tool if interrupt else None)
            with pytest.raises(AgentAccessClosed):
                await interface.observe()
            after = await game.save_snapshot(output / "after")
            score = evaluate_displacement(before, after, min_distance=2)
            first = json.loads((before / "observation.json").read_text())
            last = json.loads((after / "observation.json").read_text())
            response_models = sorted({str(message.provider_data["response_model"]) for message in agent.messages
                                      if message.role == "assistant" and "response_model" in message.provider_data})
            report.update(score=score, agent_exit=asdict(outcome), deadline_reached=timed_out,
                          response_models=response_models, client_updates_advanced=last["tick"] - first["tick"],
                          elapsed_to_gate_seconds=(game._boundary["end_requested_at_ns"] - started) / 1e9)
            assert response_models == ["gpt-6-astra"]
            assert last["tick"] > first["tick"], "Native world did not advance"
            assert interactions and any(message.role == "tool" for message in agent.messages), "No game tool round trip"
            if track == "visual_motor":
                assert image_count > 0, "No actual images reached the underlying model"
            if interrupt:
                assert isinstance(agent, ProcessAgent) and not timed_out
                assert agent.stop_reason == StopReason.OPERATOR_CANCEL and outcome.reason == AgentExitReason.STOPPED
        finally:
            try:
                await agent.close()
            finally:
                try:
                    await game.close()
                finally:
                    await client.close()
            if isinstance(agent, ProcessAgent):
                report.update(integration_admitted=agent.admitted, forced_worker_termination=agent.forced_termination,
                              worker_returncode=agent._process.returncode if agent._process else None)
        if isinstance(agent, ProcessAgent):
            assert agent.admitted and not agent.forced_termination
            assert agent._process is not None and agent._process.returncode == 0
        assert game._session is not None and game._session.process is not None
        assert game._session.process.returncode == 0
        if recording:
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                            "-map", "0:v:0", "-f", "null", "-"], check=True, capture_output=True, timeout=30)
        report.update(status="task_success" if score["success"] else "task_failure", integration_status="passed")

    print(f"Veloren {agent_name} artifacts: {output}")
    try:
        asyncio.run(scenario())
    except BaseException as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        output.mkdir(parents=True, exist_ok=True)
        report.update(attempts=[asdict(event) for event in events], game_interactions=interactions)
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
