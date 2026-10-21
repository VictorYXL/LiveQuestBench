import asyncio
import logging
import os
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from agents.llm.base_client import ClientError, LLMResponse, Message, RequestEvent
from agents.llm.providers.responses import ResponsesClient, array, obj, text


logger = logging.getLogger(__name__)


class GitHubCopilotClient(ResponsesClient):
    """Direct Copilot protocol adapted from GameAgentVisual, not a public API SLA.

    Set COPILOT_GITHUB_TOKEN. An explicitly assigned token_file is a fallback.
    No implicit access to other projects' credential caches is performed.
    """

    provider = "github_copilot"
    token_file: Path | None = None
    TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

    def __init__(
        self, model: str, *, token_file: Path | None = None,
        max_output_tokens: int = 4096, reasoning_effort: str | None = None,
        timeout: float = 120, max_attempts: int = 1, retry_backoff: float = 1,
        on_request: Callable[[RequestEvent], None] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            model, max_output_tokens=max_output_tokens, reasoning_effort=reasoning_effort,
            timeout=timeout, max_attempts=max_attempts, retry_backoff=retry_backoff,
            on_request=on_request, transport=transport,
        )
        self.token_file = token_file
        self._token: str | None = None
        self._expires_at = 0.0
        self._endpoint = "https://api.githubcopilot.com"
        self._fallback = False
        self._models: list[dict[str, object]] | None = None
        self._auth_lock = asyncio.Lock()
        self._http.headers.update({
            "User-Agent": "LiveQuestBench",
            "Editor-Version": "vscode/1.115.0",
            "Editor-Plugin-Version": "copilot-chat/0.44.0",
            "Copilot-Integration-Id": "vscode-chat",
            "X-GitHub-Api-Version": "2025-05-01",
        })

    def _github_token(self) -> str:
        token = "" if self._fallback else os.environ.get("COPILOT_GITHUB_TOKEN", "").strip()
        if not token and self.token_file is not None:
            token = self.token_file.read_text(encoding="utf-8").strip()
            self._fallback = True
        if not token:
            raise ValueError("Set COPILOT_GITHUB_TOKEN or assign a nonempty token_file")
        return token

    async def _authenticate(self) -> None:
        async with self._auth_lock:
            if self._token and time.time() < self._expires_at:
                return
            token = self._github_token()
            if token.startswith("github_pat_"):
                self._token = token
                self._endpoint = "https://api.githubcopilot.com"
                self._expires_at = float("inf")
                return
            response = await self._http.get(
                self.TOKEN_URL, headers={"Authorization": f"token {token}"},
            )
            self.check_status(response)
            envelope = obj(response.json())
            endpoint = text(obj(envelope.get("endpoints", {})).get("api", self._endpoint))
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme != "https" or not parsed.hostname
                or not (parsed.hostname == "api.githubcopilot.com" or parsed.hostname.endswith(".githubcopilot.com"))
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            ):
                raise ValueError("Copilot returned an untrusted API endpoint")
            exchanged = text(envelope.get("token"))
            if not exchanged:
                raise ValueError("Copilot returned an empty token")
            expires, refresh = envelope.get("expires_at"), envelope.get("refresh_in")
            if not isinstance(expires, (int, float)) or not isinstance(refresh, (int, float)):
                raise ValueError("Copilot token expiry metadata is missing")
            self._endpoint = endpoint.rstrip("/")
            self._token = exchanged
            self._expires_at = min(expires, time.time() + refresh) - 60

    async def list_models(self) -> list[dict[str, object]]:
        """Read account model metadata without making a generation request."""
        async with asyncio.timeout(self.timeout):
            await self._authenticate()
            response = await self._http.get(
                f"{self._endpoint}/models",
                headers={"Authorization": f"Bearer {self._token}"},
            )
            self.check_status(response)
            return [obj(model) for model in array(obj(response.json()).get("data"))]

    async def _request_impl(
        self, messages: Sequence[Message], *,
        tools: Sequence[dict[str, object]] | None, tool_choice: str | None,
    ) -> LLMResponse:
        body = self.body(messages, tools, tool_choice, stream=True)
        images = any(
            part.get("type") == "input_image"
            for item in array(body["input"])
            for part in (obj(p) for p in array(obj(item).get("content", [])))
        )
        for attempt in range(2):
            try:
                await self._authenticate()
                if self._models is None:
                    self._models = await self.list_models()
                model = next((m for m in self._models if m.get("id") == self.model), None)
                if model is None:
                    raise ValueError(f"Copilot model {self.model!r} is unavailable")
                if obj(model.get("policy", {})).get("state") == "disabled":
                    raise ValueError("Copilot model is disabled")
                if "/responses" not in array(model.get("supported_endpoints", [])):
                    raise ValueError("Copilot model does not support Responses")
                supports = obj(obj(model.get("capabilities")).get("supports"))
                if tools and not supports.get("tool_calls"):
                    raise ValueError("Copilot model does not support tools")
                if images and not supports.get("vision"):
                    raise ValueError("Copilot model does not support images")
                efforts = supports.get("reasoning_effort")
                if self.reasoning_effort is not None and isinstance(efforts, list) and self.reasoning_effort not in efforts:
                    raise ValueError("Unsupported reasoning_effort for Copilot model")
                headers = {
                    "Authorization": f"Bearer {self._token}",
                    "X-Request-Id": uuid.uuid4().hex,
                    "OpenAI-Intent": "conversation-agent",
                }
                if images:
                    headers["Copilot-Vision-Request"] = "true"
                return await self.send(f"{self._endpoint}/responses", body, headers)
            except ClientError as exc:
                if exc.status not in (401, 403) or attempt:
                    raise
                logger.warning("Copilot authentication rejected; refreshing once")
                self._token = None
                self._models = None
                if self.token_file is not None:
                    self._fallback = True
        raise ClientError("authentication_failed")

    async def close(self) -> None:
        await super().close()
        self._token = None
