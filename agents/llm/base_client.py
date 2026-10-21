from abc import ABC, abstractmethod
import asyncio
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
    Keep provider-specific state intact when appending an assistant response.
    """

    role: Literal["system", "user", "assistant", "tool"]
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
    ) -> None:
        super().__init__(f"Model request failed: {code} (HTTP status: {status})")
        self.code = code
        self.status = status
        self.usage = usage


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

    External Agents are not required to use this client. Timeouts, interrupted
    streams and incomplete generations are never automatically replayed.
    """

    def __init__(
        self, *, timeout: float = 120, max_attempts: int = 1,
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

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, object]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Return a complete response; retry only connection failures or rate limits."""
        for attempt in range(1, self.max_attempts + 1):
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
                retryable = isinstance(exc, httpx.ConnectError) or (
                    isinstance(exc, ClientError) and exc.status == 429
                    and exc.code not in {"insufficient_quota", "billing_hard_limit_reached"}
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
            await asyncio.sleep(self.retry_backoff * 2 ** (attempt - 1))
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
