from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal


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


class BaseLLMClient(ABC):
    """Model calls only; Agents own messages, tools and memory.

    External Agents are not required to use this client. Provider implementations,
    retry policy and call accounting are deliberately not implemented here yet.
    """

    @abstractmethod
    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, object]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Request a response without executing tools or modifying chat history."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Release client-owned resources; allow repeated cleanup."""
        raise NotImplementedError
