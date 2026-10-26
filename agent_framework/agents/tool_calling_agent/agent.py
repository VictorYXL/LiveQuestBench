"""A minimal native tool-calling loop with injected observation and tool bindings."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from typing import TypeVar

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.llm_client.base_client import BaseLLMClient, ClientError, LLMResponse, Message
from agent_framework.utils.tools import Observation, Tool


InterfaceT = TypeVar("InterfaceT")


class ToolCallingAgent(BaseAgent[InterfaceT]):
    """Observe, ask the model, execute tools in order, and repeat.

    The caller owns the injected client and game resources. There is no planner,
    query Agent, automatic tool retry, or independent task-success detector.
    By default only the latest observation is sent; action history is retained.
    A configured observation window retains recent public inputs without summarization.
    Full messages remain available for inspection and on_message recording.
    The runner must gate game access at the deadline and on every exit path.
    """

    def __init__(
        self, client: BaseLLMClient, *, tools: Sequence[Tool[InterfaceT]],
        observe: Callable[[InterfaceT], Awaitable[Observation]],
        on_message: Callable[[Message], None] | None = None,
        observation_history: int = 1,
    ) -> None:
        if type(observation_history) is not int or observation_history < 1:
            raise ValueError("observation_history must be a positive integer")
        self.observation_history = observation_history
        self.client = client
        self.tools = tuple(tools)
        self._by_name = {tool.name: tool for tool in self.tools}
        if not self.tools or any(not tool.name.strip() for tool in self.tools):
            raise ValueError("Provide at least one named tool")
        if len(self._by_name) != len(self.tools):
            raise ValueError("Tool names must be unique")
        self._observe = observe
        self._on_message = on_message
        self.messages: list[Message] = []
        self._text_observation_offsets: dict[int, int] = {}
        self.stop_reason: StopReason | None = None
        self._task: asyncio.Task[AgentExit] | None = None
        self._used = False
        self._closed = False
        self._call_ids: set[str] = set()

    async def run(self, context: AgentContext[InterfaceT]) -> AgentExit:
        if self._used or self._closed:
            raise RuntimeError("Use a fresh ToolCallingAgent for each attempt")
        self._used = True
        if self.stop_reason is not None:
            return AgentExit(AgentExitReason.STOPPED, native_reason=self.stop_reason.value)
        self._task = asyncio.create_task(self._loop(context))
        try:
            return await self._task
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if self.stop_reason is None or (current is not None and current.cancelling()):
                raise
            return AgentExit(AgentExitReason.STOPPED, native_reason=self.stop_reason.value)

    async def stop(self, reason: StopReason) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def close(self) -> None:
        if self._closed:
            return
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._closed = True

    def _append(self, message: Message) -> None:
        self.messages.append(message)
        if self._on_message is not None:
            self._on_message(message)

    def _request_messages(self) -> list[Message]:
        result: list[Message] = []
        observations = [
            index for index, message in enumerate(self.messages)
            if message.role == "user" and isinstance(message.content, list)
        ]
        retained = set(observations[-self.observation_history:])
        for index, message in enumerate(self.messages):
            content = message.content
            if index not in retained and index < len(self.messages) - 1 and isinstance(content, list):
                if index in self._text_observation_offsets:
                    content = content[:self._text_observation_offsets[index]] + [{
                        "type": "text", "text": "[Earlier observation omitted; latest observation follows.]",
                    }]
                else:
                    content = [
                        {"type": "text", "text": "[Earlier image omitted; latest observation follows.]"}
                        if block.get("type") == "image" else block
                        for block in content
                    ]
                message = replace(message, content=content)
            result.append(message)
        return result

    def _validate_response(self, response: LLMResponse) -> None:
        if response.finish_reason not in ("stop", "tool_calls"):
            raise RuntimeError(f"Incomplete Agent response: {response.finish_reason!r}")
        if response.content is not None and not isinstance(response.content, str):
            raise RuntimeError("Expected text assistant content")
        if not response.tool_calls:
            if response.finish_reason != "stop" or not response.content or not response.content.strip():
                raise RuntimeError("Expected a nonempty final answer or tool calls")
        ids: set[str] = set()
        for call in response.tool_calls:
            call_id, name, arguments = call.get("id"), call.get("name"), call.get("arguments")
            if not isinstance(call_id, str) or not call_id or call_id in ids | self._call_ids:
                raise ValueError("Tool call IDs must be nonempty and unique throughout a run")
            if not isinstance(name, str) or name not in self._by_name:
                raise ValueError(f"Unknown Agent tool: {name!r}")
            if not isinstance(arguments, dict) or any(not isinstance(key, str) for key in arguments):
                raise ValueError(f"Invalid tool arguments: {name}")
            ids.add(call_id)
        self._call_ids.update(ids)

    async def _loop(self, context: AgentContext[InterfaceT]) -> AgentExit:
        if context.game_instructions:
            self._append(Message("system", context.game_instructions))
        first = True
        while True:
            observed = await self._observe(context.interface)
            blocks: list[dict[str, object]] = []
            if first:
                blocks.append({"type": "text", "text": (
                    f"Task: {context.task}\n"
                    f"Wall-clock budget: {(context.deadline_at_ns - context.started_at_ns) / 1e9:g} seconds."
                )})
            if isinstance(observed, str):
                self._text_observation_offsets[len(self.messages)] = len(blocks)
            blocks.append({"type": "text", "text": "Current observation:"})
            blocks.extend([{"type": "text", "text": observed}] if isinstance(observed, str) else observed)
            self._append(Message("user", blocks))
            try:
                response = await self.client.chat(
                    self._request_messages(), tools=[tool.schema() for tool in self.tools],
                    tool_choice="auto",
                )
            except ClientError as error:
                if error.code != "context_length_exceeded":
                    raise
                return AgentExit(
                    AgentExitReason.NATIVE_LIMIT, "Model context capacity exhausted.",
                    native_reason="context_limit_exceeded",
                )
            self._validate_response(response)
            self._append(Message(
                "assistant", response.content, response.tool_calls, provider_data=response.provider_data,
            ))
            if not response.tool_calls:
                assert isinstance(response.content, str)
                return AgentExit(AgentExitReason.RETURNED, response.content, response.finish_reason)
            for call in response.tool_calls:
                name, arguments, call_id = call["name"], call["arguments"], call["id"]
                assert isinstance(name, str) and isinstance(arguments, dict) and isinstance(call_id, str)
                result = await self._by_name[name].execute(context.interface, arguments)
                if not isinstance(result, str):
                    raise TypeError(f"Tool {name!r} must return text")
                self._append(Message("tool", result, tool_call_id=call_id))
            first = False
