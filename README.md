# LiveQuestBench

LiveQuestBench is an early-stage benchmark project for agents pursuing
long-horizon objectives in continuously evolving 3D games. The intended focus is
the interaction between immediate reaction, persistent resources and decisions
whose consequences affect later stages.

**Current status: model clients, six Agent integrations and Minecraft
VM/ST, not a complete benchmark.** GitHub Copilot, OpenAI Responses
and local vLLM clients are implemented.
Minecraft shares isolated local sessions, initialization and native snapshot
inventory and bounded structure evaluation across VM and ST using one native-client implementation.
VM supports screenshots/input; ST exposes fixed native-client structured tools.
Both support desktop/headless execution and native first-person recording,
including the controlled player's HUD and inventory screens.
Both local modes run without Microsoft login; VM uses a prepared Fabric
development client with Minecraft's native renderer, not a replacement viewer.
`ToolCallingAgent` implements the autonomous loop directly. Pinned DeepSeek
harness and Hermes integrations preserve their native loops using process
Wrappers, with disclosed restrictions and no upstream patches. Orak's native
zeroshot runner has a fixed-tool game extension with a lazy-service patch;
smolagents uses its unpatched native ToolCallingAgent, not CodeAgent.
GamingAgent preserves its native perception-memory-reflection-reasoning harness
and episode runner through a declared transport patch and fixed-tool extension.
All six use
Minecraft's mode-local tool/observation bindings and shared scored tests.
See the [Orak](agent_framework/agents/orak/README.md) and
[smolagents](agent_framework/agents/smolagents/README.md) profiles for setup and
fidelity boundaries, and the [live acceptance report](output/survey/additional_agent_integrations_20261022.md)
for the earlier twelve-case evidence and deferred Game Agent candidates.
See [GamingAgent](agent_framework/agents/gamingagent/README.md) for its
native-image profile and real validation command, and the
[Game Agent follow-up](output/survey/game_agent_followup_20261022.md) for
refreshed candidate evidence and integration results.
There is no experiment
configuration loader, production Episode runner or benchmark launcher yet.

## Development setup

The initial development target is Linux with Python 3.11, matching the minimum
declared by the existing Minecraft projects. Python metadata permits newer
versions, but game/Agent combinations must be checked before claiming support.
Veloren's existing harness declares Python 3.13 or newer; its integration is
deferred, not certified by this environment.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run from
the repository root:

```bash
uv sync --locked
uv run --locked python -c "from game.base_game import BaseGame; from agent_framework.agents.base_agent import BaseAgent; from agent_framework.llm_client.base_client import BaseLLMClient; print('Scaffold imports OK')"
```

- `pyproject.toml` declares Python dependencies; `uv.lock` pins their resolution.
- `.python-version` selects the development interpreter; `.venv/` is local only.
- The model clients use `httpx`; tests use the optional `test` dependency group.
  Do not install all future Agent frameworks into the environment in advance.
- This is a source-run project (`tool.uv.package = false`), not an installable
  distribution yet. Run commands from the repository root.
- Keep one authoritative dependency declaration and lock. Export a requirements
  file if needed; do not maintain a second dependency list manually.

uv manages the Python environment, not Minecraft/Veloren installations, Java,
FFmpeg, X11 setup or game assets. Per-game setup scripts handle explicit
system/game provisioning. External Agents may retain an upstream Conda or
container environment and connect through an adapter; all Agents need not share
one environment.

## Layout

```text
config/
  minecraft/
    tasks/                  Task definitions
    experiments/            Task/Agent/settings selections
    fixtures/               Immutable starting assets or references
game/
  base_game.py              Minimal administrative game contract
  minecraft/
    README.md
    setup.sh
    game.py
    runtime/                Installation, accounts and client/server lifecycle
    init_player_state.py    Private initial player state and verification
    prompts/                introduction.txt plus visual_motor.txt / structured_tool.txt
    evaluators/
    visual_motor/
    structured_tools/
      actions/
      observations/
      tools/
agent_framework/
  llm_client/
    base_client.py          Message/response types and model client contract
    responses.py            Shared multimodal/tool Responses protocol
    github_copilot_client.py
    openai_client.py
    vllm_client.py
  utils/
    tools.py                Shared public tool and observation types
    source.py               Shared pinned-checkout preparation
  agents/
    base_agent.py           Autonomous per-Episode Agent contract
    process_agent.py        Shared native-process lifecycle and tool/model bridge
    tool_calling_agent/     Vanilla baseline, with its own README
    deepseek_harness/       Agent, worker, pinned setup and README
    hermes/                 Agent, worker, configuration, pinned setup and README
    orak/                   Native zeroshot runner extension, declared patch and locked runtime
    smolagents/             Native tool-calling loop and locked runtime, no source patches
    gamingagent/            Native perception/memory/reflection/reasoning and episode runner
core/                       Orchestration boundary and shared infrastructure
  backends/x11/             Shared input and isolated display
tests/
  conftest.py               Shared display and recording options
  test_agent/
    test_agents.py          Real Minecraft/model acceptance for six Agents and operator-stop cases
  test_client/              Three opt-in checks per provider: text, image, tools
  test_game/
    minecraft/
      test_game.py          Installation, world isolation, snapshots and recording
      test_vm.py            Pixels and basic motor actions
      test_st.py            Structured state, tools and cancellation
      test_structure.py     Native construction scoring and consequential counterexamples
pyproject.toml
uv.lock
.python-version
README.md
```

