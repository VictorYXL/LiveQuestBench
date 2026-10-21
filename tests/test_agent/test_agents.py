"""Offline loop checks and opt-in, three-minute Minecraft wood-collection runs."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import TypeVar
from uuid import uuid4

import pytest

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.llm_client.base_client import BaseLLMClient, LLMResponse, Message, RequestEvent
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


class ScriptedClient(BaseLLMClient):
    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__()
        self.responses = iter(responses)
        self.requests: list[list[Message]] = []
        self.closed = False

    async def _request_impl(
        self, messages: Sequence[Message], *, tools: Sequence[dict[str, object]] | None,
        tool_choice: str | None,
    ) -> LLMResponse:
        self.requests.append(deepcopy(list(messages)))
        assert tools and tool_choice == "auto"
        return next(self.responses)

    async def close(self) -> None:
        self.closed = True


def context(interface: list[str]) -> AgentContext[list[str]]:
    start = time.monotonic_ns()
    return AgentContext("offline", "Collect three logs", interface, start, start + 180_000_000_000,
                        "Public game instructions")


async def observe(interface: list[str]) -> Observation:
    return [{"type": "text", "text": json.dumps(interface)},
            {"type": "image", "data": b"test-image", "mime_type": "image/png"}]


async def execute(interface: list[str], arguments: dict[str, object]) -> str:
    interface.append(str(arguments["value"]))
    return json.dumps({"accepted": arguments["value"]})


def make_tool() -> Tool[list[str]]:
    return Tool("act", "Perform an action", {
        "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"],
    }, execute)


def call(call_id: str, value: str = "one") -> dict[str, object]:
    return {"id": call_id, "name": "act", "arguments": {"value": value}}


def test_prompt_files_and_public_task_separation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from game.minecraft.game import MinecraftGame
    from game.minecraft import game as minecraft_module

    PROMPTS = Path(minecraft_module.__file__).parent / "prompts"
    assert {path.name for path in PROMPTS.iterdir()} == {
        "introduction.txt", "visual_motor.txt", "structured_tool.txt",
    }
    monkeypatch.chdir(tmp_path)
    GAME_INSTRUCTIONS = (PROMPTS / "introduction.txt").read_text(encoding="utf-8").strip()
    VM_INSTRUCTIONS = MinecraftGame(output_dir=tmp_path / "vm").get_instructions()
    ST_INSTRUCTIONS = MinecraftGame(output_dir=tmp_path / "st", track="structured_tool").get_instructions()
    assert VM_INSTRUCTIONS == GAME_INSTRUCTIONS + "\n" + (PROMPTS / "visual_motor.txt").read_text(encoding="utf-8").strip()
    assert ST_INSTRUCTIONS == GAME_INSTRUCTIONS + "\n" + (PROMPTS / "structured_tool.txt").read_text(encoding="utf-8").strip()
    public_text = "\n".join([GAME_INSTRUCTIONS, VM_INSTRUCTIONS, ST_INSTRUCTIONS]).lower()
    for fixture_hint in ("oak", "collect", "pick up", "pickup", "craft", "0, 72", "three logs",
                         "aim the crosshair", "release inputs before finishing"):
        assert re.search(r"\b" + re.escape(fixture_hint) + r"\b", public_text) is None

    monkeypatch.chdir(tmp_path)

    async def scenario() -> None:
        for task, instructions in (
            ("Collect three logs", VM_INSTRUCTIONS),
            ("Reach the destination", ST_INSTRUCTIONS),
            ("Play another game", "Instructions supplied by a different game."),
            ("No system instructions", ""),
        ):
            client = ScriptedClient([LLMResponse(content="Finished.", finish_reason="stop")])
            agent = ToolCallingAgent(client, tools=[make_tool()], observe=observe)
            try:
                await agent.run(replace(context([]), task=task, game_instructions=instructions))
                systems = [message.content for message in client.requests[0] if message.role == "system"]
                assert systems == ([instructions] if instructions else [])
                assert task in str(next(message.content for message in client.requests[0] if message.role == "user"))
            finally:
                await agent.close()
    asyncio.run(scenario())


def test_observe_tool_loop_and_history() -> None:
    async def scenario() -> None:
        state: list[str] = []
        provider_data = {"opaque": {"reasoning": "provider continuation"}}
        client = ScriptedClient([
            LLMResponse(tool_calls=[call("a"), call("b", "two")], finish_reason="tool_calls",
                        provider_data=provider_data),
            LLMResponse(content="Finished.", finish_reason="stop"),
        ])
        trace: list[Message] = []
        agent = ToolCallingAgent(client, tools=[make_tool()], observe=observe, on_message=trace.append)
        result = await agent.run(context(state))
        assert result.reason is AgentExitReason.RETURNED and result.message == "Finished."
        assert state == ["one", "two"]
        assert [message.role for message in agent.messages] == [
            "system", "user", "assistant", "tool", "tool", "user", "assistant",
        ]
        assert agent.messages[0].content and "Public game instructions" in agent.messages[0].content
        assert "Collect three logs" in str(client.requests[0][1].content)
        assert '["one", "two"]' in str(client.requests[1][-1].content)
        assert [message.tool_call_id for message in agent.messages if message.role == "tool"] == ["a", "b"]
        assert client.requests[1][2].provider_data == provider_data
        for request in client.requests:
            images = [block for message in request if isinstance(message.content, list)
                      for block in message.content if block.get("type") == "image"]
            assert len(images) == 1
        assert sum(block.get("type") == "image" for message in trace if isinstance(message.content, list)
                   for block in message.content) == 2
        with pytest.raises(RuntimeError, match="fresh"):
            await agent.run(context(state))
        await agent.close()
        await agent.close()
        assert not client.closed
        with pytest.raises(ValueError, match="unique"):
            ToolCallingAgent(client, tools=[make_tool(), make_tool()], observe=observe)
    asyncio.run(scenario())


@pytest.mark.parametrize("response,error", [
    (LLMResponse(content="Truncated", finish_reason="length"), RuntimeError),
    (LLMResponse(content="", finish_reason="stop"), RuntimeError),
    (LLMResponse(tool_calls=[call("a"), call("a")], finish_reason="tool_calls"), ValueError),
    (LLMResponse(tool_calls=[{"id": "a", "name": "admin", "arguments": {}}],
                 finish_reason="tool_calls"), ValueError),
])
def test_invalid_response_has_no_tool_effect(response: LLMResponse, error: type[Exception]) -> None:
    async def scenario() -> None:
        state: list[str] = []
        agent = ToolCallingAgent(ScriptedClient([response]), tools=[make_tool()], observe=observe)
        with pytest.raises(error):
            await agent.run(context(state))
        await agent.close()
        assert state == []
    asyncio.run(scenario())


def test_stop_cancellation_and_tool_errors() -> None:
    async def scenario() -> None:
        entered = asyncio.Event()

        async def blocking_observation(interface: list[str]) -> Observation:
            entered.set()
            await asyncio.Event().wait()
            return ""

        client = ScriptedClient([])
        agent = ToolCallingAgent(client, tools=[make_tool()], observe=blocking_observation)
        running = asyncio.create_task(agent.run(context([])))
        await entered.wait()
        await agent.stop(StopReason.DEADLINE)
        await agent.stop(StopReason.OPERATOR_CANCEL)
        assert (await running).reason is AgentExitReason.STOPPED
        assert agent.stop_reason is StopReason.DEADLINE
        await agent.close()
        assert not client.closed

        entered.clear()
        cancelled = ToolCallingAgent(client, tools=[make_tool()], observe=blocking_observation)
        running = asyncio.create_task(cancelled.run(context([])))
        await entered.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        await cancelled.close()

        async def fail(interface: list[str], arguments: dict[str, object]) -> str:
            raise OSError("tool connection lost")

        failing = ToolCallingAgent(
            ScriptedClient([LLMResponse(tool_calls=[call("a")], finish_reason="tool_calls")]),
            tools=[Tool("act", "Failure test", {}, fail)], observe=observe,
        )
        with pytest.raises(OSError, match="connection lost"):
            await failing.run(context([]))
        await failing.close()
    asyncio.run(asyncio.wait_for(scenario(), timeout=2))


def test_deadline_gates_game_before_stopping_agent() -> None:
    async def scenario() -> None:
        async def blocked(interface: list[str]) -> Observation:
            await asyncio.Event().wait()
            return ""

        agent = ToolCallingAgent(ScriptedClient([]), tools=[make_tool()], observe=blocked)
        gates: list[int] = []

        async def end_game() -> None:
            assert agent.stop_reason is None
            gates.append(time.monotonic_ns())

        started = time.monotonic_ns()
        public = AgentContext("deadline", "Task", [], started, started + 20_000_000)
        result, timed_out = await run_bounded(agent, public, end_game)
        assert timed_out and result.reason is AgentExitReason.STOPPED
        assert agent.stop_reason is StopReason.DEADLINE
        assert len(gates) == 1 and gates[0] >= public.deadline_at_ns
        await agent.close()
    asyncio.run(asyncio.wait_for(scenario(), timeout=2))


def test_minecraft_bindings_preserve_permissions() -> None:
    pytest.importorskip("PIL")
    pytest.importorskip("Xlib")
    from PIL import Image
    from game.minecraft.structured_tools import interface as st_api
    from game.minecraft.visual_motor import interface as vm_api
    from game.minecraft.structured_tools.interface import StructuredInterface, tool_schemas
    from game.minecraft.visual_motor.capture import CapturedFrame
    from game.minecraft.visual_motor.interface import MotorInterface, action_tool_schema

    async def scenario() -> None:
        state = {"inventory": [], "nearby_blocks": {
            "format": "palette_cube", "minp": {"x": 0, "y": 0, "z": 0},
            "dims": {"x": 2, "y": 2, "z": 2}, "palette": ["air", "oak_log"],
            "data": [0, 0, 1, 1, 1, 0, 0, 0],
        }}

        async def observe_st() -> dict:
            return state

        names: list[str] = []

        async def st_call(name: str, arguments: dict) -> dict:
            names.append(name)
            return {"success": False, "message": "ordinary refusal"}

        st = StructuredInterface(observe_st, st_call, tool_schemas)
        encoded = await st_api.agent_observation(st)
        assert isinstance(encoded, str)
        cube = json.loads(encoded)["nearby_blocks"]
        assert [value for value, count in cube["data_rle"] for _ in range(count)] == state["nearby_blocks"]["data"]
        assert state["nearby_blocks"]["format"] == "palette_cube"
        tools = st_api.agent_tools()
        assert {tool.name for tool in tools} == {s["name"] for s in tool_schemas()} - {"GetObservationTool"}
        for tool in tools:
            assert tool.schema() == next(schema for schema in tool_schemas() if schema["name"] == tool.name)
            assert json.loads(await tool.execute(st, {}))["success"] is False
        assert names == [tool.name for tool in tools]

        async def observe_vm() -> CapturedFrame:
            return CapturedFrame(1, 42, 10, 20, Image.new("RGB", (2, 2)))

        submitted: list[dict[str, object]] = []

        async def act_vm(commands: list[dict[str, object]]) -> list:
            submitted.extend(commands)
            return []

        vm = MotorInterface(observe_vm, act_vm)
        observed = await vm_api.agent_observation(vm)
        assert isinstance(observed, list)
        assert [block["type"] for block in observed] == ["text", "image"]
        assert "inventory" not in str(observed)
        action, = vm_api.agent_tools()
        assert action.schema() == action_tool_schema()
        commands = [{"name": "wait", "arguments": {"milliseconds": 10}}]
        await action.execute(vm, {"commands": commands})
        assert submitted == commands
        with pytest.raises(ValueError):
            await action.execute(vm, {"commands": [], "admin": "give"})
    asyncio.run(scenario())


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


@pytest.mark.parametrize("agent_name", ["deepseek", "hermes"])
def test_external_missing_checkout(agent_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    variable = NATIVE_AGENTS[agent_name].source["environment"]
    monkeypatch.delenv(variable, raising=False)
    with pytest.raises(IntegrationUnavailable, match="prepared pinned checkout"):
        NATIVE_AGENTS[agent_name].source_root()
    monkeypatch.setenv(variable, str(tmp_path / "missing"))
    with pytest.raises(IntegrationUnavailable, match="does not exist"):
        NATIVE_AGENTS[agent_name].source_root()


@pytest.mark.external
@pytest.mark.parametrize("agent_name", ["deepseek", "hermes"])
def test_native_external_roundtrip(agent_name: str, tmp_path: Path) -> None:
    if os.environ.get("LIVEQUEST_EXTERNAL_TEST") != "1":
        pytest.skip("Set LIVEQUEST_EXTERNAL_TEST=1 for installed native Agent checks without model/game calls")
    try:
        NATIVE_AGENTS[agent_name].source_root()
    except IntegrationUnavailable as error:
        pytest.skip(str(error))

    async def scenario() -> None:
        state: list[str] = []
        client = ScriptedClient([
            LLMResponse(tool_calls=[call("native-1")], finish_reason="tool_calls",
                        provider_data={"marker": "native-state"}),
            LLMResponse(content="Finished.", finish_reason="stop"),
        ])
        agent = NATIVE_AGENTS[agent_name](
            client, output_dir=tmp_path / agent_name, tools=[make_tool()], observe=observe,
            model="gpt-6-astra", reasoning_effort="low", max_output_tokens=4096,
        )
        try:
            for invalid in (
                {"model": "unapproved-model"},
                {"model": "gpt-6-astra", "max_tokens": 999},
                {"model": "gpt-6-astra", "reasoning_effort": "high"},
                {"model": "gpt-6-astra", "unmapped_option": True},
                {"model": "gpt-6-astra", "stream": True},
                {"model": "gpt-6-astra", "parallel_tool_calls": False},
                {"model": "gpt-6-astra", "tools": []},
            ):
                with pytest.raises(IntegrationIncompatible):
                    await agent._chat(context(state), invalid)
            assert not client.requests and state == []
            result = await asyncio.wait_for(agent.run(context(state)), timeout=30)
            assert result.reason is AgentExitReason.RETURNED
            assert result.message == "Finished."
            assert state == ["one"]
            assert agent.admitted and len(client.requests) == 2
            assert any("Public game instructions" in str(message.content) for message in client.requests[0])
            replay = next(message for message in client.requests[1] if message.tool_calls)
            assert replay.provider_data == {"marker": "native-state"}
            assert next(message for message in agent.messages if message.role == "tool").tool_call_id == "native-1"
        finally:
            await agent.close()
        assert agent._process is not None and agent._process.returncode == 0
        assert not client.closed
    asyncio.run(scenario())


@pytest.mark.external
@pytest.mark.parametrize("agent_name", ["deepseek", "hermes"])
def test_native_external_cancellation(agent_name: str, tmp_path: Path) -> None:
    if os.environ.get("LIVEQUEST_EXTERNAL_TEST") != "1":
        pytest.skip("Set LIVEQUEST_EXTERNAL_TEST=1 for installed native Agent checks")
    try:
        NATIVE_AGENTS[agent_name].source_root()
    except IntegrationUnavailable as error:
        pytest.skip(str(error))

    async def scenario() -> None:
        for cooperative in (True, False):
            entered = asyncio.Event()

            class WaitingClient(ScriptedClient):
                async def _request_impl(
                    self, messages: Sequence[Message], *, tools: Sequence[dict[str, object]] | None,
                    tool_choice: str | None,
                ) -> LLMResponse:
                    entered.set()
                    await asyncio.Event().wait()
                    raise AssertionError("Blocked model request must be cancelled")

            client = WaitingClient([])
            state: list[str] = []
            agent = NATIVE_AGENTS[agent_name](
                client, output_dir=tmp_path / f"{agent_name}-{cooperative}",
                tools=[make_tool()], observe=observe, model="gpt-6-astra",
                reasoning_effort="low", max_output_tokens=4096,
            )
            running = asyncio.create_task(agent.run(context(state)))
            try:
                await asyncio.wait_for(entered.wait(), timeout=30)
                assert agent.admitted
                if cooperative:
                    await agent.stop(StopReason.DEADLINE)
                    result = await asyncio.wait_for(running, timeout=10)
                    assert result.reason is AgentExitReason.STOPPED
                    assert result.native_reason == "deadline"
                else:
                    running.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await asyncio.wait_for(running, timeout=10)
                assert state == []
                assert agent._process is not None and agent._process.returncode is not None
                assert not client.closed
            finally:
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
                await agent.close()
                await agent.close()
    asyncio.run(scenario())
