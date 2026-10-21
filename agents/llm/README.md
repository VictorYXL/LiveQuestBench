# Model clients

Three implementations share the existing `Message` / `LLMResponse` interface:

- [`GitHubCopilotClient`](providers/github_copilot_client.py): direct Copilot
  Responses protocol adapted from GameAgentVisual's `xianya/init_mincraft` branch.
  This is not the Copilot SDK or a guaranteed stable public GitHub API; account
  entitlement, policy and upstream protocol changes can affect availability.
- [`OpenAIClient`](providers/openai_client.py): the official
  `https://api.openai.com/v1/responses` endpoint, called with `httpx`, not the
  OpenAI Python SDK. This avoids two transport/retry stacks.
- [`VLLMClient`](providers/vllm_client.py): a local OpenAI-compatible
  `/v1/chat/completions` endpoint, following the existing GameAgent vLLM path.
  The inference server and its GPU dependencies run in a separate environment.

All support text, encoded PNG/JPEG/WebP user images, function-tool calls and results,
provider-state replay, usage reporting, timeouts, cancellation and
explicit cleanup. They return a complete response, not token-by-token callbacks.
Copilot SSE is consumed internally; OpenAI requests a non-streamed response.
vLLM uses non-streamed Chat Completions, not Responses.

## Authentication and a first request

Use `COPILOT_GITHUB_TOKEN` or `OPENAI_API_KEY` in the process environment. Never
commit credentials. Copilot optionally accepts an explicit local token-file path;
the environment wins initially, with one file fallback on authentication rejection.
It does not search other projects' credential caches.

```python
import asyncio
from pathlib import Path

from agents.llm.base_client import Message
from agents.llm.providers.github_copilot_client import GitHubCopilotClient


async def main():
    async with GitHubCopilotClient(
        "gpt-5.4-nano",  # Use a model available to your account.
        token_file=Path("output/support/github_copilot_token.txt"),
        max_output_tokens=1024,
        reasoning_effort="none",  # Only if this model supports it.
    ) as client:
        response = await client.chat([Message("user", "Say hello.")])
        print(response.content)


asyncio.run(main())
```

For OpenAI, import `OpenAIClient` and use an account-supported model with
`OPENAI_API_KEY` set. There is no `token_file` argument for OpenAI.
Model names are explicit; no model downgrade or substitute is chosen silently.
Copilot checks account model metadata for Responses, vision and tool support.
OpenAI reports unsupported model features through the official endpoint.

## Image input

```python
message = Message("user", [
    {"type": "text", "text": "Describe this game screen."},
    {
        "type": "image",
        "data": Path("screen.png").read_bytes(),
        "mime_type": "image/png",
    },
])
response = await client.chat([message])
```

Images are encoded file bytes, not paths, raw pixels or PIL objects. Content
validation checks byte type and MIME, not image decoding or model size limits.
The provider creates Base64 data URLs without resizing. System/assistant images,
audio, video, generated image output and built-in hosted tools are not supported.

## Function tools and history

Pass flat tool definitions with `name`, optional `description`, and `parameters`
(a JSON-schema object). Do not wrap them in a Chat Completions `function` envelope.
The client uses `strict=False` to preserve existing tool schema compatibility.

```python
tools = [{
    "name": "get_inventory",
    "description": "Read the player's permitted inventory.",
    "parameters": {"type": "object", "properties": {}},
}]
messages = [Message("user", "Check my inventory.")]
response = await client.chat(messages, tools=tools, tool_choice="required")
messages.append(Message(
    role="assistant",
    content=response.content,
    tool_calls=response.tool_calls,
    provider_data=response.provider_data,
))
# The Agent validates/executes each requested tool and appends one result per ID.
```

For each call, append `Message("tool", result_content, tool_call_id=call_id)` before
the next model request. Multiple calls are allowed; this does not prescribe
parallel game execution. Missing/duplicate/unmatched result IDs fail explicitly.
Client code never executes tools, modifies caller history or declares task success.
The Agent remains responsible for tool authorization and argument schema checks.

`tool_choice` accepts `auto`, `none` and `required`. Tool image results follow
GameAgentVisual's explicit compatibility mapping: a text `function_call_output`
linked by ID, followed by a user image message labeled with the same ID. This is
not native image-valued function output and can affect model interpretation.

