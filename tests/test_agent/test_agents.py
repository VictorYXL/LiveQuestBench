"""Real-time Minecraft runs for three Agents using a live model, with a three-minute budget."""

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

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.llm_client.base_client import Message, RequestEvent
from agent_framework.agents.tool_calling_agent import ToolCallingAgent
from agent_framework.utils.tools import Observation, Tool
from agent_framework.agents.deepseek_harness import DeepSeekHarnessAgent
from agent_framework.agents.hermes import HermesAgent
from agent_framework.agents.process_agent import IntegrationIncompatible, IntegrationUnavailable, ProcessAgent


InterfaceT = TypeVar("InterfaceT")
NATIVE_AGENTS = {"deepseek": DeepSeekHarnessAgent, "hermes": HermesAgent}


async def run_bounded(
    agent: BaseAgent[InterfaceT], public: AgentContext[InterfaceT],
    end_game: Callable[[], Awaitable[None]],
) -> tuple[AgentExit, bool]:
    running = asyncio.create_task(agent.run(public))
    timed_out = False
    try:
        done, _ = await asyncio.wait(
            {running}, timeout=max(0, (public.deadline_at_ns - time.monotonic_ns()) / 1e9),
        )
        timed_out = not done
    finally:
        try:
            await end_game()
        finally:
            if not running.done():
                await agent.stop(StopReason.DEADLINE if timed_out else StopReason.INFRASTRUCTURE_ERROR)
            outcomes = await asyncio.wait_for(asyncio.gather(running, return_exceptions=True), timeout=10)
    outcome = outcomes[0]
    if isinstance(outcome, asyncio.CancelledError) and timed_out:
        return AgentExit(AgentExitReason.STOPPED, native_reason="deadline_game_gate_cancelled_tool"), True
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome, timed_out