Empty reserved directories contain `.gitkeep` files so that the structure survives
a checkout. They do not indicate implemented functionality. No dummy task YAML,
nonfunctional installer or fake-success runner is supplied.

The four business directories have distinct ownership:

- **config:** what to evaluate, under which conditions and with which fixtures.
- **game:** how to launch/interact with a game and acquire/interpret its evidence.
- **agent_framework:** Agent execution, model clients and shared integration utilities.
- **core:** when to initialize, run, terminate, score and clean up an Episode.

Task-specific fixture assets belong with evaluation configuration conceptually,
even when stored externally by version/hash. Keep templates immutable and create
writable per-Episode state separately. Game binaries and unlicensed assets must
not be committed.

## Provisional base interfaces

These are small starting contracts, not a frozen public API.

| Base | Operations | Responsibility |
| --- | --- | --- |
| [`BaseGame`](game/base_game.py) | `start`, `begin`, `end`, `get_agent_interface`, `save_snapshot`, `close` | One game session, public interaction handle and private evidence acquisition |
| [`BaseAgent`](agent_framework/agents/base_agent.py) | `run(context)`, `stop(reason)`, `close` | Full-attempt execution, typed exit reasons, cooperative stop requests and Agent-owned cleanup |
| [`BaseLLMClient`](agent_framework/llm_client/base_client.py) | `chat`, `close` | Model requests, without taking over Agent history or tool execution |

Game configuration and fixture selection belong to concrete constructors for now.
`start()` initializes a fresh session; the runner collects before evidence,
calls `begin()`, runs the Agent, calls `end()`, collects after evidence and
finally calls `close()`. Snapshot timing and limitations remain game-specific.
No universal world serializer or session-reuse policy is implemented.

Game and Agent bases are generic over their public interface type. This keeps the
scaffold typed without inventing a universal observation/action vocabulary before
adapting a real backend. VM (Visual-Motor) and ST (Structured-Tool) will expose
different allowed operations. The Agent must not receive the administrative game
object, private snapshots, hidden task parameters or evaluator state. A Python
handle alone is not an isolation boundary for untrusted code.

Agents own their reasoning/observation/action loops. The future runner owns
lifecycle and budgets, initializes a fresh Agent per Episode and coordinates
termination with evidence capture. Returning from `run()` is not a successful
score. Stopping an Agent does not stop world evolution, and closing a connection
too early can prevent final evidence acquisition.

The LLM message fields follow the existing Minecraft client's conventions,
including multimodal/tool content and provider state. `LLMResponse` is an initial
typed container, not a drop-in guarantee for existing dictionary-returning
providers. The two hosted providers share Responses serialization and
per-attempt usage callbacks; missing usage is never treated as zero. Aggregate
costs and Episode-level accounting remain future work.

The base Game and Agent contracts remain abstract; Minecraft provides the first
concrete game. The model base implements the
common request lifecycle and requires provider-specific request/cleanup methods.
There are no no-op concrete games, agents or model clients.

## Agent integration

The integration policy is **wrapper-first, with minimal upstream changes**.
Preserve an Agent's existing runtime and behavior wherever possible; prefer
configuration and supported extension points over rewriting its implementation.
The concrete integrations currently available are
[ToolCallingAgent](agent_framework/agents/tool_calling_agent/README.md),
[DeepSeek harness](agent_framework/agents/deepseek_harness/README.md),
[Hermes](agent_framework/agents/hermes/README.md),
[Orak](agent_framework/agents/orak/README.md),
[smolagents](agent_framework/agents/smolagents/README.md) and
[GamingAgent](agent_framework/agents/gamingagent/README.md). This does not establish
support for arbitrary upstream features or other Agents. An end-to-end
benchmark runner is not yet implemented.