Retain `provider_data` when appending assistant replies. Its raw
`responses_output` includes items needed to replay reasoning state exactly once.
It is tied to the provider and selected model; cross-provider/model replay is
rejected. Do not edit raw replay items independently of the public tool calls.
It is protocol state, not a credential store or a transcript export format.

## Failure, retries and accounting

- `timeout` bounds each whole attempt, including authentication and body reading.
  A caller needing an overall deadline must wrap the entire `chat()` call.
- `max_attempts=1` by default. If increased, only connection-establishment errors
  and HTTP 429 rate limits are retried, with exponential `retry_backoff`.
  Known insufficient-quota/billing-limit codes are not retried.
- Timeouts, interrupted streams, HTTP 5xx, incomplete generations and malformed
  outputs are not replayed automatically: remote completion/cost may be uncertain.
  Cancellation propagates immediately. Cancellation does not guarantee cancellation
  of remote inference or billing.
- Copilot handles a rejected authentication (401/403) by refreshing once within
  an attempt. No successful generation is retried for authentication.
- HTTP failures expose a sanitized `ClientError`, not the server's arbitrary
  message or authorization headers. Unsupported inputs fail with explicit errors.
- `finish_reason` is `stop`, `tool_calls` or `content_filter` for accepted replies.
  Incomplete output raises instead of handing potentially truncated tools to an
  Agent. A refusal is returned as refusal text with `content_filter`, not success.
- `usage` retains the Responses usage fields (`input_tokens`, `output_tokens`,
  `total_tokens` and provider detail objects) when supplied. Missing usage is
  `None`, never a fabricated zero.

Pass `on_request=callback` to receive a `RequestEvent` per attempt: elapsed time,
success, error type and available usage, including failed/cancelled attempts.
This event excludes prompts and credentials. It is not aggregate cost accounting.
Callbacks must be fast and non-throwing; a callback failure propagates and is not
treated as a retryable model failure. Standard logs include attempt status only.
Do not enable HTTP header/body debug logging with production credentials.

`async with` closes the client; `close()` may also be called repeatedly. Closing
does not cancel caller-owned concurrent tasks; cancel/await them before shutdown.

## Validation

```bash
uv sync --locked --group test
uv run --locked --group test python -m pytest tests/test_client -q
```

Only three types of test are retained, parameterized over the three providers:
pure text, text with a generated all-black PNG, and function-tool calling.
The earlier offline contract suite was removed at the user's request and remains
available in Git history. Default execution skips all nine cases without network
requests; skipped tests are not evidence of working service integration.

Opt-in live Copilot validation (four generations, potentially consuming quota):

```bash
LIVEQUEST_LIVE_COPILOT=1 \
LIVEQUEST_COPILOT_MODEL=gpt-5.4-nano \
LIVEQUEST_REASONING_EFFORT=none \
LIVEQUEST_COPILOT_TOKEN_FILE=output/support/github_copilot_token.txt \
LIVEQUEST_LIVE_REPORT_DIR=output/runs/client-smoke \
uv run --locked --group test python -m pytest \
  tests/test_client/test_llm_client.py -k copilot -x -q
```

The live tests check exact text, recognition of a synthetic black image, function
name/arguments and the final answer after a synthetic tool result. It does not
send repository code, real screenshots or private task data. Summary reports
contain check status and usage, not credentials or raw provider state.

For OpenAI, explicitly set `LIVEQUEST_LIVE_OPENAI=1`,
`LIVEQUEST_OPENAI_MODEL=<available-model>` and `OPENAI_API_KEY`, and select
`tests/test_client/test_llm_client.py -k openai`. Omit reasoning settings for models that
do not support them. Live tests are skipped by default; opting in without a
model or usable credentials is a failure, not a passing skip.

### OpenAI collaborator handoff

