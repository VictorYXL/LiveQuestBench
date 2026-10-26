from abc import ABC, abstractmethod
import asyncio
import json
import logging
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import httpx


logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A chat turn using the existing Minecraft client's content conventions.

    Content blocks contain text or encoded image bytes plus a MIME type.
    Tool calls contain id, name and parsed arguments; tool_call_id links results.
    Keep provider-specific evidence intact; clients declare what history is replayed.
    """

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[dict[str, object]] | None = ""
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    tool_call_id: str | None = None
    provider_data: dict[str, object] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Provider response; missing usage is unknown, not zero."""

    content: str | list[dict[str, object]] | None = None
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, object] | None = None
    provider_data: dict[str, object] = field(default_factory=dict)


class ClientError(RuntimeError):
    """A sanitized provider failure, possibly with usage from a rejected response."""

    def __init__(
        self, code: str, *, status: int | None = None,
        usage: dict[str, object] | None = None,
        response_details: dict[str, object] | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(f"Model request failed: {code} (HTTP status: {status})")
        self.code = code
        self.status = status
        self.usage = usage
        self.response_details = response_details
        if retry_after_seconds is not None and (not math.isfinite(retry_after_seconds) or retry_after_seconds < 0):
            raise ValueError("retry_after_seconds must be finite and nonnegative")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class RequestEvent:
    """One attempt, including failed/cancelled attempts; no credentials or prompts."""

    attempt: int
    elapsed_seconds: float
    success: bool
    error_type: str | None
    usage: dict[str, object] | None


class BaseLLMClient(ABC):
    """Model calls only; Agents own messages, tools and memory.

    External Agents are not required to use this client. Transport retries may
    duplicate remote inference/cost, but never replay executed game actions.
    """

    history_policy = "provider-native-v1"

    def __init__(
        self, *, timeout: float = 120, max_attempts: int = 3,
        retry_backoff: float = 1,
        on_request: Callable[[RequestEvent], None] | None = None,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if not math.isfinite(retry_backoff) or retry_backoff < 0:
            raise ValueError("retry_backoff must be finite and nonnegative")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.retry_backoff = retry_backoff
        self.on_request = on_request
        self.on_query: Callable[[str, dict[str, object]], None] | None = None
        self._query_index = 0

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, object]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Retry transport failures, empty/incomplete generations and invalid JSON."""
        self._query_index += 1
        query_id = self._query_index
        for attempt in range(1, self.max_attempts + 1):
            if self.on_query:
                self.on_query("prompt", {
                    "query_id": query_id, "attempt": attempt, "messages": list(messages),
                    "tools": list(tools) if tools is not None else None, "tool_choice": tool_choice,
                    "history_policy": self.history_policy,
                })
            started = time.monotonic()
            response = None
            error: BaseException | None = None
            try:
                async with asyncio.timeout(self.timeout):
                    response = await self._request_impl(
                        messages, tools=tools, tool_choice=tool_choice,
                    )
                return response
            except BaseException as exc:
                error = exc
                retryable = isinstance(exc, (
                    TimeoutError, httpx.TimeoutException, httpx.NetworkError,
                    httpx.RemoteProtocolError, json.JSONDecodeError,
                )) or (
                    isinstance(exc, ClientError)
                    and exc.code not in {
                        "insufficient_quota", "billing_hard_limit_reached", "context_length_exceeded",
                    }
                    and (exc.status in {408, 429, 500, 502, 503, 504}
                         or exc.code in {
                             "stream_ended_without_response", "incomplete_response", "invalid_json_response",
                             "empty_response",
                         })
                )
                if not retryable or attempt == self.max_attempts:
                    raise
            finally:
                event = RequestEvent(
                    attempt=attempt,
                    elapsed_seconds=time.monotonic() - started,
                    success=response is not None,
                    error_type=type(error).__name__ if error else None,
                    usage=response.usage if response else (
                        error.usage if isinstance(error, ClientError) else None
                    ),
                )
                logger.log(
                    logging.INFO if event.success else logging.WARNING,
                    "LLM attempt %s: success=%s error=%s elapsed=%.3fs",
                    attempt, event.success, event.error_type, event.elapsed_seconds,
                )
                if self.on_request:
                    self.on_request(event)
                if self.on_query:
                    self.on_query("response" if response is not None else "error", {
                        "query_id": query_id, "attempt": attempt, "response": response,
                        "request": event,
                        "error_code": error.code if isinstance(error, ClientError) else None,
                        "http_status": error.status if isinstance(error, ClientError) else None,
                        "response_details": error.response_details if isinstance(error, ClientError) else None,
                        "retry_after_seconds": error.retry_after_seconds if isinstance(error, ClientError) else None,
                    })
            delay = self.retry_backoff * 2 ** (attempt - 1)
            if isinstance(error, ClientError):
                if error.retry_after_seconds is not None:
                    delay = max(delay, error.retry_after_seconds)
                elif error.status == 429:
                    delay = max(delay, 30 * 2 ** (attempt - 1))
            logger.warning("Retrying LLM request in %.3fs (next attempt %s)", delay, attempt + 1)
            await asyncio.sleep(delay)
        raise RuntimeError("No request attempt was made")

    @abstractmethod
    async def _request_impl(
        self, messages: Sequence[Message], *,
        tools: Sequence[dict[str, object]] | None,
        tool_choice: str | None,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release client-owned resources; allow repeated cleanup."""
        raise NotImplementedError

    async def __aenter__(self) -> "BaseLLMClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
