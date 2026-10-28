"""Shared Responses protocol used by OpenAI and the existing Copilot integration."""

import base64
import copy
import json
import logging
import math
import re
import time
from collections.abc import Callable, Sequence
from email.utils import parsedate_to_datetime

import httpx

from agent_framework.llm_client.base_client import BaseLLMClient, ClientError, LLMResponse, Message, RequestEvent


def obj(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object with string keys")
    return dict(value)


def array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array")
    return list(value)


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a string")
    return value


def content_parts(content: str | list[dict[str, object]] | None) -> list[dict[str, object]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]
    parts: list[dict[str, object]] = []
    for block in content:
        kind = block.get("type")
        if kind == "text":
            parts.append({"type": "input_text", "text": text(block.get("text"))})
        elif kind == "image":
            data, mime = block.get("data"), block.get("mime_type")
            if not isinstance(data, bytes) or not data:
                raise ValueError("Image data must be nonempty encoded bytes")
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise ValueError("Unsupported image MIME type")
            encoded = base64.b64encode(data).decode("ascii")
            parts.append({
                "type": "input_image", "image_url": f"data:{mime};base64,{encoded}",
                "detail": "auto",
            })
        else:
            raise ValueError("Unsupported message content block")
    return parts


def serialize_messages(
    messages: Sequence[Message], provider: str, model: str,
) -> list[dict[str, object]]:
    if not messages:
        raise ValueError("At least one message is required")
    items: list[dict[str, object]] = []
    pending: set[str] = set()
    seen: set[str] = set()
    for message in messages:
        if message.role not in ("system", "developer", "user", "assistant", "tool"):
            raise ValueError("Unsupported message role")
        if message.role != "tool" and pending:
            raise ValueError("All tool calls require results before the next message")
        if message.role != "assistant" and message.tool_calls:
            raise ValueError("Only assistant messages can request tools")
        if message.role != "tool" and message.tool_call_id is not None:
            raise ValueError("Only tool messages can reference tool_call_id")
        parts = content_parts(message.content)
        if message.role == "assistant":
            for call in message.tool_calls:
                call_id = text(call.get("id"))
                if not call_id or call_id in seen:
                    raise ValueError("Tool call IDs must be nonempty and unique")
                text(call.get("name"))
                obj(call.get("arguments"))
                seen.add(call_id)
                pending.add(call_id)
            saved = message.provider_data.get("responses_output")
            if saved is not None:
                if message.provider_data.get("provider") != provider or message.provider_data.get("model") != model:
                    raise ValueError("Cannot replay provider state across providers or models")
                native = [obj(item) for item in array(saved)]
                native_calls = [
                    {"id": item.get("call_id"), "name": item.get("name"),
                     "arguments": obj(json.loads(text(item.get("arguments"))))}
                    for item in native if item.get("type") == "function_call"
                ]
                if native_calls != message.tool_calls:
                    raise ValueError("Replayed output and tool_calls disagree")
                # Preserve visible output/tool IDs, but never replay hidden reasoning.
                items.extend(copy.deepcopy(item) for item in native if item.get("type") != "reasoning")
                continue
            if any(part["type"] != "input_text" for part in parts):
                raise ValueError("Assistant image output is not supported")
            if parts:
                items.append({"role": "assistant", "content": [
                    {"type": "output_text", "text": part["text"]} for part in parts
                ]})
            for call in message.tool_calls:
                items.append({
                    "type": "function_call", "call_id": call["id"],
                    "name": call["name"], "arguments": json.dumps(call["arguments"]),
                })
        elif message.role == "tool":
            if message.tool_call_id not in pending:
                raise ValueError("Tool result does not match a pending tool call")
            pending.remove(message.tool_call_id)
            items.append({
                "type": "function_call_output", "call_id": message.tool_call_id,
                "output": "\n".join(text(p["text"]) for p in parts if p["type"] == "input_text"),
            })
            images = [p for p in parts if p["type"] == "input_image"]
            if images:
                # Preserve the existing Copilot-compatible screenshot-result mapping.
                items.append({"role": "user", "content": [
                    {"type": "input_text", "text": f"Image result of tool call {message.tool_call_id}:"},
                    *images,
                ]})
        else:
            if message.role in ("system", "developer") and any(p["type"] == "input_image" for p in parts):
                raise ValueError("System/developer messages cannot contain images")
            items.append({"role": message.role, "content": parts})
    if pending:
        raise ValueError("Missing tool results")
    return items


def recognized_error_code(error: object, fallback: str) -> str:
    """Normalize known failures without exposing arbitrary server text."""
    if not isinstance(error, dict):
        return fallback
    code = error.get("code")
    if code in ("insufficient_quota", "billing_hard_limit_reached", "context_length_exceeded"):
        return str(code)
    if code == "context_window_exceeded":
        return "context_length_exceeded"
    message = error.get("message")
    if isinstance(message, str) and re.search(
        r"\bexceed(?:s|ed)?\b[^.\n]{0,120}\bcontext (?:window|length|limit)\b"
        r"|\bcontext (?:window|length|limit)\b[^.\n]{0,120}\bexceed(?:s|ed)?\b",
        message, re.IGNORECASE,
    ):
        return "context_length_exceeded"
    return fallback


def parse_response(payload: dict[str, object], provider: str, model: str) -> LLMResponse:
    raw_usage = payload.get("usage")
    usage = obj(raw_usage) if raw_usage is not None else None
    try:
        return _parse_output(payload, provider, model, usage)
    except json.JSONDecodeError as exc:
        raise ClientError("invalid_json_response", usage=usage) from exc
    except (ValueError, TypeError) as exc:
        raise ClientError("invalid_response", usage=usage) from exc


def _parse_output(
    payload: dict[str, object], provider: str, model: str,
    usage: dict[str, object] | None,
) -> LLMResponse:
    status = payload.get("status")
    if status != "completed":
        code = "incomplete_response" if status == "incomplete" else "failed_response"
        raise ClientError(recognized_error_code(payload.get("error"), code), usage=usage)
    output = array(payload.get("output"))
    texts: list[str] = []
    calls: list[dict[str, object]] = []
    refused = False
    for raw in output:
        item = obj(raw)
        kind = item.get("type")
        if kind == "message":
            for raw_part in array(item.get("content")):
                part = obj(raw_part)
                if part.get("type") == "output_text":
                    texts.append(text(part.get("text")))
                elif part.get("type") == "refusal":
                    texts.append(text(part.get("refusal")))
                    refused = True
                else:
                    raise ClientError("unsupported_response_content", usage=usage)
        elif kind == "function_call":
            calls.append({
                "id": text(item.get("call_id")), "name": text(item.get("name")),
                "arguments": obj(json.loads(text(item.get("arguments")))),
            })
        elif kind != "reasoning":
            raise ClientError("unsupported_response_item", usage=usage)
    ids = [call["id"] for call in calls]
    if any(not call["id"] or not call["name"] for call in calls) or len(set(ids)) != len(ids):
        raise ClientError("invalid_tool_calls", usage=usage)
    if not any(texts) and not calls:
        raise ClientError("empty_response", usage=usage, response_details={
            "status": status, "output_types": [obj(item).get("type") for item in output],
            "text_parts": len(texts), "tool_calls": len(calls),
        })
    return LLMResponse(
        content="".join(texts) or None, tool_calls=calls,
        finish_reason="content_filter" if refused else ("tool_calls" if calls else "stop"),
        usage=usage,
        provider_data={"provider": provider, "model": model,
                       "response_model": payload.get("model"), "response_id": payload.get("id"),
                       "responses_output": copy.deepcopy(output)},
    )


class ResponsesClient(BaseLLMClient):
    """Replay visible history only, consistently across models and native Agents.

    Raw provider output remains available as evidence, not as hidden next-turn
    memory. Reasoning effort still controls each new generation.
    """

    provider = ""
    history_policy = "responses-visible-history"

    def __init__(
        self, model: str, *, max_output_tokens: int = 4096,
        reasoning_effort: str | None = None, timeout: float = 120,
        max_attempts: int = 3, retry_backoff: float = 1,
        on_request: Callable[[RequestEvent], None] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(timeout=timeout, max_attempts=max_attempts,
                         retry_backoff=retry_backoff, on_request=on_request)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a nonempty identifier")
        if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        if reasoning_effort is not None and (
            not isinstance(reasoning_effort, str) or not reasoning_effort
        ):
            raise ValueError("reasoning_effort must be a nonempty string")
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False)

    def body(
        self, messages: Sequence[Message], tools: Sequence[dict[str, object]] | None,
        tool_choice: str | None, *, stream: bool,
    ) -> dict[str, object]:
        if tool_choice not in (None, "auto", "none", "required"):
            raise ValueError("tool_choice must be auto, none or required")
        if not tools and tool_choice not in (None, "none"):
            raise ValueError("tool_choice requires tools")
        body: dict[str, object] = {
            "model": self.model, "input": serialize_messages(messages, self.provider, self.model),
            "store": False, "stream": stream, "truncation": "disabled",
            "max_output_tokens": self.max_output_tokens,
        }
        if tools:
            definitions = []
            names: set[str] = set()
            for tool in tools:
                if set(tool) - {"name", "description", "parameters"}:
                    raise ValueError("Tools accept name, description and parameters only")
                name = text(tool.get("name"))
                if not name or name in names:
                    raise ValueError("Tool names must be nonempty and unique")
                names.add(name)
                obj(tool.get("parameters"))
                if "description" in tool:
                    text(tool["description"])
                definitions.append({"type": "function", **tool, "strict": False})
            body["tools"] = definitions
            body["tool_choice"] = tool_choice or "auto"
            body["parallel_tool_calls"] = True
        if self.reasoning_effort is not None:
            body["reasoning"] = {"effort": self.reasoning_effort}
        return body

    @staticmethod
    def check_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        code = f"http_{response.status_code}"
        try:
            error = obj(response.json()).get("error")
            code = recognized_error_code(error, code)
        except (ValueError, TypeError):
            pass
        retry_after = None
        value = response.headers.get("retry-after")
        if value is not None:
            try:
                try:
                    retry_after = float(value)
                except ValueError:
                    deadline = parsedate_to_datetime(value)
                    if deadline.tzinfo is None:
                        raise ValueError("Retry-After date has no timezone")
                    retry_after = max(0, deadline.timestamp() - time.time())
                if not math.isfinite(retry_after) or retry_after < 0:
                    raise ValueError("Invalid Retry-After delay")
            except (TypeError, ValueError, OverflowError):
                logging.getLogger(__name__).warning("Ignoring malformed Retry-After header")
                retry_after = None
        raise ClientError(code, status=response.status_code, retry_after_seconds=retry_after)

    async def send(
        self, url: str, body: dict[str, object], headers: dict[str, str],
    ) -> LLMResponse:
        async with self._http.stream("POST", url, json=body, headers=headers) as response:
            if not response.is_success:
                await response.aread()
                self.check_status(response)
            if "text/event-stream" not in response.headers.get("content-type", ""):
                await response.aread()
                return parse_response(obj(response.json()), self.provider, self.model)
            data: list[str] = []

            def consume() -> LLMResponse | None:
                payload = "\n".join(data)
                data.clear()
                if payload == "[DONE]":
                    raise ClientError("stream_ended_without_response")
                event = obj(json.loads(payload))
                if event.get("type") in ("response.completed", "response.incomplete", "response.failed"):
                    return parse_response(obj(event.get("response")), self.provider, self.model)
                if event.get("type") == "error":
                    raise ClientError(recognized_error_code(event, "stream_error"))
                return None

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line and data:
                    result = consume()
                    if result is not None:
                        return result
            if data:
                result = consume()
                if result is not None:
                    return result
        raise ClientError("stream_ended_without_response")

    async def close(self) -> None:
        await self._http.aclose()