### Which Agents can be integrated?

The initial target is an autonomous Agent system that can:

- Receive a public task and game/control instructions.
- Run its own observation, decision and action loop, including an existing
  upstream runner or controller.
- Interact through the selected game's permitted observations and actions.
  VM uses images and motor controls; ST uses approved structured observations
  and fixed skills. Not every Agent needs to support both tracks.
- Expose a recognizable end or return condition and allow the benchmark to
  stop further game interaction at the deadline.
- Honor the model and settings required by the selected experiment, or explicitly
  declare that configuration unsupported.

Agents do not need particular internal method names, a dedicated completion
tool, native asynchronous code, or provider-native LLM tool-call output.
Programmatic observation and safely parsed requests for permitted actions are
valid integration paths. Agent completion does not establish task success;
the benchmark evaluates the outcome independently.

### Choosing an integration path

| Existing Agent capability | Expected integration work |
| --- | --- |
| Configurable task/run entry point, tools and model backend | Write a thin Wrapper that binds game interactions and translates configuration and lifecycle events. Upstream source changes may be unnecessary. |
| Supported Agent Client Protocol (ACP), Model Context Protocol (MCP), or configurable model endpoint | Reuse an appropriate protocol adapter or model bridge. Once the shared integration exists, a compatible Agent may need only configuration. These protocols are optional and do not guarantee compatibility by themselves. |
| Custom environment, tool or model extension interfaces | Implement the upstream interface in a separate adapter and inject it through the Wrapper. |
| Hard-coded game connections, model settings or inaccessible lifecycle hooks | Make a small, versioned upstream patch where necessary. Document its purpose and any behavioral changes. |
| Only a next-action policy, or a runtime requiring different game permissions or timing | Requires additional controller/profile design; it is not a drop-in integration under the initial autonomous-Agent scope. |

A Wrapper presents the benchmark-facing [BaseAgent](agent_framework/agents/base_agent.py)
contract while delegating to the original Agent. It connects task delivery,
execution and stopping, permitted game interactions, and experiment settings.
It can use native calls, an external process or an existing protocol adapter;
wrapping an Agent does not require replacing its internal architecture.
One reusable Wrapper may serve multiple compatible Agents.

### Models, instructions and adaptation limits

An Agent may retain its own LLM client. For fixed-model Agent comparisons,
experiment settings must select the actual model/backend and required generation
parameters, including enabled auxiliary generation roles. Other components,
such as embedding or vision models, must also be declared. Use native
configuration, client injection or a compatible proxy as appropriate; using
LiveQuestBench's Python model client is not mandatory.

Do not silently ignore required settings, substitute models or fall back to
defaults while claiming a controlled comparison. Record effective configuration
and disclose any remaining verification limits. Native full-system results with
different model stacks must be distinguished from fixed-model comparisons.

Public game instructions and task information are supplied by the benchmark.
The Wrapper delivers them through the Agent's supported input mechanism without
requiring a custom system-prompt API. Agent-specific strategy prompts, memory,
extra resources and adaptation changes must be disclosed.

Minimal source edits are acceptable, but changing an Agent's planning method,
skill repertoire or information access is more than interface translation.
Native execution of model-generated programs, hidden-state access, or pausing
the world during reasoning is not covered by the current restricted real-time
condition merely because it can be wrapped or exposed as a tool. Such systems
need an explicitly reviewed adaptation or a separately defined condition.

Support is established for a specific Agent version, adapter, model configuration
and game/track combination after integration checks, including observation/action
round trips, configuration handling, termination and deadline enforcement.
A configurable interface alone is not a claim of working support.

### Python lifecycle contract

[`base_agent.py`](agent_framework/agents/base_agent.py) provides the abstract contract
for native implementations and Wrappers:

- `run(AgentContext[InterfaceT]) -> AgentExit` receives the public task, game
  instructions, permitted interface, episode ID and host-monotonic start/deadline
  timestamps in nanoseconds.
- `AgentExitReason` distinguishes `completed`, `gave_up`, `returned`,
  `native_limit` and `stopped`. The optional native reason preserves upstream
  details. Errors propagate as exceptions; no exit reason is a benchmark score.
