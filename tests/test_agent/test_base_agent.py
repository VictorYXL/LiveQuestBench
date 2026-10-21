"""Offline checks for public Agent inputs and the wrapper lifecycle contract."""

import asyncio
from dataclasses import FrozenInstanceError, fields
import inspect

import pytest

from agents.base_agent import (
    AgentContext,
    AgentExit,
    AgentExitReason,
    BaseAgent,
    StopReason,
)


def test_contract_is_abstract_and_public_inputs_are_frozen() -> None:
    assert inspect.isabstract(BaseAgent)
    assert BaseAgent.__abstractmethods__ == {"run", "stop", "close"}
    interface = object()
    context = AgentContext("episode", "Collect logs", interface, 10, 20)
    assert context.interface is interface
    assert context.game_instructions == ""
    assert {field.name for field in fields(context)} == {
        "episode_id", "task", "interface", "started_at_ns",
        "deadline_at_ns", "game_instructions",
    }
    with pytest.raises(FrozenInstanceError):
        setattr(context, "task", "Changed task")
    result = AgentExit(AgentExitReason.NATIVE_LIMIT, native_reason="max_turns")
    assert result.reason.value == "native_limit"
    assert result.native_reason == "max_turns"
    assert {field.name for field in fields(result)} == {"reason", "message", "native_reason"}


@pytest.mark.parametrize(
    "episode_id,task,start,deadline,error",
    [
        (" ", "Task", 10, 20, "episode_id"),
        ("episode", "\n", 10, 20, "task"),
        ("episode", "Task", -1, 20, "deadline_at_ns"),
        ("episode", "Task", 10, 10, "deadline_at_ns"),
        ("episode", "Task", 20, 10, "deadline_at_ns"),
    ],
)
def test_invalid_public_context(
    episode_id: str, task: str, start: int, deadline: int, error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        AgentContext(episode_id, task, object(), start, deadline)


class PublicInterface:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def observe(self) -> str:
        self.calls.append("observe")
        return "visible scene"


class ExampleWrapper(BaseAgent[PublicInterface]):
    def __init__(self, *, fail: bool = False) -> None:
        self.started = asyncio.Event()
        self.retire = asyncio.Event()
        self.stop_reason: StopReason | None = None
        self.fail = fail
        self.closed = False

    async def run(self, context: AgentContext[PublicInterface]) -> AgentExit:
        await context.interface.observe()
        self.started.set()
        if self.fail:
            raise RuntimeError("upstream failure")
        await self.retire.wait()
        return AgentExit(AgentExitReason.STOPPED)

    async def stop(self, reason: StopReason) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
        self.retire.set()

    async def close(self) -> None:
        self.closed = True


def test_wrapper_lifecycle_and_error_propagation() -> None:
    async def scenario() -> None:
        interface = PublicInterface()
        context = AgentContext("episode", "Collect logs", interface, 10, 20)
        wrapper = ExampleWrapper()
        running = asyncio.create_task(wrapper.run(context))
        await wrapper.started.wait()
        await wrapper.stop(StopReason.DEADLINE)
        result = await running
        await wrapper.stop(StopReason.OPERATOR_CANCEL)
        await wrapper.close()
        await wrapper.close()
        assert wrapper.closed
        assert wrapper.stop_reason is StopReason.DEADLINE
        assert result.reason is AgentExitReason.STOPPED
        assert interface.calls == ["observe"]
        assert await interface.observe() == "visible scene"

        failing = ExampleWrapper(fail=True)
        with pytest.raises(RuntimeError, match="upstream failure"):
            await failing.run(context)
        await failing.stop(StopReason.INFRASTRUCTURE_ERROR)
        await failing.close()
        assert failing.closed

    asyncio.run(asyncio.wait_for(scenario(), timeout=2))
