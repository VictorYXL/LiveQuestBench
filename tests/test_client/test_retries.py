"""Offline request-retry policy, accounting and cancellation boundaries."""

import asyncio
import json

import httpx
import pytest

from agent_framework.llm_client.base_client import BaseLLMClient, ClientError, LLMResponse, Message


class ProbeClient(BaseLLMClient):
    def __init__(self, outcomes, **kwargs):
        self.events = []
        super().__init__(retry_backoff=0, on_request=self.events.append, **kwargs)
        self.outcomes = iter(outcomes)
        self.requests = []

    async def _request_impl(self, messages, *, tools, tool_choice):
        self.requests.append((messages, tools, tool_choice))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def close(self):
        pass


@pytest.mark.parametrize("error", [
    httpx.ConnectError("offline"), httpx.ReadError("disconnected"),
    httpx.WriteError("disconnected"), httpx.ReadTimeout("slow"),
    httpx.RemoteProtocolError("incomplete body"), TimeoutError(),
    *[ClientError(f"http_{status}", status=status) for status in (408, 429, 500, 502, 503, 504)],
    ClientError("stream_ended_without_response"),
    ClientError("incomplete_response", usage={"output_tokens": 3}),
    ClientError("invalid_json_response", usage={"output_tokens": 3}),
    ClientError("empty_response", usage={"output_tokens": 18}),
    json.JSONDecodeError("invalid", "{", 1),
])
def test_transient_failures_retry_same_request_with_accounting(error):
    response = LLMResponse(content="done", finish_reason="stop", usage={"output_tokens": 2})
    client = ProbeClient([error, error, response])
    messages = [Message("user", "Observe")]
    assert asyncio.run(client.chat(messages)) is response
    assert len(client.requests) == 3
    assert all(request == client.requests[0] for request in client.requests)
    assert [event.attempt for event in client.events] == [1, 2, 3]
    assert [event.success for event in client.events] == [False, False, True]
    failed_usage = error.usage if isinstance(error, ClientError) else None
    assert [event.usage for event in client.events] == [failed_usage, failed_usage, response.usage]


@pytest.mark.parametrize("error", [
    *[ClientError(f"http_{status}", status=status) for status in (400, 401, 403, 404, 422, 501)],
    ClientError("insufficient_quota", status=429),
    ClientError("billing_hard_limit_reached", status=503),
    *[ClientError(code, usage={"output_tokens": 3}) for code in (
        "invalid_response", "invalid_finish_reason",
        "invalid_tool_calls", "failed_response", "stream_error",
    )],
    ValueError("tool arguments have the wrong shape"),
    httpx.LocalProtocolError("bad request"),
    asyncio.CancelledError(),
])
def test_permanent_output_and_cancellation_failures_do_not_retry(error):
    client = ProbeClient([error, LLMResponse(content="must not run")])
    with pytest.raises(type(error)):
        asyncio.run(client.chat([Message("user", "Observe")]))
    assert len(client.requests) == len(client.events) == 1
    assert not client.events[0].success
    assert client.events[0].usage == (error.usage if isinstance(error, ClientError) else None)


@pytest.mark.parametrize("attempts", [1, 3])
def test_attempt_limit_is_total_not_additional(attempts):
    error = ClientError("empty_response", usage={"output_tokens": 18})
    client = ProbeClient([error] * 4, max_attempts=attempts)
    with pytest.raises(ClientError, match="empty_response"):
        asyncio.run(client.chat([Message("user", "Observe")]))
    assert len(client.requests) == len(client.events) == attempts


def test_empty_response_diagnostics_survive_retry_and_outer_cancellation():
    details = {"status": "completed", "output_types": ["reasoning"], "text_parts": 0, "tool_calls": 0}
    error = ClientError("empty_response", usage={"output_tokens": 18}, response_details=details)

    async def scenario():
        client = ProbeClient([error, LLMResponse(content="done")])
        queries = []
        client.on_query = lambda kind, data: queries.append((kind, data))
        assert (await client.chat([Message("user", "Observe")])).content == "done"
        assert queries[1][0] == "error"
        assert queries[1][1]["response_details"] == details
        assert queries[1][1]["request"].usage == {"output_tokens": 18}
        client = ProbeClient([error, LLMResponse(content="must not run")])
        client.retry_backoff = 10
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(.02):
                await client.chat([Message("user", "Observe")])
        assert len(client.requests) == 1

    asyncio.run(scenario())