- `stop(StopReason)` accepts deadline, game-terminal, operator-cancel or
  infrastructure-error requests. It acknowledges cooperative stopping, not
  guaranteed termination of blocking work.
- `close()` releases Agent-owned resources and allows repeated cleanup.

Create a fresh instance per attempt and pass Agent/model configuration through
its implementation-specific constructor or factory. No model client or
ACP/MCP dependency is required by the base. Remote adapters must translate host
timestamps appropriately. The future runner/game gate, not this abstract class,
must enforce deadlines and preserve final evidence independently of Agent cleanup.

### Adding a game and supplying instructions

Implement [BaseGame](game/base_game.py) under `game/<game_name>/`, document
installation, reset, public permissions, timing, termination, private evidence
and scoring limitations in that game's README. Reuse the existing runtime and
interface patterns where appropriate; do not expose an administrative game
object to an Agent. Admission must reject unsupported game/track combinations.
Validate initialization, observation/action round trips, stopping and evidence
acquisition before interpreting task scores.

The fixed public-text layout is:

```text
game/<game_name>/prompts/
  introduction.txt          Common game introduction and interaction rules
  visual_motor.txt          Optional VM-specific controls/observation format
  structured_tool.txt       Optional ST-specific tools/observation format
```

Load the introduction followed by the selected mode's text. A common-only game
needs only the introduction; file existence alone does not establish track
support. These static files must not contain fixture coordinates, target
resources, task solutions or task-specific strategies. Supply the public task
separately in `AgentContext`. Developer README text is not model input.

Minecraft exposes `get_instructions()` on [MinecraftGame](game/minecraft/game.py).
Its existing [VM](game/minecraft/visual_motor/interface.py) and
[ST](game/minecraft/structured_tools/interface.py) modules each expose
`agent_tools()` and `agent_observation(interface)`. They reuse native schemas
and restricted operations; there is no additional centralized binding module.
VM encodes PNG images; ST losslessly run-length encodes its native palette cube.
No cells or unknown states are removed.

Agent packages do not import games or read game prompt files. The caller
injects game instructions, observation functions and
[Tool definitions](agent_framework/utils/tools.py).
The baseline uses the supplied instructions without adding a system prompt;
upstream Agents retain their own native prompts and disclose differences.
Earlier three-log results used older public instructions. They remain
historical evidence, not task-performance certification of revised prompts.
New live results save the actual game instructions.

### Shared process integration

[`ProcessAgent`](agent_framework/agents/process_agent.py) is an abstract base
for native-process Wrappers, not a standalone Agent. Each concrete Agent owns
its worker, runtime configuration, source pin and setup entrypoint.
Import the concrete class rather than passing a name to the abstract base.
Source URLs, exact commits, licenses and patch lists live in per-Agent
`source.json` files. Game/asset licensing is separate from framework licensing.

[`source.py`](agent_framework/utils/source.py) shares metadata loading and
non-destructive checkout preparation. Setup rejects mismatched pins and unexpected
edits without resetting them. Declared patches are applied only to a pristine
checkout; already-patched checkouts must match exactly. Runtime admission builds
the expected pin-plus-patches tree in a temporary Git index and compares it with
tracked working files, without modifying the checkout's real index.
It also checks the required build. Dependencies and built outputs are trusted, not
integrity-verified; use dedicated checkouts. Tests/runs never install dependencies.
The pinned checkouts are neither vendored source nor submodules.

- The runner owns game lifecycle, deadline and private scoring. Gate game
  interaction before awaiting Agent shutdown. Workers have fresh homes; pending
  work is cancelled and forced termination is reported. Clients/games stay
  caller-owned.
  A raced `AgentAccessClosed` denial is a stopped outcome only when the runner
  intentionally requested cutoff and established the final game boundary.
  Other runtime errors remain failures; they are not converted into stops.
- Workers receive public task/instructions and approved schemas, not game
  administration. A serial JSON-line bridge checks tool admission and each
  model request's tool names. Execution must match model-proposed calls.
  Explicit native control tools such as smolagents' `final_answer` have no game
  access. Python workers share the credential-free
  [`WorkerBridge`](agent_framework/utils/worker.py); Orak can also request public
  observation text for its native memory. It cannot inspect scoring state.
- Model requests use the injected client; credentials stay in the parent.
  Provider continuation state and call IDs are retained. Native settings are
  checked against declared configuration; callers must configure clients
  consistently because arbitrary client internals cannot be inspected.
  Parent transport settings and the benchmark deadline govern actual calls,
  not native HTTP timeout defaults.

