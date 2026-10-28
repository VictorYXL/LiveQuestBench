"""Real Minecraft/model acceptance, independent of three-log task success."""

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
from agent_framework.llm_client.base_client import Message, RequestEvent
from agent_framework.agents.tool_calling_agent import ToolCallingAgent
from agent_framework.utils.tools import Observation, Tool
from agent_framework.agents.process_agent import IntegrationIncompatible, IntegrationUnavailable, ProcessAgent
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
    for name in ("deepseek_harness", "orak", "smolagents", "gamingagent")
])
def test_minecraft_collect_three_logs(
    track: str, agent_name: str, interrupt: bool, headless: bool, recording: bool,
) -> None:
    if os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1" or os.environ.get("LIVEQUEST_LIVE_COPILOT") != "1":
        pytest.skip("Set LIVEQUEST_MINECRAFT_TEST=1 and LIVEQUEST_LIVE_COPILOT=1 for game/model runs")
    nbtlib = pytest.importorskip("nbtlib")
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
    interactions: list[dict[str, object]] = []
    report: dict[str, object] = {
        "status": "execution_error", "track": track, "agent": agent_name,
        "provider": "github_copilot", "model": "gpt-6-astra",
        "reasoning_effort": "low", "max_output_tokens": 4096, "max_attempts": 1,
        "budget_seconds": 180, "recording": recording, "headless": headless,
        "fixture": "island",
        "interrupt_after_first_game_tool": interrupt,
        "integration_status": "not_verified",
        "upstream": NATIVE_AGENTS[agent_name].source if agent_name in NATIVE_AGENTS else None,
        "world_path": str(Path(__file__).resolve().parents[2] / "output/back/legacy-config-20261026/config/minecraft/fixtures/island"),
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
        first_tool = asyncio.Event()
        client = GitHubCopilotClient(
            "gpt-6-astra", token_file=Path(token_file) if token_file else None,
            reasoning_effort="low", max_output_tokens=4096, timeout=180, on_request=events.append,
        )
        game = MinecraftGame(
            track=track, output_dir=output, headless=headless, recording=recording,
            world_path=Path(str(report["world_path"])),
            difficulty="peaceful", player_state=PlayerState(position=(0.5, 72, 0.5), yaw=180),
        )
        def build_agent(
            tools: Sequence[Tool[InterfaceT]],
            observe: Callable[[InterfaceT], Awaitable[Observation]],
        ) -> ToolCallingAgent[InterfaceT] | ProcessAgent[InterfaceT]:
            tracked_tools = []
            for tool in tools:
                async def execute(
                    interface: InterfaceT, arguments: dict[str, object], original: Tool[InterfaceT] = tool,
                ) -> str:
                    result = await original.execute(interface, arguments)
                    interactions.append({"name": original.name, "arguments": arguments,
                                         "result": result, "completed_at_ns": time.monotonic_ns()})
                    first_tool.set()
                    return result
                tracked_tools.append(Tool(tool.name, tool.description, tool.parameters, execute))
            return (
                ToolCallingAgent(client, tools=tracked_tools, observe=observe, on_message=record)
                if agent_name == "tool_calling" else NATIVE_AGENTS[agent_name](
                    client, output_dir=output / "external", tools=tracked_tools,
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
            before = await game.save_snapshot(output / "before")
            from game.minecraft.evaluators.world import read_blocks
            assert set(read_blocks(before, (0, 72, -2), (0, 74, -2), "minecraft:overworld").values()) == {"minecraft:oak_log"}
            interface = game.get_agent_interface()
            started = time.monotonic_ns()
            deadline = started + 180_000_000_000
            await game.begin()
            public = AgentContext(
                output.name, str(report["task"]), interface, started, deadline,
                instructions,
            )
            outcome, timed_out = await run_bounded(agent, public, game.end, first_tool if interrupt else None)
            with pytest.raises(AgentAccessClosed):
                await interface.observe()
            after = await game.save_snapshot(output / "after")
            report["elapsed_to_gate_seconds"] = (game._boundary["end_requested_at_ns"] - started) / 1e9
            report["deadline_reached"] = timed_out
            report["agent_exit"] = asdict(outcome)
            assert game.player_uuid is not None
            score = evaluate_inventory(before, after, game.player_uuid, [
                {"item": "oak_log", "min_count": 3},
            ])
            report["score"] = score
            report["response_models"] = sorted({
                str(message.provider_data["response_model"]) for message in agent.messages
                if message.role == "assistant" and "response_model" in message.provider_data
            })
            ticks = int(nbtlib.load(after / "level.dat")["Data"]["Time"]) - int(nbtlib.load(before / "level.dat")["Data"]["Time"])
            report["world_ticks_advanced"] = ticks
            assert score["inventory_before"] == {}, "This fixture must start with an empty inventory"
            assert ticks > 0, "The game world did not advance"
            assert report["response_models"] == ["gpt-6-astra"], "Missing or unexpected underlying model"
            assert interactions, "No real game tool round trip; integration is not established"
            assert any(message.role == "tool" for message in agent.messages), "No tool-result telemetry"
            if agent_name == "gamingagent":
                native = output / "external/native"
                reasoning = json.loads((native / "reasoning_module.json").read_text())
                memory = json.loads((native / "memory_module.json").read_text())
                assert reasoning and all(entry["reflection"] for entry in reasoning)
                assert any("###Action" in entry for entry in memory)
                if track == "visual_motor":
                    assert all(entry["processed_visual_description"] for entry in reasoning)
                report["native_harness"] = {
                    "reasoning_steps": len(reasoning), "memory_entries": len(memory),
                    "reflection_verified": True, "visual_perception_verified": track == "visual_motor",
                }
            if interrupt:
                assert isinstance(agent, ProcessAgent)
                assert not timed_out and agent.stop_reason == StopReason.OPERATOR_CANCEL
                assert outcome.reason == AgentExitReason.STOPPED
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
        if isinstance(agent, ProcessAgent):
            assert agent.admitted, "Native tool set was not admitted"
            assert not agent.forced_termination, "Native worker required forced termination"
            assert agent._process is not None and agent._process.returncode is not None, "Native worker leaked"
            if agent_name == "deepseek_harness":
                assert agent._process.returncode == 0, "DeepSeek worker must exit cleanly, including benchmark stop"
        if recording:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-i", str(output / "video.mp4"),
                 "-map", "0:v:0", "-f", "null", "-"],
                check=True, capture_output=True, timeout=30,
            )
        report["status"] = "task_success" if score["success"] else "task_failure"
        report["integration_status"] = "passed"

    print(f"{agent_name} artifacts: {output}")
    try:
        asyncio.run(scenario())
    except IntegrationIncompatible as error:
        report["status"] = "integration_incompatible"
        report["reason"] = str(error)
        raise
    except BaseException as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        output.mkdir(parents=True, exist_ok=True)
        report["attempts"] = [asdict(event) for event in events]
        report["game_interactions"] = interactions
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
