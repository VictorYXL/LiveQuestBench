"""Supervised native Agent processes with an allowlisted stdio tool/model bridge."""

import asyncio
import base64
from abc import abstractmethod
from collections.abc import Awaitable, Callable, Sequence
import json
import os
from pathlib import Path
import time
from typing import ClassVar, Generic, TypeVar

from agent_framework.agents.base_agent import AgentContext, AgentExit, AgentExitReason, BaseAgent, StopReason
from agent_framework.llm_client.base_client import BaseLLMClient, Message
from agent_framework.llm_client.responses import array, obj, text
from agent_framework.utils.source import SourceSpec, verify_checkout
from agent_framework.utils.tools import Observation, Tool


InterfaceT = TypeVar("InterfaceT")


class IntegrationUnavailable(RuntimeError):
    """A pinned external runtime has not been prepared."""


class IntegrationIncompatible(RuntimeError):
    """The attempted native composition cannot honor the integration condition."""


class ProcessAgent(BaseAgent[InterfaceT], Generic[InterfaceT]):
    """Keep the upstream loop; translate only lifecycle, tools and model transport.

    The native process receives no provider credentials or game administrative
    handles. It is a cooperative integration, not an OS sandbox. The caller owns
    the injected client. Source installs are explicit, never performed by run().
    """

    name: ClassVar[str]
    directory: ClassVar[Path]
    source: ClassVar[SourceSpec]
    required_runtime: ClassVar[str]
    native_observations: ClassVar[bool] = False

    def _additional_tools(self) -> Sequence[Tool[InterfaceT]]:
        return ()

    @classmethod
    def source_root(cls) -> Path:
        source = cls.source
        value = os.environ.get(source["environment"])
        if not value:
            raise IntegrationUnavailable(f"Set {source['environment']} to the prepared pinned checkout")
        root = Path(value).resolve()
        if not root.is_dir():
            raise IntegrationUnavailable(f"{cls.name}: configured checkout does not exist: {root}")
        try:
            verify_checkout(source, root, cls.directory)
        except ValueError as error:
            raise IntegrationIncompatible(f"{cls.name}: {error}") from error
        if not (root / cls.required_runtime).is_file():
            raise IntegrationUnavailable(f"{cls.name}: runtime is not built; see {cls.directory / 'README.md'}")
        return root

    @abstractmethod
    def _worker_command(self) -> list[str]:
        """Return the native runtime and this Agent's worker entrypoint."""
        raise NotImplementedError

    def _prepare_home(self, home: Path) -> None:
        """Optionally install Agent-specific configuration into the fresh home."""

    def __init__(
        self, client: BaseLLMClient, *, output_dir: Path,
        tools: Sequence[Tool[InterfaceT]], observe: Callable[[InterfaceT], Awaitable[Observation]],
        model: str, reasoning_effort: str, max_output_tokens: int,
        on_message: Callable[[Message], None] | None = None,
    ) -> None:
        self.root = self.source_root()
        self.client, self.output_dir = client, Path(output_dir).resolve()
        tools = [*tools, *self._additional_tools()]
        self.tools = {tool.name: tool for tool in tools}
        if not self.tools or len(self.tools) != len(tools):
            raise ValueError("Provide uniquely named tools")
        self.observe = observe
        self.model, self.reasoning_effort, self.max_output_tokens = model, reasoning_effort, max_output_tokens
        self.on_message = on_message
        self.messages: list[Message] = []
        self.stop_reason: StopReason | None = None
        self.forced_termination = False
        self.admitted = False
        self._process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[AgentExit] | None = None
        self._used = False
        self._closed = False
        self._provider_state: dict[str, dict[str, object]] = {}
        self._pending_calls: list[dict[str, object]] = []

    def _record(self, message: Message) -> None:
        self.messages.append(message)
        if self.on_message:
            self.on_message(message)

    async def run(self, context: AgentContext[InterfaceT]) -> AgentExit:
        if self._used or self._closed:
            raise RuntimeError("Use a fresh ProcessAgent for each attempt")
        self._used = True
        if self.stop_reason is not None:
            return AgentExit(AgentExitReason.STOPPED, native_reason=self.stop_reason.value)
        self._task = asyncio.create_task(self._serve(context))
        try:
            return await self._task
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if self.stop_reason is None or (current is not None and current.cancelling()):
                raise
            return AgentExit(AgentExitReason.STOPPED, native_reason=self.stop_reason.value)
        finally:
            await self._terminate()

    async def stop(self, reason: StopReason) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _terminate(self) -> None:
        process = self._process
        if process is not None and process.returncode is None:
            if process.stdin is not None:
                process.stdin.close()
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                self.forced_termination = True
                process.kill()
                await process.wait()

    async def close(self) -> None:
        if self._closed:
            return
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._terminate()
        self._closed = True

    async def _serve(self, context: AgentContext[InterfaceT]) -> AgentExit:
        self.output_dir.mkdir(parents=True, exist_ok=False)
        home = self.output_dir / "home"
        home.mkdir()
        self._prepare_home(home)
        env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE") if key in os.environ}
        env.update(HOME=str(home), PYTHONUNBUFFERED="1")
        with (self.output_dir / "worker.log").open("wb") as log:
            self._process = await asyncio.create_subprocess_exec(
                *self._worker_command(), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=log, cwd=self.output_dir, env=env,
                limit=16 * 1024 * 1024,
            )
            assert self._process.stdin is not None and self._process.stdout is not None
            config = {
                "model": self.model, "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": self.max_output_tokens, "task": context.task,
                "instructions": context.game_instructions,
                "tools": [tool.schema() for tool in self.tools.values()],
                "episode_id": context.episode_id,
            }
            self._process.stdin.write((json.dumps(config) + "\n").encode())
            await self._process.stdin.drain()
            while line := await self._process.stdout.readline():
                request = obj(json.loads(line))
                operation = text(request.get("op"))
                if operation == "exit":
                    result = obj(request.get("result"))
                    code = await self._process.wait()
                    if code != 0 or not self.admitted or self._pending_calls:
                        raise IntegrationIncompatible(f"{self.name}: invalid exit, no admission, or unsettled tool calls")
                    reason = AgentExitReason(text(result.get("reason")))
                    return AgentExit(reason, text(result.get("message", "")), text(result.get("native_reason", "")))
                if operation == "ready":
                    actual = array(request.get("tools"))
                    (self.output_dir / "admission.json").write_text(json.dumps({
                        "expected": sorted(self.tools), "actual": actual,
                        "upstream": self.source,
                    }, indent=2) + "\n")
                    if set(actual) != set(self.tools):
                        raise IntegrationIncompatible(f"{self.name}: native tool whitelist mismatch: {actual}")
                    self.admitted = True
                    value: object = {"accepted": True}
                elif not self.admitted:
                    raise IntegrationIncompatible("Native Agent requested work before tool admission")
                elif operation == "tool":
                    name = text(request.get("name"))
                    if name not in self.tools:
                        raise IntegrationIncompatible(f"Native Agent attempted an unapproved tool: {name}")
                    arguments = obj(request.get("arguments"))
                    proposed = next((call for call in self._pending_calls
                                     if call["name"] == name and call["arguments"] == arguments), None)
                    if proposed is None:
                        raise IntegrationIncompatible("Native Agent attempted an unproposed or repeated tool call")
                    self._pending_calls.remove(proposed)
                    value = await self.tools[name].execute(context.interface, arguments)
                    self._record(Message("tool", value, tool_call_id=text(proposed["id"])))
                elif operation == "observe":
                    observation = await self.observe(context.interface)
                    if self.native_observations:
                        self._record(Message("user", observation))
                        value = observation if isinstance(observation, str) else [
                            {**block, "data": base64.b64encode(block["data"]).decode("ascii")}
                            if block.get("type") == "image" and isinstance(block.get("data"), bytes) else block
                            for block in observation
                        ]
                    else:
                        value = observation if isinstance(observation, str) else "\n".join(
                            text(block["text"]) for block in observation if block.get("type") == "text"
                        )
                elif operation == "chat":
                    value = await self._chat(context, obj(request.get("request")))
                else:
                    raise IntegrationIncompatible(f"Unknown native bridge operation: {operation}")
                self._process.stdin.write((json.dumps({"id": request.get("id"), "result": value}) + "\n").encode())
                await self._process.stdin.drain()
            code = await self._process.wait()
            raise IntegrationIncompatible(f"{self.name}: native worker exited without a result (code {code}); {self.output_dir / 'worker.log'}")

    async def _chat(self, context: AgentContext[InterfaceT], request: dict[str, object]) -> dict[str, object]:
        allowed = {
            "model", "messages", "tools", "max_tokens", "max_completion_tokens",
            "reasoning_effort", "temperature", "top_p", "stop", "timeout",
            "stream", "tool_choice",
        }
        unknown = {key for key, value in request.items() if key not in allowed and value is not None}
        if unknown:
            raise IntegrationIncompatible(f"Unmapped native model settings: {sorted(unknown)}")
        if request.get("stream") not in (None, False):
            raise IntegrationIncompatible("This model bridge requires complete, non-streaming native requests")
        if self._pending_calls:
            raise IntegrationIncompatible("Native Agent requested a new model turn before settling tool calls")
        if request.get("model") != self.model:
            raise IntegrationIncompatible("Native Agent attempted a different model")
        for field in ("max_tokens", "max_completion_tokens"):
            if request.get(field) not in (None, self.max_output_tokens):
                raise IntegrationIncompatible(f"Native {field} does not match experiment configuration")
        if request.get("reasoning_effort") not in (None, self.reasoning_effort):
            raise IntegrationIncompatible("Native reasoning effort does not match experiment configuration")
        for field in ("temperature", "top_p", "stop"):
            if request.get(field) is not None:
                raise IntegrationIncompatible(f"This fixed-model bridge does not support native {field}")
        schemas = [obj(obj(tool).get("function")) for tool in array(request.get("tools"))]
        if {text(schema.get("name")) for schema in schemas} != set(self.tools):
            raise IntegrationIncompatible("Native model request changed the approved tool set")
        messages: list[Message] = []
        for raw in array(request.get("messages")):
            item = obj(raw)
            role = item.get("role")
            if role not in ("system", "developer", "user", "assistant", "tool"):
                raise IntegrationIncompatible(f"Unsupported native message role: {role}")
            raw_content = item.get("content")
            content: str | list[dict[str, object]] | None
            if isinstance(raw_content, list) and self.native_observations:
                content = []
                for raw_block in raw_content:
                    block = obj(raw_block)
                    if block.get("type") == "text":
                        content.append({"type": "text", "text": text(block.get("text"))})
                    elif block.get("type") == "image" and role == "user":
                        mime = text(block.get("mime_type"))
                        if mime not in ("image/png", "image/jpeg"):
                            raise IntegrationIncompatible("Unsupported native image MIME type")
                        content.append({"type": "image", "mime_type": mime,
                                        "data": base64.b64decode(text(block.get("data")), validate=True)})
                    else:
                        raise IntegrationIncompatible("Unsupported native content block")
            elif raw_content is None or isinstance(raw_content, str):
                content = raw_content
            else:
                raise IntegrationIncompatible("Native history must contain text; public images are injected separately")
            calls: list[dict[str, object]] = []
            for raw_call in array(item.get("tool_calls", [])):
                call = obj(raw_call)
                function = obj(call.get("function"))
                calls.append({"id": text(call.get("id")), "name": text(function.get("name")),
                              "arguments": obj(json.loads(text(function.get("arguments"))))})
            state = self._provider_state.get(text(calls[0]["id"]), {}) if calls else {}
            call_id = item.get("tool_call_id")
            if call_id is not None and not isinstance(call_id, str):
                raise IntegrationIncompatible("Invalid native tool-call ID")
            messages.append(Message(role, content, calls, call_id, state))
        if self.native_observations:
            for message in messages:
                if isinstance(message.content, list):
                    self._record(message)
        else:
            observation = await self.observe(context.interface)
            current = Message("user", observation)
            messages.append(current)
            self._record(current)
        with (self.output_dir / "requests.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at_ns": time.monotonic_ns(), "native": request, "effective": {
                "model": self.model, "reasoning_effort": self.reasoning_effort,
                "max_output_tokens": self.max_output_tokens,
            }}) + "\n")
        choice = request.get("tool_choice", "auto")
        if choice not in ("auto", "required", "none"):
            raise IntegrationIncompatible(f"Unsupported native tool choice: {choice}")
        response = await self.client.chat(messages, tools=schemas, tool_choice=choice)
        if response.finish_reason not in ("stop", "tool_calls"):
            raise RuntimeError(f"Incomplete model response: {response.finish_reason}")
        assistant = Message("assistant", response.content, response.tool_calls, provider_data=response.provider_data)
        self._record(assistant)
        for call in response.tool_calls:
            self._provider_state[text(call["id"])] = response.provider_data
        self._pending_calls.extend(response.tool_calls)
        usage = response.usage
        return {
            "id": f"lqb-{len(self.messages)}", "object": "chat.completion",
            "created": int(time.time()), "model": self.model,
            "choices": [{"index": 0, "finish_reason": response.finish_reason, "message": {
                "role": "assistant", "content": response.content,
                "tool_calls": [{"id": call["id"], "type": "function", "function": {
                    "name": call["name"], "arguments": json.dumps(call["arguments"]),
                }} for call in response.tool_calls],
            }}],
            "usage": None if usage is None else {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        }