This is cooperative isolation, **not an OS sandbox for untrusted code**.
By default, the latest observation is injected at the model bridge. VM gets one current
image and ST one current state. Images are not stored in native history; Orak
also retains public observation text through its native memory adapter. Full
observations stay in audit traces. This differs from the baseline's historical
observation-text retention and must be disclosed in comparisons.
GamingAgent explicitly opts into native observation handling: public frames/text
are captured at native environment boundaries, and its native image resizing,
perception and reflection stages run before action reasoning. Its bridge accepts
inline PNG/JPEG content, not arbitrary attachment paths or URLs, and does not
replace that frame with a newer one during reasoning. Auxiliary roles use the
same configured model/settings with actions disabled. This observation-age and
inference-cost difference must be retained in comparisons.
Unmapped non-null settings fail; new profiles/pins need admission.

### Agent validation

`tests/test_agent/test_agents.py` contains **only real-time game tests using
a live model**: six Agents times two Minecraft modes, plus three operator-stop
cases for the new native workers. It contains no scripted
model responses, fake game interfaces or unit checks. Without explicit opt-in,
all fifteen cases skip; that is not a passing Agent validation.

To inspect the cases without running them:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py --collect-only -q
```

Prepare the pinned runtimes using each Agent's README. Missing runtimes are
explicit skips, not evidence of successful integration. The former `external`
marker and `LIVEQUEST_EXTERNAL_TEST` flag have been removed along with the
simulated/native-offline Agent checks.

The twelve-case Minecraft matrix combines `tool_calling`, `deepseek`, `hermes`,
`orak`, `smolagents` and `gamingagent`
with VM/ST, using `gpt-6-astra`, reasoning `low`, output limit 4096 and one request
attempt. Each case has a 180-second wall-clock budget beginning just before
`game.begin()`, excluding setup/evidence/cleanup. End-request timing is not an
atomic native tick cutoff. These are simple integration tasks: an isolated
peaceful flat world with an empty inventory and a privately prepared three-log
column. Task success requires independently saved inventory count and delta of at
least three oak logs, not an Agent completion claim. Test acceptance instead
requires the configured actual model, real game tool/results, advancing world
time, revoked observation access after the gate, and native admission/cleanup.
Returning an answer without any real game interaction does not establish
integration. Expected operator-stop cases terminate after the first game tool,
not after task completion, and verify the stop outcome and final evidence.

Prepare Minecraft and review/accept its EULA using its
[README](game/minecraft/README.md), then explicitly opt in:

```bash
export MINECRAFT_EULA_ACCEPTED=true
export LIVEQUEST_MINECRAFT_TEST=1
export LIVEQUEST_LIVE_COPILOT=1
# Set COPILOT_GITHUB_TOKEN or an existing authorized token file:
export LIVEQUEST_COPILOT_TOKEN_FILE=/absolute/path/to/copilot-token.txt
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py -m game -q -s --headless --recording
```

Use `-k tool_calling`, `-k deepseek`, `-k hermes`, `-k orak`, `-k smolagents`
or `-k gamingagent` to select an Agent. `-k stop` selects all three operator-stop cases.
`--no-recording` disables video/decoding, not observations or snapshots.
`--no-headless` uses a dedicated existing X11 desktop.
Credentials are never discovered in other repositories; no substitute model
is chosen if the requested one is unavailable. These checks consume quota.

Unique `output/test/` directories (or `MINECRAFT_TEST_OUTPUT`) retain messages,
VM observation images, optional decoded video, private before/after saves, and
`result.json` with configuration, actual instructions, model identity, timing,
usage, Agent exit, real game interactions, `integration_status` and independent
inventory scoring. Process attempts additionally
save admission, native/effective model requests, worker logs, native results when emitted,
and cleanup outcomes.

An independently scored task failure does **not** fail an otherwise validated
integration test: `integration_status=passed` can coexist with
`status=task_failure`. Execution errors are not task outcomes; admission
rejection is recorded as `integration_incompatible` and must be investigated,
not skipped or treated as successful integration. Single samples establish neither
success rates nor Agent rankings or long-horizon competence.

For engineering acceptance, distinguish a valid task failure caused by Agent
capability from a broken integration. The former does not block accepting the
integration, but remains a task failure in scores and test artifacts. Failures
caused by benchmark communication, adaptation, test fixtures, parameters or
scripts must be corrected and revalidated; do not relabel them as capability
limits. Base attribution on recorded evidence, not just the pytest exit code.

## Model clients

The native [`ToolCallingAgent`](agent_framework/agents/tool_calling_agent/README.md) can use these clients directly.
Its Minecraft VM/ST tests exercise the full observation/tool loop and independently
score native inventory snapshots; the provider checks below test clients alone.

Clients live directly under [`llm_client/`](agent_framework/llm_client/), without
a nested provider directory. All implement `Message` / `LLMResponse`:

- [GitHubCopilotClient](agent_framework/llm_client/github_copilot_client.py):
  direct Copilot Responses protocol adapted from GameAgentVisual, not Copilot
  SDK or a guaranteed stable public GitHub API. Entitlement, policy and upstream
  changes affect availability.
- [OpenAIClient](agent_framework/llm_client/openai_client.py):
  official `https://api.openai.com/v1/responses` over `httpx`, not the OpenAI SDK,
  avoiding two transport/retry stacks.
