import asyncio
import copy
import json
import time
from pathlib import Path

import httpx
import pytest

from agents.llm.base_client import ClientError, Message, RequestEvent
from agents.llm.providers.github_copilot_client import GitHubCopilotClient
from agents.llm.providers.openai_client import OpenAIClient


MODEL = {
    "id": "test-model", "supported_endpoints": ["/responses"],
    "capabilities": {"supports": {"tool_calls": True, "vision": True}},
}
TOOL = {"name": "lookup", "parameters": {"type": "object", "properties": {}}}


def reply(output=None, **extra):
    return {
        "status": "completed", "id": "response-1", "model": "test-model",
        "output": output if output is not None else [
            {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": "OK"}]},
        ],
        **extra,
    }


def wire(payload, *, eof=False):
    return httpx.Response(
        200, headers={"Content-Type": "text/event-stream"},
        content="event: response.completed\n"
        + "data: " + json.dumps({"type": "response.completed", "response": payload})
        + ("" if eof else "\n\n"),
    )


@pytest.mark.parametrize("provider", ["openai", "copilot"])
def test_multimodal_tool_roundtrip(provider, monkeypatch, red_png):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "github_pat_test")
    bodies = []
    events: list[RequestEvent] = []
    output = [
        {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque-test-state"},
        {"type": "function_call", "call_id": "call-1", "name": "lookup", "arguments": "{}"},
        {"type": "function_call", "call_id": "call-2", "name": "lookup", "arguments": "{}"},
    ]
    usage = {"input_tokens": 20, "output_tokens": 4, "total_tokens": 24}

    def handler(request):
        assert request.headers["authorization"] in ("Bearer test-key", "Bearer github_pat_test")
        if request.url.path == "/models":
            return httpx.Response(200, json={"data": [MODEL]})
        body = json.loads(request.content)
        bodies.append(body)
        if provider == "copilot":
            assert request.headers["Copilot-Vision-Request"] == "true"
        payload = reply(output, usage=usage) if len(bodies) == 1 else reply()
        return wire(payload, eof=True) if provider == "copilot" else httpx.Response(200, json=payload)

    async def scenario():
        cls = OpenAIClient if provider == "openai" else GitHubCopilotClient
        client = cls("test-model", transport=httpx.MockTransport(handler), on_request=events.append)
        history = [Message("user", [
            {"type": "text", "text": "Read this image and look up twice."},
            {"type": "image", "data": red_png, "mime_type": "image/png"},
        ])]
        original = copy.deepcopy(history)
        async with client:
            response = await client.chat(history, tools=[TOOL], tool_choice="required")
            assert response.finish_reason == "tool_calls"
            assert response.tool_calls[0]["arguments"] == {}
            assert response.usage == usage
            assert history == original
            history += [
                Message("assistant", response.content, response.tool_calls,
                        provider_data=response.provider_data),
                Message("tool", "first", tool_call_id="call-1"),
                Message("tool", [
                    {"type": "text", "text": "second"},
                    {"type": "image", "data": red_png, "mime_type": "image/png"},
                ], tool_call_id="call-2"),
            ]
            result = await client.chat(history, tools=[TOOL], tool_choice="none")
            assert result.content == "OK" and result.usage is None
        await client.close()
        with pytest.raises(RuntimeError):
            await client.chat([Message("user", "After close")])

    asyncio.run(scenario())
    assert bodies[0]["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert bodies[0]["tools"][0]["strict"] is False
    replay = bodies[1]["input"]
    assert sum(item.get("type") == "reasoning" for item in replay) == 1
    assert sum(item.get("type") == "function_call" for item in replay) == 2
    assert [item["call_id"] for item in replay if item.get("type") == "function_call_output"] == ["call-1", "call-2"]
    assert events[0].usage == usage and events[1].usage is None


@pytest.mark.parametrize("failure,expected_count", [
    ("rate_limit", 2), ("quota", 1), ("connect", 2), ("read_timeout", 1),
    ("incomplete", 1), ("invalid_arguments", 1), ("truncated_stream", 1),
])
def test_errors_and_bounded_retries(failure, expected_count, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []
    events = []

    def handler(request):
        calls.append(request.url.path)
        if len(calls) > 1:
            return httpx.Response(200, json=reply())
        if failure in ("rate_limit", "quota"):
            return httpx.Response(429, json={
                "error": {"code": "insufficient_quota" if failure == "quota" else "rate_limit",
                          "message": "SECRET MUST NOT APPEAR"},
            })
        if failure == "connect":
            raise httpx.ConnectError("connection failed")
        if failure == "read_timeout":
            raise httpx.ReadTimeout("read timed out")
        if failure == "incomplete":
            return httpx.Response(200, json=reply(status="incomplete", usage={"output_tokens": 10}))
        if failure == "invalid_arguments":
            return httpx.Response(200, json=reply([
                {"type": "function_call", "call_id": "c1", "name": "lookup", "arguments": "[]"},
            ]))
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                              content='data: {"type":"response.created"}\n\n')

    async def scenario():
        async with OpenAIClient(
            "test-model", max_attempts=3, retry_backoff=0,
            transport=httpx.MockTransport(handler), on_request=events.append,
        ) as client:
            if expected_count == 2:
                assert (await client.chat([Message("user", "Hello")])).content == "OK"
            else:
                with pytest.raises((ClientError, httpx.ReadTimeout, ValueError)) as caught:
                    await client.chat([Message("user", "Hello")])
                assert "SECRET" not in str(caught.value)

    asyncio.run(scenario())
    assert len(calls) == len(events) == expected_count
    assert not events[0].success
    if failure == "incomplete":
        assert events[0].usage == {"output_tokens": 10}


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_and_cancellation_are_not_retried(cancel, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    events = []

    async def scenario():
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        async with OpenAIClient(
            "test-model", timeout=10 if cancel else 0.02, max_attempts=3,
            transport=httpx.MockTransport(handler), on_request=events.append,
        ) as client:
            task = asyncio.create_task(client.chat([Message("user", "Hello")]))
            await entered.wait()
            if cancel:
                task.cancel()
            with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
                await task

    asyncio.run(scenario())
    assert len(events) == 1 and not events[0].success


def test_copilot_auth_fallback_and_endpoint_validation(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "bad-test-token")
    token_file = tmp_path / "token.txt"
    token_file.write_text("fallback-test-token")
    auth = []

    def handler(request):
        if request.url.path == "/copilot_internal/v2/token":
            auth.append(request.headers["authorization"])
            if len(auth) == 1:
                return httpx.Response(401, json={})
            return httpx.Response(200, json={
                "token": "exchanged-test-token", "expires_at": time.time() + 3600,
                "refresh_in": 3600, "endpoints": {"api": "https://api.githubcopilot.com"},
            })
        assert request.headers["authorization"] == "Bearer exchanged-test-token"
        if request.url.path == "/models":
            return httpx.Response(200, json={"data": [MODEL]})
        return wire(reply())

    async def scenario():
        async with GitHubCopilotClient(
            "test-model", token_file=token_file, transport=httpx.MockTransport(handler),
        ) as client:
            assert (await client.chat([Message("user", "Hello")])).content == "OK"
            assert (await client.chat([Message("user", "Again")])).content == "OK"
        def malicious_endpoint(request):
            return httpx.Response(200, json={
                "token": "never-send", "expires_at": time.time() + 3600,
                "refresh_in": 3600, "endpoints": {"api": "https://untrusted.example"},
            })
        async with GitHubCopilotClient(
            "test-model", transport=httpx.MockTransport(malicious_endpoint),
        ) as client:
            with pytest.raises(ValueError, match="untrusted"):
                await client.chat([Message("user", "Hello")])

    asyncio.run(scenario())
    assert auth == ["token bad-test-token", "token fallback-test-token"]


def test_invalid_messages_fail_before_network(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    invalid = [
        [Message("user", [{"type": "image", "data": "not bytes", "mime_type": "image/png"}])],
        [Message("tool", "unmatched", tool_call_id="missing")],
        [Message("assistant", tool_calls=[{"id": "c", "name": "lookup", "arguments": {}}])],
        [Message("assistant", "OK", provider_data={
            "responses_output": [], "provider": "github_copilot", "model": "test-model",
        })],
    ]

    def handler(request):
        pytest.fail("Invalid input must not send a request")

    async def scenario():
        async with OpenAIClient("test-model", transport=httpx.MockTransport(handler)) as client:
            for messages in invalid:
                with pytest.raises(ValueError):
                    await client.chat(messages)

    asyncio.run(scenario())
