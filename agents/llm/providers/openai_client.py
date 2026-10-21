import os
from collections.abc import Sequence

from agents.llm.base_client import LLMResponse, Message
from agents.llm.providers.responses import ResponsesClient


class OpenAIClient(ResponsesClient):
    """OpenAI's official Responses endpoint, using HTTP rather than the SDK."""

    provider = "openai"

    async def _request_impl(
        self, messages: Sequence[Message], *,
        tools: Sequence[dict[str, object]] | None, tool_choice: str | None,
    ) -> LLMResponse:
        body = self.body(messages, tools, tool_choice, stream=False)
        token = os.environ.get("OPENAI_API_KEY", "").strip()
        if not token:
            raise ValueError("Set OPENAI_API_KEY for OpenAI authentication")
        return await self.send(
            "https://api.openai.com/v1/responses", body,
            {"Authorization": f"Bearer {token}"},
        )