- [VLLMClient](agent_framework/llm_client/vllm_client.py):
  local OpenAI-compatible Chat Completions, with inference/GPU dependencies in
  a separate environment.

Clients return complete responses, not token callbacks. Copilot consumes SSE
internally; OpenAI and vLLM use non-streamed requests. They support encoded
PNG/JPEG/WebP user images, tools, provider-state replay, usage, cancellation and
explicit cleanup, without owning Agent history or tool execution.

### Authentication and requests

Use `COPILOT_GITHUB_TOKEN` or `OPENAI_API_KEY` in the environment; never commit
credentials. Copilot optionally accepts an explicit `token_file`: the environment
wins initially, with one file fallback on authentication rejection. It does not
search other repositories' caches. OpenAI has no token-file parameter.

```python
import asyncio
from agent_framework.llm_client.base_client import Message
from agent_framework.llm_client.github_copilot_client import GitHubCopilotClient

async def main():
    async with GitHubCopilotClient(
        "gpt-5.4-nano", max_output_tokens=1024, reasoning_effort="none",
    ) as client:
        response = await client.chat([Message("user", "Say hello.")])
        print(response.content)

asyncio.run(main())
```

The model/effort are examples; choose supported settings for your account.
No model substitution occurs. Copilot checks model metadata for Responses,
vision and tools; OpenAI reports unsupported features through its endpoint.

```python
from pathlib import Path
message = Message("user", [
    {"type": "text", "text": "Describe this game screen."},
    {"type": "image", "data": Path("screen.png").read_bytes(), "mime_type": "image/png"},
])
response = await client.chat([message])
```

Images are encoded bytes, not paths, raw pixels or PIL objects. Validation
checks byte type/MIME, not decoding or model size limits. Providers create
Base64 data URLs without resizing. System/assistant images, audio/video,
generated-image output and hosted built-in tools are unsupported.

### Tools, history and accounting

Pass flat definitions with `name`, optional `description` and JSON-schema
`parameters`, not a nested Chat Completions `function` envelope:

```python
tools = [{
    "name": "get_inventory",
    "description": "Read the player's permitted inventory.",
    "parameters": {"type": "object", "properties": {}},
}]
messages = [Message("user", "Check my inventory.")]
response = await client.chat(messages, tools=tools, tool_choice="required")
messages.append(Message(
    "assistant", response.content, response.tool_calls,
    provider_data=response.provider_data,
))
# Validate and execute allowed calls, then append each result:
# messages.append(Message("tool", result_text, tool_call_id=call_id))
```

`tool_choice` supports `auto`, `none`, `required`; Responses tools use
`strict=False` for schema compatibility. Append every result before the next
model request. Missing/duplicate/unmatched IDs fail explicitly. Multiple calls
do not prescribe parallel game execution. Clients never execute tools, mutate
caller history or score success. Agents authorize tools and validate arguments.

Keep `provider_data` with assistant replies. Responses replay includes reasoning
state tied to the provider/model; cross-provider/model replay is rejected.
Do not edit raw replay independently of public calls. This is protocol state,
not a credential store or transcript export. Tool-image results map to a text
result linked by ID, followed by a labeled user image, not native image-valued
function output; that mapping can affect interpretation.

- `timeout` bounds a whole attempt, including authentication/body reading, not
  the entire Episode. Wrap the call for a separate overall deadline.
- `max_attempts=1` by default. Additional attempts retry connection-establishment
  errors and HTTP 429 with exponential backoff, not known quota/billing limits.