@pytest.mark.live
@pytest.mark.game
@pytest.mark.parametrize("agent_name", ["tool_calling", "deepseek", "hermes"])
@pytest.mark.parametrize("track", ["visual_motor", "structured_tool"])
def test_minecraft_collect_three_logs(
    track: str, agent_name: str, headless: bool, recording: bool,
) -> None:
    if os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1" or os.environ.get("LIVEQUEST_LIVE_COPILOT") != "1":
        pytest.skip("Set LIVEQUEST_MINECRAFT_TEST=1 and LIVEQUEST_LIVE_COPILOT=1 for game/model runs")
    pytest.importorskip("nbtlib")
    pytest.importorskip("PIL")
    pytest.importorskip("Xlib")
    from agent_framework.llm_client.github_copilot_client import GitHubCopilotClient
    from game.minecraft.structured_tools import interface as st_api
    from game.minecraft.visual_motor import interface as vm_api
    from game.minecraft.evaluators.inventory import evaluate_inventory
    from game.minecraft.game import MinecraftGame
    from game.minecraft.init_player_state import PlayerState

    root = Path(os.environ.get("MINECRAFT_TEST_OUTPUT", str(Path(__file__).resolve().parents[2] / "output/test")))
    output = root.resolve() / f"{agent_name}-{track}-{uuid4().hex}"
    if agent_name != "tool_calling":
        try:
            NATIVE_AGENTS[agent_name].source_root()
        except IntegrationUnavailable as error:
            pytest.skip(str(error))
    token_file = os.environ.get("LIVEQUEST_COPILOT_TOKEN_FILE")
    if not os.environ.get("COPILOT_GITHUB_TOKEN") and not token_file:
        pytest.fail("Set COPILOT_GITHUB_TOKEN or LIVEQUEST_COPILOT_TOKEN_FILE; credentials are not auto-discovered")
    events: list[RequestEvent] = []
    report: dict[str, object] = {
        "status": "execution_error", "track": track, "agent": agent_name,
        "provider": "github_copilot", "model": "gpt-6-astra",
        "reasoning_effort": "low", "max_output_tokens": 4096, "max_attempts": 1,
        "budget_seconds": 180, "recording": recording, "headless": headless,
        "fixture": "three-oak-logs-v1",
        "upstream": NATIVE_AGENTS[agent_name].source if agent_name in NATIVE_AGENTS else None,
        "fixture_commands": ["fill 0 72 -2 0 74 -2 minecraft:oak_log"],
        "task": "Collect at least 3 oak logs in your inventory. Keep them as logs, not planks. "
                "Do not drop them. Finish with a text answer when you believe the task is complete.",
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
        with (output / "messages.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at_ns": time.monotonic_ns(), **entry}) + "\n")

    async def scenario() -> None:
        client = GitHubCopilotClient(
            "gpt-6-astra", token_file=Path(token_file) if token_file else None,
            reasoning_effort="low", max_output_tokens=4096, timeout=180, on_request=events.append,
        )
        game = MinecraftGame(
            track=track, output_dir=output, headless=headless, recording=recording,
            difficulty="peaceful", player_state=PlayerState(position=(0.5, 72, 0.5), yaw=180),
        )
        def build_agent(
            tools: Sequence[Tool[InterfaceT]],
            observe: Callable[[InterfaceT], Awaitable[Observation]],
        ) -> ToolCallingAgent[InterfaceT] | ProcessAgent[InterfaceT]:
            return (
                ToolCallingAgent(client, tools=tools, observe=observe, on_message=record)
                if agent_name == "tool_calling" else NATIVE_AGENTS[agent_name](
                    client, output_dir=output / "external", tools=tools,
                    observe=observe, on_message=record, model="gpt-6-astra",
                    reasoning_effort="low", max_output_tokens=4096,
                )
            )
        agent = (build_agent(vm_api.agent_tools(), vm_api.agent_observation)
                 if track == "visual_motor" else build_agent(st_api.agent_tools(), st_api.agent_observation))
        try:
            instructions = game.get_instructions()
            report["game_instructions"] = instructions
            models = await client.list_models()
            metadata = next((model for model in models if model.get("id") == "gpt-6-astra"), None)
            if metadata is None:
                raise RuntimeError("gpt-6-astra is unavailable; no replacement model is permitted")
            report["model_metadata"] = metadata
            await game.start()
            # Private fixture setup happens before the initial evidence boundary.
            assert game._session is not None and game._session.server is not None
            feedback = await game._session.server.command("fill 0 72 -2 0 74 -2 minecraft:oak_log")
            if not any("Successfully filled 3" in line for line in feedback):
                raise RuntimeError("Could not verify the three-log fixture")
            before = await game.save_snapshot(output / "before")
            interface = game.get_agent_interface()
            started = time.monotonic_ns()
            deadline = started + 180_000_000_000
            await game.begin()
            public = AgentContext(
                output.name, str(report["task"]), interface, started, deadline,
                instructions,
            )
            outcome, timed_out = await run_bounded(agent, public, game.end)
            after = await game.save_snapshot(output / "after")
            report["elapsed_to_gate_seconds"] = (game._boundary["end_requested_at_ns"] - started) / 1e9
            report["deadline_reached"] = timed_out
            report["agent_exit"] = asdict(outcome)
            assert game.player_uuid is not None
            score = evaluate_inventory(before, after, game.player_uuid, [
                {"item": "oak_log", "min_count": 3, "min_delta": 3},
            ])
            report["score"] = score
            report["response_models"] = sorted({
                str(message.provider_data["response_model"]) for message in agent.messages
                if message.role == "assistant" and "response_model" in message.provider_data
            })
            assert score["inventory_before"] == {}, "This fixture must start with an empty inventory"
        finally:
            try:
                await agent.close()
            finally:
                try:
                    await game.close()
                finally:
                    await client.close()
            if isinstance(agent, ProcessAgent):
                report["integration_admitted"] = agent.admitted
                report["forced_worker_termination"] = agent.forced_termination
                report["worker_returncode"] = agent._process.returncode if agent._process else None
        if recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )
        report["status"] = "task_success" if score["success"] else "task_failure"
        assert score["success"], f"Agent did not collect three logs: {score['checks']}; artifacts: {output}"

    print(f"{agent_name} artifacts: {output}")
    try:
        asyncio.run(scenario())
    except IntegrationIncompatible as error:
        report["status"] = "integration_incompatible"
        report["reason"] = str(error)
        pytest.skip(f"Native integration rejected (not a task failure): {error}")
    except BaseException as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        output.mkdir(parents=True, exist_ok=True)
        report["attempts"] = [asdict(event) for event in events]
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