Run in an eligible service region using your own authorized project credentials
and available API credit. Keep the key in that environment; do not send it to
collaborators or include it in reports. A key issued abroad does not remove
[service-region restrictions](https://developers.openai.com/api/docs/supported-countries).

After cloning/pulling this repository and setting `OPENAI_API_KEY` securely:

```bash
uv sync --locked --group test
uv run --locked --group test python -m pytest tests/test_client --collect-only -q

LIVEQUEST_LIVE_OPENAI=1 \
LIVEQUEST_OPENAI_MODEL=gpt-5.4-nano \
LIVEQUEST_REASONING_EFFORT=none \
LIVEQUEST_LIVE_REPORT_DIR=output/runs/openai-client-smoke \
uv run --locked --group test python -m pytest \
  tests/test_client/test_llm_client.py -k openai -x -q

git rev-parse HEAD
uv run --locked python --version
```

The model above is an example, not a guarantee of account availability. Select
an available Responses model supporting vision and function calling, and set
reasoning effort only when supported. This test makes four generation requests
if all stages succeed; requests can incur charges even when assertions fail.

Return the commit hash, Python version, pytest outcome and
the `openai-text.json`, `openai-image.json` and `openai-tool_calling.json` files
under `output/runs/openai-client-smoke/`. Each report records its check status
and per-attempt usage. With `-x`, testing stops on the first failure; later reports
will not be produced. Inspect any
additional error logs before sharing; exclude keys, HTTP headers and account
details. Reports are local, Git-ignored artifacts, not automatically published.
Use a fresh report directory for each run to preserve previous attempts.

## Local vLLM model

The client uses the same flat public tool definitions and message types as the
hosted clients. It converts them to Chat Completions `messages`, `image_url`
blocks and nested `function` definitions. Native assistant messages (including
any reasoning fields) are retained in `provider_data`; they cannot be replayed
across endpoints or models.

```python
from agents.llm.providers.vllm_client import VLLMClient

async with VLLMClient(
    "qwen3-vl-2b",
    base_url="http://127.0.0.1:8001/v1",
    max_output_tokens=1024,
) as client:
    response = await client.chat([Message("user", "Say hello.")])
```

No hosted API key is used. Set `VLLM_API_KEY` only if your own server requires
authentication. Plain HTTP is restricted to loopback addresses; remote endpoints
require HTTPS. The client does not install/start servers, change GPU settings,
truncate history or reduce output budgets silently. Context-limit failures
propagate. Default sampling is `temperature=0`, with
`chat_template_kwargs.enable_thinking=False` and `parallel_tool_calls=False`.
These are explicit settings, not a guarantee that every model template supports
them. Tool results are text-only in this integration; images belong in user
messages. Usage retains Chat Completions fields such as `prompt_tokens` and
`completion_tokens`, rather than claiming Responses field names.

### Small-model server example

Use a separate inference environment; vLLM and PyTorch are not dependencies of
the main benchmark environment. The following starting configuration targets
a single NVIDIA GPU and a small VLM, not production throughput:

```bash
uv venv --python 3.11 output/temp/vllm-env
uv pip install --python output/temp/vllm-env/bin/python 'vllm==0.11.2'

CUDA_VISIBLE_DEVICES=0 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 \
output/temp/vllm-env/bin/vllm serve Qwen/Qwen3-VL-2B-Instruct \
  --revision 89644892e4d85e24eaac8bacfd4f463576704203 \
  --served-model-name qwen3-vl-2b \
  --host 127.0.0.1 --port 8001 \
  --dtype bfloat16 --max-model-len 4096 --max-num-seqs 1 \
  --gpu-memory-utilization 0.4 --enforce-eager \
  --limit-mm-per-prompt '{"image":1,"video":0}' \
  --mm-processor-kwargs '{"min_pixels":4096,"max_pixels":262144}' \
  --enable-auto-tool-choice --tool-call-parser hermes
```

The GPU memory fraction controls vLLM's allocation budget, not a hard process
memory cap. Image preprocessing and context/concurrency limits affect memory.
Check free GPU memory and the health endpoint before testing:

```bash
curl --fail http://127.0.0.1:8001/health
LIVEQUEST_LIVE_VLLM=1 \
LIVEQUEST_VLLM_MODEL=qwen3-vl-2b \
LIVEQUEST_VLLM_BASE_URL=http://127.0.0.1:8001/v1 \
LIVEQUEST_LIVE_REPORT_DIR=output/runs/vllm-client-smoke \
uv run --locked --group test python -m pytest \
  tests/test_client/test_llm_client.py -k vllm -x -q
```

Run the server in a separate terminal and stop it after testing to release GPU
memory. Do not stop unrelated GPU services. Downloaded weights remain cached.
The tool test uses `tool_choice="required"`: vLLM can enforce the output schema
through constrained decoding. Passing it verifies the tool protocol and result
roundtrip, not autonomous tool selection or long-horizon planning ability.

## Deferred

Prompt rendering, dialogue recording/image dumps, Agent memory, Episode budgets,
currency pricing, streaming callbacks, JSON-schema structured output and external
SDK adapters are outside this increment. Public `Message` and `LLMResponse`
remain unchanged; the base's new `_request_impl` hook owns one provider attempt.