- Timeouts, interrupted streams, HTTP 5xx, incomplete/malformed responses are
  not replayed automatically: remote completion/cost may be uncertain.
  Cancellation propagates but cannot guarantee remote inference/billing stops.
- Copilot refreshes once on rejected authentication within an attempt, without
  replaying a successful generation.
- HTTP failures expose sanitized `ClientError`, not arbitrary server text or
  authorization headers. Accepted finish reasons are `stop`, `tool_calls`,
  `content_filter`; incomplete output raises. Refusal text is not success.
- Missing usage is `None`, never zero. Responses retain provider usage/detail
  fields; vLLM retains Chat Completions usage names.

`on_request` receives per-attempt elapsed time, success/error and available
usage, including failed/cancelled calls, without prompts/credentials. It is not
aggregate cost accounting. Callbacks must be fast and non-throwing; their errors
propagate. Avoid HTTP header/body debug logging with real credentials.
`close()` is repeatable; cancel/await caller-owned concurrent requests first.
Pricing, streaming callbacks, arbitrary structured output and external SDK
adapters are not implemented by these clients.

### Client validation

```bash
uv sync --locked --group test
uv run --locked --group test python -m pytest tests/test_client -q
```

Live tests are skipped unless explicitly enabled. Only three types of model
checks are retained: text, text with a generated black image, and tool calling.
Actual OpenAI generation requires eligible API quota;
do not assume a ChatGPT account or subscription supplies API credit.

Default execution skips nine opt-in client cases without network calls. A skip
is not evidence of provider availability. Tests check exact text, a synthetic
black PNG and a tool round trip; they do not transmit repository code or real
game screenshots. Reports are written only with `LIVEQUEST_LIVE_REPORT_DIR`;
they retain status/usage, not credentials or raw provider state.

```bash
LIVEQUEST_LIVE_COPILOT=1 LIVEQUEST_COPILOT_MODEL=gpt-5.4-nano \
LIVEQUEST_REASONING_EFFORT=none LIVEQUEST_LIVE_REPORT_DIR=output/test/client-smoke \
uv run --locked --group test python -m pytest \
  tests/test_client/test_llm_client.py -k copilot -x -q
```

The full check makes four generation requests, potentially billable even when
assertions fail. For OpenAI use `LIVEQUEST_LIVE_OPENAI=1`,
`LIVEQUEST_OPENAI_MODEL=<available-model>`, `OPENAI_API_KEY`, and `-k openai`.
Omit reasoning settings for models without them. Opting in without a model or
usable credentials fails rather than skipping.

