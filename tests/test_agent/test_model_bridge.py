"""Offline native-message compatibility through the real model bridge."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from agent_framework.agents.base_agent import AgentContext
from agent_framework.agents.process_agent import IntegrationIncompatible, ProcessAgent
from agent_framework.llm_client.responses import ResponsesClient
from agent_framework.utils.tools import Tool
from benchmark.compact import read_records
from benchmark.results import EpisodeLog


class BridgeAgent(ProcessAgent):
    @classmethod
    def source_root(cls):
        return Path(__file__).parent

    def _worker_command(self):
        raise AssertionError("Offline bridge check must not launch a worker")


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.4-nano"])
@pytest.mark.parametrize("role", ["system", "developer", "unapproved"])
@pytest.mark.parametrize("storage_profile", ["legacy", "compact"])
def test_native_instruction_roles_preserved_end_to_end(tmp_path, model, role, storage_profile):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "done"}]}],
        })

    class Client(ResponsesClient):
        async def _request_impl(self, messages, *, tools, tool_choice):
            return await self.send("https://test.invalid/responses",
                                   self.body(messages, tools, tool_choice, stream=False), {})

    async def observe(interface):
        return "Public observation"

    async def execute(interface, arguments):
        raise AssertionError("Model transport must not execute game tools")

    async def scenario():
        async with Client(model, transport=httpx.MockTransport(handler)) as client:
            tool = Tool("move", "Move", {"type": "object", "properties": {}}, execute)
            agent = BridgeAgent(client, output_dir=tmp_path, tools=[tool], observe=observe,
                                model=model, reasoning_effort="low", max_output_tokens=4096)
            log = EpisodeLog(tmp_path / "evidence", storage_profile=storage_profile)
            if storage_profile == "compact":
                agent.on_native_request = log.native_request
            request = {
                "model": model, "messages": [{"role": role, "content": "Keep this instruction"},
                                            {"role": "user", "content": "Observe"}],
                "tools": [{"type": "function", "function": tool.schema()}],
            }
            context = AgentContext("test", "Observe", object(), 0, 1)
            if role == "unapproved":
                with pytest.raises(IntegrationIncompatible, match="Unsupported native message role"):
                    await agent._chat(context, request)
                assert bodies == []
            else:
                result = await agent._chat(context, request)
                assert result["choices"][0]["message"]["content"] == "done"
                assert bodies[0]["input"][0] == {
                    "role": role, "content": [{"type": "input_text", "text": "Keep this instruction"}],
                }
                assert bodies[0]["input"][-1]["role"] == "user"
                assert request["messages"][0]["role"] == role
                path = (log.directory / "native.compact.jsonl" if storage_profile == "compact"
                        else tmp_path / "requests.jsonl")
                rows = list(read_records(path))
                assert rows[0]["native"] == request
                assert rows[0]["effective"]["model"] == model

    asyncio.run(scenario())
