"""Local Chat Completions client following the existing GameAgent vLLM path."""

import copy
import json
import math
import os
from collections.abc import Callable, Sequence
from urllib.parse import urlsplit

import httpx

from agent_framework.llm_client.base_client import BaseLLMClient, ClientError, LLMResponse, Message, RequestEvent
from agent_framework.llm_client.responses import ResponsesClient, array, content_parts, obj, text


class VLLMClient(BaseLLMClient):
    """Use an independently managed vLLM server, without loading weights here."""

    def __init__(
        self, model: str, *, base_url: str = "http://127.0.0.1:8001/v1",
        max_output_tokens: int = 1024, temperature: float = 0,
        enable_thinking: bool = False, timeout: float = 120,
        max_attempts: int = 1, retry_backoff: float = 1,
        on_request: Callable[[RequestEvent], None] | None = None,
    ) -> None:
        super().__init__(timeout=timeout, max_attempts=max_attempts,
                         retry_backoff=retry_backoff, on_request=on_request)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a nonempty identifier")
        endpoint = urlsplit(base_url)
        if (
            endpoint.scheme not in ("http", "https") or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
        ):
            raise ValueError("base_url must be an HTTP(S) endpoint without credentials or query")
        if endpoint.scheme == "http" and endpoint.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Use HTTPS for non-loopback inference endpoints")
        if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        if not math.isfinite(temperature) or temperature < 0:
            raise ValueError("temperature must be finite and nonnegative")
        if not isinstance(enable_thinking, bool):
            raise ValueError("enable_thinking must be a boolean")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self._http = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

    def _messages(self, messages: Sequence[Message]) -> list[dict[str, object]]:
        if not messages:
            raise ValueError("At least one message is required")
        converted: list[dict[str, object]] = []
        pending: set[str] = set()
        seen: set[str] = set()
        for message in messages:
            if message.role not in ("system", "user", "assistant", "tool"):
                raise ValueError("Unsupported message role")
            if message.role != "tool" and pending:
                raise ValueError("Missing tool results")
            if message.role != "assistant" and message.tool_calls:
                raise ValueError("Only assistant messages can request tools")
            if message.role != "tool" and message.tool_call_id is not None:
                raise ValueError("Only tool messages can reference a tool call")
            calls = []
            for call in message.tool_calls:
                call_id, name = text(call.get("id")), text(call.get("name"))
                if not call_id or call_id in seen or not name:
                    raise ValueError("Tool calls need unique IDs and nonempty names")
                pending.add(call_id)
                seen.add(call_id)
                calls.append({
                    "id": call_id, "type": "function",
                    "function": {"name": name, "arguments": json.dumps(obj(call.get("arguments")))},
                })
            parts = content_parts(message.content)
            if message.role in ("assistant", "system", "tool") and any(
                part["type"] == "input_image" for part in parts
            ):
                raise ValueError("This vLLM integration accepts images in user messages only")
            item: dict[str, object] = {"role": message.role}
            if isinstance(message.content, list):
                item["content"] = [
                    {"type": "text", "text": part["text"]}
                    if part["type"] == "input_text" else
                    {"type": "image_url", "image_url": {"url": part["image_url"]}}
                    for part in parts
                ]
            else:
                item["content"] = message.content
            if message.role == "assistant":
                if calls:
                    item["tool_calls"] = calls
                if message.provider_data:
                    if (
                        message.provider_data.get("provider") != "vllm"
                        or message.provider_data.get("model") != self.model
                        or message.provider_data.get("base_url") != self.base_url
                    ):
                        raise ValueError("Cannot replay state across models or providers")
                    saved = obj(message.provider_data.get("chat_message"))
                    native_calls = self._tool_calls(saved.get("tool_calls") or [])
                    if native_calls != message.tool_calls or saved.get("content") != message.content:
                        raise ValueError("Native chat state disagrees with the public message")
                    item = copy.deepcopy(saved)
            elif message.role == "tool":
                if message.tool_call_id not in pending:
                    raise ValueError("Tool result does not match a pending call")
                pending.remove(message.tool_call_id)
                item["tool_call_id"] = message.tool_call_id
                item["content"] = "\n".join(text(part["text"]) for part in parts)
            converted.append(item)
        if pending:
            raise ValueError("Missing tool results")
        return converted

    @staticmethod
    def _tool_calls(raw: object) -> list[dict[str, object]]:
        calls = []
        seen: set[str] = set()
        for value in array(raw):
            call = obj(value)
            if call.get("type") != "function":
                raise ValueError("Unsupported tool call type")
            function = obj(call.get("function"))
            call_id, name = text(call.get("id")), text(function.get("name"))
            if not call_id or call_id in seen or not name:
                raise ValueError("Tool calls need unique IDs and nonempty names")
            seen.add(call_id)
            calls.append({
                "id": call_id, "name": name,
                "arguments": obj(json.loads(text(function.get("arguments")))),
            })
        return calls

    async def _request_impl(
        self, messages: Sequence[Message], *,
        tools: Sequence[dict[str, object]] | None, tool_choice: str | None,
    ) -> LLMResponse:
        if tool_choice not in (None, "auto", "none", "required"):
            raise ValueError("tool_choice must be auto, none or required")
        if not tools and tool_choice not in (None, "none"):
            raise ValueError("tool_choice requires tools")
        body: dict[str, object] = {
            "model": self.model, "messages": self._messages(messages),
            "temperature": self.temperature, "max_tokens": self.max_output_tokens,
            "stream": False, "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if tools:
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
            body["tools"] = [{"type": "function", "function": tool} for tool in tools]
            body["tool_choice"] = tool_choice or "auto"
            body["parallel_tool_calls"] = False
        token = os.environ.get("VLLM_API_KEY", "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = await self._http.post(
            f"{self.base_url}/chat/completions", json=body, headers=headers,
        )
        ResponsesClient.check_status(response)
        payload = obj(response.json())
        usage = obj(payload["usage"]) if payload.get("usage") is not None else None
        try:
            choices = array(payload.get("choices"))
            if len(choices) != 1:
                raise ClientError("expected_one_completion", usage=usage)
            choice = obj(choices[0])
            finish = choice.get("finish_reason")
            if finish not in ("stop", "tool_calls", "content_filter"):
                raise ClientError("incomplete_response", usage=usage)
            message = obj(choice.get("message"))
            if message.get("role") != "assistant":
                raise ValueError("Expected an assistant response")
            content = text(message["content"]) if message.get("content") is not None else None
            calls = self._tool_calls(message.get("tool_calls") or [])
            if not content and not calls:
                raise ClientError("empty_response", usage=usage)
            if (finish == "tool_calls") != bool(calls):
                raise ClientError("inconsistent_tool_finish_reason", usage=usage)
            return LLMResponse(
                content=content, tool_calls=calls, finish_reason=text(finish), usage=usage,
                provider_data={"provider": "vllm", "model": self.model, "base_url": self.base_url,
                               "chat_message": copy.deepcopy(message)},
            )
        except (ValueError, TypeError) as exc:
            raise ClientError("invalid_response", usage=usage) from exc

    async def close(self) -> None:
        await self._http.aclose()