Run OpenAI checks in an eligible service region with authorized project
credentials and API credit. Keys issued elsewhere do not remove
[region restrictions](https://developers.openai.com/api/docs/supported-countries).
For collaborator handoff, return the commit, Python version, pytest outcome and
the three provider text/image/tool JSON reports from a fresh report directory.
With `-x`, later reports may be absent after a failure. Inspect logs before
sharing and exclude keys, headers and account details. Generated reports are
Git-ignored and not automatically published.

### Local vLLM

```python
from agent_framework.llm_client.vllm_client import VLLMClient
async with VLLMClient(
    "qwen3-vl-2b", base_url="http://127.0.0.1:8001/v1", max_output_tokens=1024,
) as client:
    response = await client.chat([Message("user", "Say hello.")])
```

Set `VLLM_API_KEY` only if your server needs it. Plain HTTP is loopback-only;
remote endpoints require HTTPS. The client never launches servers, changes GPUs,
truncates history or reduces budgets. Context-limit errors propagate. Defaults
are `temperature=0`, `chat_template_kwargs.enable_thinking=False` and
`parallel_tool_calls=False`; model templates must support them. Tool results
are text-only; images are user messages. Native assistant state cannot be
replayed across endpoints/models.

An optional single-GPU example uses a separate environment, not benchmark
dependencies:

```bash
uv venv --python 3.11 "$HOME/.local/share/livequestbench/vllm-env"
uv pip install --python "$HOME/.local/share/livequestbench/vllm-env/bin/python" 'vllm==0.11.2'
CUDA_VISIBLE_DEVICES=0 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 \
"$HOME/.local/share/livequestbench/vllm-env/bin/vllm" serve Qwen/Qwen3-VL-2B-Instruct \
  --revision 89644892e4d85e24eaac8bacfd4f463576704203 \
  --served-model-name qwen3-vl-2b --host 127.0.0.1 --port 8001 \
  --dtype bfloat16 --max-model-len 4096 --max-num-seqs 1 \
  --gpu-memory-utilization 0.4 --enforce-eager \
  --limit-mm-per-prompt '{"image":1,"video":0}' \
  --mm-processor-kwargs '{"min_pixels":4096,"max_pixels":262144}' \
  --enable-auto-tool-choice --tool-call-parser hermes
```

Check free GPU memory first; the fraction is an allocation budget, not a hard
memory cap. Image/context/concurrency settings affect resources. In another
terminal:

```bash
curl --fail http://127.0.0.1:8001/health
LIVEQUEST_LIVE_VLLM=1 LIVEQUEST_VLLM_MODEL=qwen3-vl-2b \
LIVEQUEST_VLLM_BASE_URL=http://127.0.0.1:8001/v1 \
LIVEQUEST_LIVE_REPORT_DIR=output/test/vllm-client-smoke \
uv run --locked --group test python -m pytest \
  tests/test_client/test_llm_client.py -k vllm -x -q
```

Stop your own server afterward; never terminate unrelated GPU services.
Weights remain cached. The tool check uses required/constrained tool selection,
verifying protocol round trips rather than autonomous planning.

## Bottom-up implementation sequence

1. Adapt one Minecraft fixture/session/snapshot path from the existing projects.
   Select one task and one supported interface first, not the entire task catalog.
2. Connect the simplest autonomous reference Agent through the public interface.
3. Build the minimal Benchmark loop around that working path: initialization,
   before evidence, Agent execution, terminal boundary/after evidence, scoring,
   artifacts and cleanup.
4. Integrate a second meaningfully different Agent to check the Agent boundary.
5. Adapt one representative Veloren task to check the game/evidence boundary.
6. Expand Agent, task and interface coverage after both extension points work.

Steps 2 and 3 should iterate closely rather than producing a separate temporary
benchmark. Do not integrate every Agent before checking a second game.

See the [Minecraft integration notes](game/minecraft/README.md) for the local reuse
sources. Existing source and historical results are not proof that every new
combination will run reproducibly.

## Lean validation policy

Keep a few high-value checks, not a test for every edit, method or task YAML.
Prioritize scoring correctness, lifecycle cleanup, result identity and private
information boundaries. There is no test-count or coverage-percentage target.
Agent validation means an actual Agent running a real evolving game with a
live model. Do not substitute scripted replies or import/schema assertions
and report that as successful Agent validation. Static checks can support
development, but they are not Agent acceptance tests.

Keep unit tests only for consequential cases difficult to establish through a
successful gameplay sample. Currently three remain: immutable world-copy/native
inventory evidence, refusal to start without explicit EULA consent, and structure
scoring counterexamples with incomplete/corrupt saved evidence. Structure scoring
also has a real native placement test; no model is needed to validate a scorer.
Removed tests must not be relocated into
new files simply to retain a large suite; avoid assertions that just repeat
dataclass fields, enum values, schema literals or trivial constructor behavior.

Organize tests by the component being checked, not by unit/integration level:

- `tests/test_client/`: supported model clients, using the same three check types.
- `tests/test_game/<game>/`: game basics, VM and ST checks in separate files.
- `tests/test_agent/`: real-time game/model runs and independently scored outcomes.
- `tests/test_benchmark/`: Episode orchestration, configuration, evaluator
  invocation and result persistence.

Current test directories are `test_client`, `test_agent` and `test_game/minecraft`.
Shared options live in [`tests/conftest.py`](tests/conftest.py):
`--recording` / `--no-recording` control test video capture independently of
`--headless` / `--no-headless`. Tests that create a game must pass the shared
`recording` fixture to its constructor and check video only when enabled.
Recording defaults to on; the legacy `MINECRAFT_TEST_RECORDING=0` override is
honored unless a recording CLI option is supplied. Tests without game video
are unaffected.

Keep explicit opt-in switches for
real services and games.
Do not duplicate scoring checks between game and benchmark tests, build a large
mock framework or mirror every source module.

Fast checks must not launch games, modify display sessions or make paid model
requests. Native game smoke checks are separate and opt-in. Import/syntax checks
do not qualify real gameplay, timing, reset, scoring or provider compatibility.

Tests should not write persistent reports by default. Necessary game runtime
files, snapshots and recordings belong under `output/test/`; client reports are
opt-in. These are generated outputs, not prerequisites supplied by the repository.
Public instructions must not depend on private development notes, credentials or
other untracked intermediate files. Research hypotheses and proposed protocols
must not be presented as implemented or independently validated behavior.