def test_request_timeout_retries_but_outer_deadline_cancels_backoff():
    class SlowClient(ProbeClient):
        async def _request_impl(self, messages, *, tools, tool_choice):
            self.requests.append(messages)
            await asyncio.sleep(10)
            raise AssertionError("Expected timeout")

    async def scenario():
        client = SlowClient([], timeout=.01)
        with pytest.raises(TimeoutError):
            await client.chat([Message("user", "Observe")])
        assert len(client.events) == 3
        assert all(event.error_type == "TimeoutError" for event in client.events)
        client = ProbeClient([httpx.ConnectError("offline")])
        client.retry_backoff = 10
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(.02):
                await client.chat([Message("user", "Observe")])
        assert len(client.requests) == len(client.events) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("protocol", ["responses", "responses_stream", "chat"])
@pytest.mark.parametrize("failure,retry", [
    ("json_body", True), ("json_arguments", True), ("incomplete", True),
    ("empty", True), ("argument_shape", False), ("refusal", False),
])
def test_provider_parsing_drives_resends_without_executing_tools(protocol, failure, retry):
    from agent_framework.llm_client.responses import ResponsesClient
    from agent_framework.llm_client.vllm_client import VLLMClient

    class LocalResponses(ResponsesClient):
        async def _request_impl(self, messages, *, tools, tool_choice):
            return await self.send(
                "https://test.invalid/responses",
                self.body(messages, tools, tool_choice, stream=protocol == "responses_stream"), {},
            )

    requests = []
    usage = {"output_tokens": 7}

    def payload(broken):
        if protocol == "chat":
            message = {"role": "assistant", "content": "done"}
            finish = "stop"
            if broken:
                if failure in ("json_arguments", "argument_shape"):
                    message = {"role": "assistant", "content": None, "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "move", "arguments": "{" if failure == "json_arguments" else "[]"},
                    }]}
                    finish = "tool_calls"
                elif failure == "incomplete":
                    finish = "length"
                elif failure == "empty":
                    message["content"] = ""
                elif failure == "refusal":
                    finish = "content_filter"
            return {"choices": [{"message": message, "finish_reason": finish}], "usage": usage}
        result = {
            "status": "completed", "usage": usage,
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "done"}]}],
        }
        if broken:
            if failure in ("json_arguments", "argument_shape"):
                result["output"] = [{
                    "type": "function_call", "call_id": "call_1", "name": "move",
                    "arguments": "{" if failure == "json_arguments" else "[]",
                }]
            elif failure == "incomplete":
                result["status"] = "incomplete"
            elif failure == "empty":
                result["output"] = []
            elif failure == "refusal":
                result["output"] = [{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}]
        return result

    def handler(request):
        requests.append(request.content)
        broken = len(requests) == 1
        data = payload(broken)
        if protocol == "responses_stream":
            event = {"type": "response.incomplete" if data["status"] == "incomplete" else "response.completed",
                     "response": data}
            encoded = "{" if broken and failure == "json_body" else json.dumps(event)
            return httpx.Response(200, text=f"data: {encoded}\n\n", headers={"content-type": "text/event-stream"})
        if broken and failure == "json_body":
            return httpx.Response(200, text="{", headers={"content-type": "application/json"})
        return httpx.Response(200, json=data)

    async def scenario():
        events = []
        if protocol == "chat":
            client = VLLMClient("test", retry_backoff=0, on_request=events.append)
            await client._http.aclose()
            client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        else:
            client = LocalResponses("test", retry_backoff=0, on_request=events.append,
                                    transport=httpx.MockTransport(handler))
        messages = [Message("user", "Move")]
        async with client:
            if retry or failure == "refusal":
                result = await client.chat(messages)
                assert result.finish_reason == ("stop" if retry else "content_filter")
            else:
                with pytest.raises(ClientError):
                    await client.chat(messages)
        assert len(requests) == len(events) == (2 if retry else 1)
        assert all(body == requests[0] for body in requests)
        assert messages == [Message("user", "Move")]
        if failure != "refusal":
            assert not events[0].success
            assert events[0].usage == (None if failure == "json_body" else usage)
        if retry:
            assert events[1].success and events[1].usage == usage

    asyncio.run(scenario())
