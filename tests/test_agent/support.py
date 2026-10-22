"""Shared real-game Agent admission and benchmark-owned stop behavior."""

import asyncio
from collections.abc import Awaitable, Callable
import time
from typing import TypeVar

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.agents.deepseek_harness import DeepSeekHarnessAgent
from agent_framework.agents.hermes import HermesAgent
from agent_framework.agents.orak import OrakAgent
from agent_framework.agents.smolagents import SmolagentsAgent
from agent_framework.agents.gamingagent import GamingAgent
from game.base_game import AgentAccessClosed


InterfaceT = TypeVar("InterfaceT")
NATIVE_AGENTS = {
    "deepseek": DeepSeekHarnessAgent, "hermes": HermesAgent, "orak": OrakAgent,
    "smolagents": SmolagentsAgent, "gamingagent": GamingAgent,
}


async def run_bounded(
    agent: BaseAgent[InterfaceT], public: AgentContext[InterfaceT],
    end_game: Callable[[], Awaitable[None]], stop_after_tool: asyncio.Event | None = None,
) -> tuple[AgentExit, bool]:
    running = asyncio.create_task(agent.run(public))
    stop_wait = asyncio.create_task(stop_after_tool.wait()) if stop_after_tool is not None else None
    timed_out = False
    operator_stop = False
    try:
        done, _ = await asyncio.wait(
            {running, stop_wait} if stop_wait is not None else {running},
            timeout=max(0, (public.deadline_at_ns - time.monotonic_ns()) / 1e9),
            return_when=asyncio.FIRST_COMPLETED,
        )
        timed_out = not done
        operator_stop = stop_wait is not None and stop_wait in done
    finally:
        if stop_wait is not None:
            stop_wait.cancel()
            await asyncio.gather(stop_wait, return_exceptions=True)
        try:
            await end_game()
        finally:
            if timed_out or operator_stop or not running.done():
                await agent.stop(StopReason.DEADLINE if timed_out else
                                 StopReason.OPERATOR_CANCEL if operator_stop else StopReason.INFRASTRUCTURE_ERROR)
            outcomes = await asyncio.wait_for(asyncio.gather(running, return_exceptions=True), timeout=10)
    outcome = outcomes[0]
    if isinstance(outcome, asyncio.CancelledError) and (timed_out or operator_stop):
        return AgentExit(AgentExitReason.STOPPED, native_reason="benchmark_game_gate_cancelled_tool"), timed_out
    if isinstance(outcome, AgentAccessClosed) and (timed_out or operator_stop):
        return AgentExit(AgentExitReason.STOPPED, native_reason="benchmark_game_gate_closed"), timed_out
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome, timed_out
