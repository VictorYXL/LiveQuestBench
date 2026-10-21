# LiveQuestBench

LiveQuestBench is an early-stage benchmark project for agents pursuing
long-horizon objectives in continuously evolving 3D games. The intended focus is
the interaction between immediate reaction, persistent resources and decisions
whose consequences affect later stages.

**Current status: model clients, a native tool-calling baseline and a Minecraft
VM/ST integration, not a complete benchmark.** GitHub Copilot, OpenAI Responses
and local vLLM clients are implemented.
Minecraft shares isolated local sessions, initialization and native snapshot
inventory evaluation across VM and ST using one native-client implementation.
VM supports screenshots/input; ST exposes fixed native-client structured tools.
Both support desktop/headless execution and native first-person recording,
including the controlled player's HUD and inventory screens.
Both local modes run without Microsoft login; VM uses a prepared Fabric
development client with Minecraft's native renderer, not a replacement viewer.
`ToolCallingAgent` implements the autonomous loop directly, with Minecraft
bindings and opt-in scored integration tests. There is no experiment
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
uv run --locked python -c "from game.base_game import BaseGame; from agents.base_agent import BaseAgent; from agents.llm.base_client import BaseLLMClient; print('Scaffold imports OK')"
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
    guide/
    evaluators/
    visual_motor/
    structured_tools/
      actions/
      observations/
      tools/
agents/
  base_agent.py             Autonomous per-Episode Agent contract
  tool_calling_agent.py     Native vanilla tool-calling baseline
  minecraft_tool_calling.py Minecraft VM/ST observation and tool bindings
  README.md                 Baseline behavior, ownership and live checks
  adapters/                 Future external Agent adapters
  llm/
    base_client.py          Message/response types and model client contract
    README.md               Provider usage and validation instructions
    providers/
      responses.py          Shared multimodal/tool Responses protocol
      github_copilot_client.py
      openai_client.py
      vllm_client.py
core/                       Orchestration boundary and shared infrastructure
  backends/x11/             Shared input and isolated display
tests/
  conftest.py               Shared display and recording options
  test_agent/
    test_base_agent.py      Lifecycle contract checks
    test_tool_calling_agent.py Offline loop checks and opt-in Minecraft runs
  test_client/              Three opt-in checks per provider: text, image, tools
  test_game/
    minecraft/
      test_game.py          Installation, world isolation, snapshots and recording
      test_vm.py            Pixels and basic motor actions
      test_st.py            Structured state, tools and cancellation
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
- **agents:** how an Agent reasons and acts, plus model integrations.
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
| [`BaseAgent`](agents/base_agent.py) | `run(context)`, `stop(reason)`, `close` | Full-attempt execution, typed exit reasons, cooperative stop requests and Agent-owned cleanup |
| [`BaseLLMClient`](agents/llm/base_client.py) | `chat`, `close` | Model requests, without taking over Agent history or tool execution |

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
This describes the intended integration contract, not shipped adapters:
external Agent integrations and the end-to-end benchmark runner are not yet
implemented.

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

A Wrapper presents the benchmark-facing [BaseAgent](agents/base_agent.py)
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

[`agents/base_agent.py`](agents/base_agent.py) provides the abstract contract
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

## Model clients

The native [`ToolCallingAgent`](agents/README.md) can use these clients directly.
Its Minecraft VM/ST tests exercise the full observation/tool loop and independently
score native inventory snapshots; the provider checks below test clients alone.

See [the client guide](agents/llm/README.md) for authentication, text/image/tool
examples, retry semantics, live checks and limitations.

```bash
uv sync --locked --group test
uv run --locked --group test python -m pytest tests/test_client -q
```

Live tests are skipped unless explicitly enabled. Only three types of model
checks are retained: text, text with a generated black image, and tool calling.
Actual OpenAI generation requires eligible API quota;
do not assume a ChatGPT account or subscription supplies API credit.

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

Organize tests by the component being checked, not by unit/integration level:

- `tests/test_client/`: supported model clients, using the same three check types.
- `tests/test_game/<game>/`: game basics, VM and ST checks in separate files.
- `tests/test_agent/`: Agent execution, stopping and per-Episode state.
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
