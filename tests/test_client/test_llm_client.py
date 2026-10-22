"""Three opt-in checks per supported client: text, image and tool calling."""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest
import httpx

from agent_framework.llm_client.base_client import BaseLLMClient, ClientError, Message
from agent_framework.llm_client.github_copilot_client import GitHubCopilotClient
from agent_framework.llm_client.openai_client import OpenAIClient
from agent_framework.llm_client.vllm_client import VLLMClient
from agent_framework.llm_client.responses import ResponsesClient, parse_response


@pytest.mark.parametrize("error,expected", [
    ({"code": "context_length_exceeded"}, "context_length_exceeded"),
    ({"code": "context_window_exceeded"}, "context_length_exceeded"),
    ({"code": "invalid_request_body", "message": "Request exceeds the context window."}, "context_length_exceeded"),
    ({"message": "Maximum context length is 100 tokens; the request exceeded it."}, "context_length_exceeded"),
    ({"code": "invalid_request_body", "message": "Invalid context field."}, "http_400"),
    ({"message": "Rate limit exceeded."}, "http_400"),
    ({"code": "insufficient_quota"}, "insufficient_quota"),
])
def test_provider_errors_are_sanitized_and_not_retried(error, expected):
    class Client(BaseLLMClient):
        calls = 0

        async def _request_impl(self, messages, **kwargs):
            self.calls += 1
            ResponsesClient.check_status(httpx.Response(400, json={"error": error}))

        async def close(self):
            pass

    async def run():
        client = Client(retry_backoff=0)
        with pytest.raises(ClientError) as raised:
            await client.chat([Message("user", "test")])
        assert raised.value.code == expected and client.calls == 1
        assert str(raised.value) == f"Model request failed: {expected} (HTTP status: 400)"
        if expected == "context_length_exceeded":
            with pytest.raises(ClientError) as streamed:
                parse_response({"status": "failed", "error": error}, "test", "test")
            assert streamed.value.code == expected
        await client.close()

    asyncio.run(run())


@pytest.mark.live
@pytest.mark.parametrize("provider", ["copilot", "openai", "vllm"])
@pytest.mark.parametrize("kind", ["text", "image", "tool_calling"])
def test_live_client(provider, kind, black_png):
    if os.environ.get(f"LIVEQUEST_LIVE_{provider.upper()}") != "1":
        pytest.skip(f"Set LIVEQUEST_LIVE_{provider.upper()}=1 to consume provider quota")
    model = os.environ.get(f"LIVEQUEST_{provider.upper()}_MODEL")
    if not model:
        pytest.fail("An explicit LIVEQUEST_<PROVIDER>_MODEL is required")
    events = []
    report = {"provider": provider, "model": model, "check": kind, "status": "failed"}

    async def scenario():
        if provider == "copilot":
            token_path = os.environ.get("LIVEQUEST_COPILOT_TOKEN_FILE")
            client = GitHubCopilotClient(
                model, token_file=Path(token_path) if token_path else None,
                max_output_tokens=1024, on_request=events.append,
                reasoning_effort=os.environ.get("LIVEQUEST_REASONING_EFFORT"),
            )
        elif provider == "openai":
            client = OpenAIClient(
                model, max_output_tokens=1024, on_request=events.append,
                reasoning_effort=os.environ.get("LIVEQUEST_REASONING_EFFORT"),
            )
        else:
            client = VLLMClient(
                model, base_url=os.environ.get("LIVEQUEST_VLLM_BASE_URL", "http://127.0.0.1:8001/v1"),
                max_output_tokens=1024, on_request=events.append,
            )
        async with client:
            if kind == "text":
                result = await client.chat([Message("user", "Reply with exactly: LIVEQUEST_OK")])
                assert isinstance(result.content, str) and result.content.strip() == "LIVEQUEST_OK"
                return
            if kind == "image":
                result = await client.chat([Message("user", [
                    {"type": "text", "text": "What is the dominant color of this image? Reply with one English color word."},
                    {"type": "image", "data": black_png, "mime_type": "image/png"},
                ])])
                assert isinstance(result.content, str) and result.content.strip().lower().rstrip(".") == "black"
                return
            tools = [{
                "name": "lookup_code", "description": "Look up the code for a key.",
                "parameters": {"type": "object", "properties": {"key": {"type": "string"}},
                               "required": ["key"], "additionalProperties": False},
            }]
            history = [Message("user", "Call lookup_code with key 'island' once, then reply with only its returned code.")]
            result = await client.chat(history, tools=tools, tool_choice="required")
            assert len(result.tool_calls) == 1
            call = result.tool_calls[0]
            assert call["name"] == "lookup_code" and call["arguments"] == {"key": "island"}
            call_id = call["id"]
            assert isinstance(call_id, str) and call_id
            history.extend([
                Message("assistant", result.content, result.tool_calls, provider_data=result.provider_data),
                Message("tool", '{"code":"LQB_7391"}', tool_call_id=call_id),
            ])
            final = await client.chat(history, tools=tools, tool_choice="none")
            assert not final.tool_calls
            assert isinstance(final.content, str) and final.content.strip() == "LQB_7391"

    try:
        asyncio.run(scenario())
        report["status"] = "passed"
    finally:
        report["attempts"] = [asdict(event) for event in events]
        report_directory = os.environ.get("LIVEQUEST_LIVE_REPORT_DIR")
        if report_directory:
            destination = Path(report_directory)
            destination.mkdir(parents=True, exist_ok=True)
            path = destination / f"{provider}-{kind}.json"
            path.write_text(json.dumps(report, indent=2) + "\n")
