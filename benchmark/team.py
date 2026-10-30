"""Concurrent peer Agents inside one benchmark-owned Episode."""

import asyncio
from dataclasses import asdict
from pathlib import Path

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.agents.process_agent import ProcessAgent
from agent_framework.llm_client.base_client import BaseLLMClient
from benchmark.config import AgentConfig
from benchmark.factory import make_agent, make_client
from benchmark.results import EpisodeLog, write_json
from game.bindings import Controls
from game.team import TeamGame


class TeamAgent(BaseAgent[Controls]):
    def __init__(self, config: AgentConfig, game: TeamGame, root: Path,
                 aggregate: EpisodeLog, *, record_chat: bool):
        self.config, self.game, self.root, self.aggregate = config, game, root, aggregate
        self.record_chat = record_chat
        self.agents: dict[str, BaseAgent[Controls]] = {}
        self.clients: dict[str, BaseLLMClient] = {}
        self.logs: dict[str, EpisodeLog] = {}
        self.results: dict[str, dict] = {}
        self.tasks: list[asyncio.Task[None]] = []
        self.closed = False

    async def run(self, context: AgentContext[Controls]) -> AgentExit:
        from benchmark.runner import RECOVERY_INSTRUCTIONS, logged_controls, run_bounded

        for role in self.game.members:
            output = self.root / "participants" / role
            output.mkdir(parents=True, exist_ok=True)
            log = EpisodeLog(output, record_chat=self.record_chat,
                             storage_profile=self.aggregate.storage_profile)
            self.logs[role] = log
            client = make_client(self.config.model, log.request)
            self.clients[role] = client
            client.on_query = log.query if self.record_chat else None
            public, tools = self.game.controls(role)
            public = logged_controls(public, log)
            agent = make_agent(self.config, client, tools, output / "agent", log.message)
            if isinstance(agent, ProcessAgent) and log.compact is not None:
                agent.on_native_request = log.native_request
            self.agents[role] = agent
            instructions = self.game.instructions(role) + RECOVERY_INSTRUCTIONS + (
                "\nCall final_answer when your participation is finished."
                if self.config.name == "smolagents" else
                "\nReturn a nonempty final response without tool calls when your participation is finished."
            )
            child = AgentContext(
                context.episode_id + "." + role, context.task, public,
                context.started_at_ns, context.deadline_at_ns, instructions,
            )
            self.results[role] = {"role": role, "agent": self.config.resolved(),
                                  "tools": [tool.schema() for tool in tools],
                                  "started_at_ns": context.started_at_ns, "deadline_at_ns": context.deadline_at_ns}
            if isinstance(agent, ProcessAgent):
                self.results[role]["agent_source"] = agent.source

            async def run_member(role=role, agent=agent, child=child):
                async def finish():
                    await self.game.finish(role)
                try:
                    outcome, timed_out = await run_bounded(agent, child, finish)
                    self.results[role].update(agent_exit=asdict(outcome), deadline_reached=timed_out)
                except BaseException as error:
                    self.results[role]["error_type"] = type(error).__name__
                    raise

            self.tasks.append(asyncio.create_task(run_member(), name="participant-" + role))
        done, _ = await asyncio.wait(self.tasks, return_when=asyncio.FIRST_EXCEPTION)
        # Do not cancel other Agents until run_bounded has revoked the shared game gate.
        for task in done:
            task.result()
        return AgentExit(AgentExitReason.COMPLETED, native_reason="all_team_members_finished")

    async def stop(self, reason: StopReason) -> None:
        try:
            outcomes = await asyncio.gather(
                *(agent.stop(reason) for agent in self.agents.values()), return_exceptions=True,
            )
        finally:
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            joined = await asyncio.gather(*self.tasks, return_exceptions=True)
        errors = [error for error in [*outcomes, *joined]
                  if isinstance(error, Exception)]
        if errors:
            raise ExceptionGroup("Team Agent retirement failed", errors)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        errors = []
        try:
            if any(not task.done() for task in self.tasks):
                try:
                    await self.stop(StopReason.INFRASTRUCTURE_ERROR)
                except Exception as error:
                    errors.append(error)
            outcomes = await asyncio.gather(
                *(asyncio.wait_for(agent.close(), 30) for agent in self.agents.values()),
                return_exceptions=True,
            )
            errors.extend(error for error in outcomes if isinstance(error, Exception))
            for role, agent in self.agents.items():
                if isinstance(agent, ProcessAgent):
                    self.results[role]["native_agent"] = {
                        "admitted": agent.admitted, "forced_termination": agent.forced_termination,
                    }
            outcomes = await asyncio.gather(
                *(asyncio.wait_for(client.close(), 10) for client in self.clients.values()),
                return_exceptions=True,
            )
            errors.extend(error for error in outcomes if isinstance(error, Exception))
        finally:
            for role, log in self.logs.items():
                self.aggregate.requests.extend(log.requests)
                self.aggregate.tool_calls += log.tool_calls
                self.aggregate.observations += log.observations
                self.results.setdefault(role, {})["accounting"] = log.accounting()
                log.event("end", **self.results[role])
                write_json(self.root / "participants" / role / "result.json", self.results[role])
        if errors:
            raise ExceptionGroup("Team Agent cleanup failed", errors)
