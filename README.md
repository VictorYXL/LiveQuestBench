# LiveQuestBench

LiveQuestBench is an early-stage benchmark project for agents pursuing
long-horizon objectives in continuously evolving 3D games. The intended focus is
the interaction between immediate reaction, persistent resources and decisions
whose consequences affect later stages.

**Current status: an executable serial benchmark framework, six Agent integrations
and Minecraft/Veloren VM/ST; not a frozen research benchmark.** GitHub Copilot, OpenAI Responses
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
The Agents use game-owned, mode-local tool/observation bindings and real-game
acceptance tests. Veloren has the same lifecycle shape, actual screenshot plus
atomic keyboard/mouse VM, fixed native-tool ST, and private endpoint evaluators.
Its world continues after public input is revoked: its endpoint evidence is not
an atomic server save. See [Veloren setup and scope](game/veloren/README.md).
The [Veloren acceptance record](output/survey/veloren_integration_20261022.md)
documents 13 real model/game cases and the native input/skill checks.
See the [Orak](agent_framework/agents/orak/README.md) and
[smolagents](agent_framework/agents/smolagents/README.md) profiles for setup and
fidelity boundaries, and the [live acceptance report](output/survey/additional_agent_integrations_20261022.md)
for the earlier twelve-case evidence and deferred Game Agent candidates.
See [GamingAgent](agent_framework/agents/gamingagent/README.md) for its
native-image profile and real validation command, and the
[Game Agent follow-up](output/survey/game_agent_followup_20261022.md) for
refreshed candidate evidence and integration results.
The file-based configuration loader, production Episode runner and
[`run_benchmark.py`](run_benchmark.py) launcher execute independent tasks and
persist private evidence, traces, scores and mode-separated summaries.
The small built-in tasks are integration examples, not evidence of long-horizon
task coverage or a finalized evaluation distribution.

## Development setup

The initial development target is Linux with Python 3.11, matching the minimum
declared by the existing Minecraft projects. Python metadata permits newer
versions, but game/Agent combinations must be checked before claiming support.
Veloren's existing harness runs in its separately verified Python 3.13 runtime.
The benchmark-facing process remains Python 3.11; the integration does not raise
the project's minimum or imply certification of every interpreter/game combination.

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
    fixtures/               Immutable native worlds shared by VM/ST
    tasks/visual_motor/     Visual-motor task definitions
    tasks/structured_tools/ Structured-tool task definitions
    experiments/            Task/Agent/settings selections
  veloren/
    fixtures/               Immutable native map and upstream license
    tasks/visual_motor/
    tasks/structured_tools/
    experiments/
game/
  base_game.py              Minimal administrative game contract
  bindings.py               Shared public controls and private Episode bindings
  backends/x11/             Shared input, capture, recording and isolated display
  minecraft/
    README.md
    setup.sh
    game.py
    binding.py              Minecraft fixture/tool admission and private scoring
    runtime/                Installation, accounts and client/server lifecycle
    init_player_state.py    Private initial player state and verification
    prompts/                introduction.txt plus visual_motor.txt / structured_tool.txt
    evaluators/
    visual_motor/
    structured_tools/
      interface.py          Public observations, fixed tools and native execution
  veloren/
    README.md
    setup.sh
    game.py
    binding.py              Veloren fixture/tool admission and private scoring
    fixture.py              Explicit native scene initialization and readback
    runtime/                Verified upstream reuse, native patch build and private worker
    patches/                Explicit physical-input opt-in; native license
    prompts/
    evaluators/             Private displacement, inventory and health endpoints
    visual_motor/           Shared atomic X11 binding
    structured_tools/       Explicit observation projection and fixed native skills
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
benchmark/                  Experiment orchestration and result persistence
  config.py                 Strict, explicit file-based Task/Experiment loading
  factory.py                Explicit game, Agent and model selection
  runner.py                 Serial lifecycle, deadline, interruption and cleanup
  results.py                Evidence logging, provenance and mode-separated summaries
tests/
  conftest.py               Shared display and recording options
  test_benchmark.py         Consequential offline configuration/lifecycle checks
  test_benchmark_live.py    Opt-in real CLI/native Agent/deadline/SIGINT checks
  test_agent/
    test_agents_minecraft.py  Real Minecraft/model acceptance and operator-stop cases
    test_agents_veloren.py    Real Veloren/model acceptance and operator-stop case
    support.py               Re-exports the production roster and bounded runner
  test_client/              Three opt-in checks per provider: text, image, tools
  test_game/
    minecraft/
      test_game.py          Installation, world isolation, snapshots and recording
      test_vm.py            Pixels and basic motor actions
      test_st.py            Structured state, tools and cancellation
      test_structure.py     Native construction scoring and consequential counterexamples
    veloren/
      test_game.py          Real VM/ST movement, cutoff, snapshots and recording
      test_evaluators.py    Threshold and evidence-integrity counterexamples
pyproject.toml
run_benchmark.py             Thin operational launcher
uv.lock
.python-version
README.md
```

## Running an experiment

The four experiments under [`config/`](config/) separate Minecraft/Veloren and
VM/ST. Each explicitly lists all tasks for its game and mode, with **10
repetitions per task per Agent configuration**. Minecraft has 11 migrated island
tasks plus `collect_3_logs`; Veloren has 10 endpoint adaptations plus
`move_2_metres`. See the [Minecraft README](game/minecraft/README.md) and
[Veloren README](game/veloren/README.md#task-catalog) for provenance and scope.
These new tasks are statically checked development configurations, **not
native-qualified results**. Prepare runtimes and credentials before execution.

Task references accept absolute paths or paths relative to the declaring
experiment file, with no implicit name lookup. Each task declares `task_type`;
experiments do not override it. ST `tools` lists select public Agent tools;
omitting the list means all supported public ST Agent tools, not administrative
operations. VM observations remain on demand, without a task-level capture
interval. Recording cadence is independent.

An experiment is a task execution plan shared by an explicit `agents` list.
Every entry has a unique `id`, an Agent implementation `name`, and its own
`model` settings. Results identify the Agent configuration as well as game,
task ID and `task_type`; VM/ST and different Agent scores remain separate.
Unsupported Agent/task combinations must be
rejected before execution, not silently skipped.

```yaml
agents:
  - id: tool_calling_astra
    name: tool_calling
    model:
      provider: github_copilot
      name: gpt-6-astra
      reasoning_effort: low
      max_output_tokens: 4096
      max_attempts: 3
```

To compare another model or Agent, add another complete entry with a distinct
ID. Entries run serially, not concurrently. Scheduled Episodes equal
`len(agents) * len(tasks) * repetitions`; request `max_attempts` does not add
Episodes. Currently each entry uses one model. Model settings belong to the
Agent so future role-specific multi-model implementations can extend this
boundary without a global model or an implicit Agent/model Cartesian product.
Legacy top-level `agent`/`model` keys are rejected; move them into an entry and
give it an explicit ID.

From the repository root:

```bash
uv sync --locked --extra minecraft --extra veloren
uv run --locked --extra minecraft --extra veloren python run_benchmark.py \
  --config config/minecraft/experiments/visual_motor_all.yaml \
  --output output/runs/minecraft_visual_motor_all \
  --headless --recording
```

For Veloren, use `config/veloren/experiments/visual_motor_all.yaml` and a separate
output directory. Select explicit task paths to create a custom experiment.
Provider credentials and prepared game runtime locations remain external to the
task configuration. Copilot accepts `COPILOT_GITHUB_TOKEN` or the explicit
`LIVEQUEST_COPILOT_TOKEN_FILE`; OpenAI uses `OPENAI_API_KEY`. Veloren requires
`LIVEQUEST_VELOREN_RUNTIME`; Minecraft requires explicit
`MINECRAFT_EULA_ACCEPTED=true` and an installed runtime.
External Agents retain their documented `LIVEQUEST_<AGENT>_ROOT` setup.

The launcher defaults to headless execution without recording. Use
`--no-headless` for an authorized existing X11 desktop, `--recording` for video
and `--recording-fps N` for 1-60 FPS. Rendering and on-demand VM observations
remain enabled without recording. These options do not override task or model
settings.

### Configuration and admission

- Agents run in explicit list order; within each Agent, tasks run in list order,
  with all repetitions of each task in order.
  Every Episode gets a fresh game session and Agent. There is no task discovery,
  task registry, inheritance, automatic Episode retry, concurrency or resume.
- YAML duplicate/unknown keys, invalid types, conflicting task identities,
  unsupported tools/evaluators and invalid scorer thresholds are rejected.
  Paths are absolute or relative to the declaring file, including Minecraft
  fixture directories relative to their Task YAML.
- `agents[].name` is `tool_calling`, `deepseek_harness`, `hermes_agent`, `orak`, `smolagents` or
  `gamingagent`. Native process profiles currently require a Responses provider
  and explicit `reasoning_effort`; vLLM is supported with `tool_calling`.
  Names follow upstream project spelling, lowercased with spaces/hyphens changed
  to underscores: **GamingAgent** is `gamingagent` (no separator upstream),
  **Hermes Agent** is `hermes_agent`, and **DeepSeek Harness** is
  `deepseek_harness`. The former short names `hermes` and `deepseek` are no
  longer configuration identifiers. Runtime environment variable names stay
  unchanged.
- Per-Agent `model` settings: `provider`, `name`, optional `reasoning_effort`,
  `max_output_tokens` (4096), `max_attempts` (3), `timeout_seconds` (120).
  Only vLLM additionally accepts `base_url`, `temperature`, `enable_thinking`;
  it rejects `reasoning_effort`. Inapplicable settings are not silently dropped.
- Every Task requires an explicit top-level `fixture` mapping. There is no
  `initialization` wrapper, null/default fixture, implicit world generation,
  named scene lookup or arbitrary setup-command list.
- Minecraft fixtures require `world_path`, `instance` (currently `"1.20.4"`),
  `difficulty` and `player_state`. `world_path` is a native save directory,
  absolute or relative to the Task YAML. The save must exist, contain
  `level.dat`, have no saved players and no symlinks. The loader copies it
  into a fresh Episode directory, then installs and verifies the declared player.
  Both integration tasks share [`config/minecraft/fixtures/collect_3_logs`](config/minecraft/fixtures/collect_3_logs/).
  This approximately 2.2 MB template already contains the three logs; no
  runtime `fill` is needed. It is a generated superflat task scene, not the
  upstream island map. Its export provenance and native-file checksums are in
  [`collect_3_logs.source.json`](config/minecraft/fixtures/collect_3_logs.source.json).
- Veloren fixtures combine explicit `world_path`, `world_seed`, `time_of_day`,
  `day_length`, `calendar`, absolute `platform` geometry and `player_state`.
  The game-side [`initialize_fixture`](game/veloren/fixture.py) authors the
  declared platform, establishes position/health/inventory, verifies equipment
  and initial look, and rejects a mismatched native readback.
  The map is a bundled native file in
  [`config/veloren/fixtures`](config/veloren/fixtures/), not an installed asset
  lookup or hidden world-generation preset. Paths resolve relative to the Task
  YAML or may be absolute; its actual file hash is recorded. The unmodified map
  retains its upstream GPLv3 license and includes source/checksum provenance.
  Calendar-driven holidays are disabled explicitly with `calendar: none`.
  There is no relative-to-spawn platform placement.
- Veloren's current loader supports Rock platforms, initial look `[0, 1, 0]`,
  positive health up to 100 and native simple-item inventory counts. Equipment
  is an exact admission requirement against the pinned ordinary-character
  loadout, not an arbitrary equipment editor. Unsupported values fail rather
  than being substituted. Changed inventories are rebuilt using the existing
  native cleanup/gift helpers; discarded supplies are dropped away from the
  scene, as documented by those helpers.
- A fixture defines authored initial conditions for a pinned game/runtime.
  It does not promise bitwise simulation replay. Veloren has native map files,
  but those are not complete ECS/character/world snapshots. This implementation
  deliberately combines map plus explicit initialization fields; it does not
  claim complete save-state restoration. Incidental IDs, setup ticks, ambient
  simulation and post-start trajectories can differ.
- Evaluators remain game-owned: Minecraft `inventory` and `structure`;
  Veloren `displacement`, `inventory` and `health`.
  `evaluator.parameters` contains the evaluator's named parameters, excluding
  private evidence paths and player identity. For Minecraft structure, that
  means a `config` mapping containing `target`, `region` and optional match settings.

### Boundaries, outputs and failures

The runner initializes and verifies the scene, saves before evidence, binds
public controls and creates the Agent before opening play. The monotonic
deadline starts immediately before `begin()`; its acknowledgement/recording
startup consumes that budget. During reasoning and model/network waits, the
world continues. At Agent return, deadline or SIGINT, the runner requests
game access revocation **before** stopping/joining the Agent. Final evidence and
evaluation precede resource cleanup. Retirement and cleanup waits are bounded;
failures remain explicit. A second forced termination or machine failure cannot
guarantee cleanup or a finalized summary.

Minecraft acknowledges a world freeze at its endpoint. Veloren revokes inputs
but its world continues until the native endpoint capture. Neither the runner
nor its clock timestamps turn Veloren evidence into an atomic server snapshot.
Results retain requested/acknowledged boundaries and host monotonic timing;
they do not claim a zero-latency real-time cutoff.

`--output` must name a **new directory**. Existing output is never overwritten,
including a previous admission failure. The output includes:

- `config.json`: resolved configurations, original YAML text, source paths and hashes.
- `provenance.json` and `launch.json`: repository revision/dirty state, implementation
  hashes, Python/package versions and operational settings. Native game/Agent
  receipts remain alongside their execution evidence.
- One `<agent-id>--<game>--<task-id>--<task_type>--<repetition>` directory per started Episode,
  containing `result.json`, before/after snapshots, `evaluation.json` when valid,
  `trace.jsonl`, deduplicated VM images, native logs and optional game video.
- `summary.json`: every scheduled Episode, including errors and unstarted cases,
  plus separate groups for each Agent/game/task/mode. Every planned Episode
  records its Agent ID and resolved model settings. No combined VM/ST or
  cross-Agent score is emitted.

The private trace retains public observations, messages/provider state, tools
and model request attempts, but is never supplied wholesale to the Agent.
Token usage reports known sums **and unknown-attempt counts**; missing usage
and monetary cost remain unknown, not zero. No price estimator is implemented.

`result.status` separates `completed`, `error` and `cancelled`;
`measurement` separates `valid`, `invalid` and `unavailable`;
`task_outcome` is `success`, `failure` or `unknown`. Agent exit is an independent
field. Admission failures have experiment status `admission_error`.
The runner stops scheduling after an execution/measurement/cleanup error, marks
remaining Episodes `not_run`, and preserves earlier evidence. A normal
unsuccessful task or deadline is **not** an infrastructure error and does not
stop subsequent tasks. Valid-completed success rates explicitly report their
denominator alongside all scheduled statuses.

CLI exit codes: **0** for completed execution, even with unsuccessful tasks;
**1** for admission/execution/measurement/cleanup failure; **130** for SIGINT.
There is no automatic game-terminal detector beyond native Agent return and
the current game gates; no pricing, parallel scheduling or sandbox for untrusted
Agent implementations is claimed.

### Runner validation

After installing the `test` dependency group:

```bash
.venv/bin/python -m pytest tests/test_benchmark.py -q
```

The opt-in CLI lifecycle checks require prepared Veloren, DeepSeek and Copilot
credentials, retain their configurations/results under `output/test/benchmark-*`,
and exercise a native Agent, a scored deadline and a real SIGINT:

```bash
LIVEQUEST_BENCHMARK_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
  .venv/bin/python -m pytest tests/test_benchmark_live.py -q --headless --recording
```

Create directories when they contain actual implementation or resources; do not
retain empty scaffolding with `.gitkeep` files. Fixture directories contain
actual resources; parameter-defined scenes can remain directly in Task YAML.

The four business directories have distinct ownership:

- **config:** what to evaluate, under which conditions and with which fixtures.
- **game:** how to launch/interact with a game and acquire/interpret its evidence.
- **agent_framework:** Agent execution, model clients and shared integration utilities.
- **benchmark:** when to initialize, run, terminate, score and clean up an Episode.

[`runner.py`](benchmark/runner.py) keeps `run_experiment`, `run_episode` and
their bounded Agent execution helper together. Experiment scheduling and single-
Episode lifecycle are separate functions, not separate frameworks.
[`factory.py`](benchmark/factory.py) selects existing implementations; each
game's `binding.py` owns fixture validation, allowed tools, evaluator selection
and private evidence wiring. Game modules do not import benchmark configuration
or orchestration. Initialization finishes inside `game.start()`; there is no
empty secondary `prepare` hook.

The shared [`game/backends/x11`](game/backends/x11/) is used by both games, not
by the scheduler directly. VM uses its capture/input tools; both VM and ST use
its display and optional recording infrastructure. It is not a plugin registry
and does not expose administrative game handles to Agents.

Task-specific fixture assets belong with evaluation configuration conceptually,
even when stored externally by version/hash. Keep templates immutable and create
writable per-Episode state separately. Game binaries and unlicensed assets must
not be committed.

## Provisional base interfaces

These are small starting contracts, not a frozen public API.

| Base | Operations | Responsibility |
| --- | --- | --- |
| [`BaseGame`](game/base_game.py) | `start`, `begin`, `end`, `get_agent_interface`, `get_instructions`, `save_snapshot`, `close` | One game session, public interaction handle and private evidence acquisition |
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

Agents own their reasoning/observation/action loops. The runner owns
lifecycle and budgets, initializes a fresh Agent per Episode and coordinates
termination with evidence capture. Returning from `run()` is not a successful
score. Stopping an Agent does not stop world evolution, and closing a connection
too early can prevent final evidence acquisition.

The LLM message fields follow the existing Minecraft client's conventions,
including multimodal/tool content and provider state. `LLMResponse` is an initial
typed container, not a drop-in guarantee for existing dictionary-returning
providers. The two hosted providers share Responses serialization and
per-attempt usage callbacks; missing usage is never treated as zero.
The runner persists Episode-level request/usage accounting; monetary pricing
remains unimplemented.

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
support for arbitrary upstream features or other Agents. The production runner
uses these same integrations without replacing their native loops.

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
timestamps appropriately. The runner/game gate, not this abstract class,
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

`tests/test_agent/test_agents_minecraft.py` contains **only real-time game tests using
a live model**: six Agents times two Minecraft modes, plus four operator-stop
cases for the new native workers. It contains no scripted
model responses, fake game interfaces or unit checks. Without explicit opt-in,
all fifteen cases skip; that is not a passing Agent validation.

To inspect the cases without running them:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py --collect-only -q
```

Prepare the pinned runtimes using each Agent's README. Missing runtimes are
explicit skips, not evidence of successful integration. The former `external`
marker and `LIVEQUEST_EXTERNAL_TEST` flag have been removed along with the
simulated/native-offline Agent checks.

The twelve-case Minecraft matrix combines `tool_calling`, `deepseek_harness`, `hermes_agent`,
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
  tests/test_agent/test_agents_minecraft.py -m game -q -s --headless --recording
```

Use `-k tool_calling`, `-k deepseek`, `-k hermes`, `-k orak`, `-k smolagents`
or `-k gamingagent` to select an Agent. `-k stop` selects all four operator-stop cases.
`--no-recording` disables video/decoding, not observations or snapshots.
`--no-headless` uses a dedicated existing X11 desktop.
Credentials are never discovered in other repositories; no substitute model
is chosen if the requested one is unavailable. These checks consume quota.

The corresponding Veloren suite is `tests/test_agent/test_agents_veloren.py`.
It uses the same six Agents and model settings with a small displacement task,
plus intentional DeepSeek and GamingAgent ST stops. Prepare the native runtime and set
`LIVEQUEST_VELOREN_RUNTIME` and `LIVEQUEST_VELOREN_TEST=1` as described in
[the game README](game/veloren/README.md), then run:

```bash
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_agent/test_agents_veloren.py -q -s --headless --recording
```

Veloren's budget starts after `begin()` acknowledges input admission.
Its native counter measures variable-duration client updates, not fixed-rate
server ticks. Task failure does not fail acceptance if actual model/game exchange,
deadline/operator control and cleanup remain correct; transport, fixture and
adapter errors do fail acceptance.

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
- `max_attempts=3` means at most three total attempts per model request, with
  exponential backoff. Retries cover network/timeouts, remote protocol errors,
  streams ending without a terminal response, incomplete/token-truncated output,
  JSON decoding failures (including tool arguments), and HTTP 408/429/500/502/503/504,
  except known quota/billing limits. Set one to disable retries.
- Following GameAgentVisual's request-resend policy, other model-output failures
  (empty responses, valid JSON with the wrong shape, invalid tool calls) are not
  retried. Authentication/configuration failures and cancellation are
  not retried either. This policy applies to the shared client, not automatically
  to external Agents' own transports.
- The world and Episode deadline continue during retries; only the model request
  is repeated, never an executed game action or an entire Episode. Every attempt
  is recorded. Remote completion/cost after a timeout or disconnect may be
  unknown, and retrying may incur duplicate inference/billing. Cancellation
  propagates but cannot guarantee remote inference/billing stops.
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
5. Expand the small Veloren integration task into representative long-horizon
   tasks after calibrating native timing, observation scope and endpoint evidence.
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
successful gameplay sample. Current checks cover immutable world-copy/native
inventory evidence, refusal to start without explicit EULA consent, and structure
scoring counterexamples with incomplete/corrupt saved evidence, plus Veloren
endpoint thresholds and evidence integrity. Structure scoring
also has a real native placement test; no model is needed to validate a scorer.
Removed tests must not be relocated into
new files simply to retain a large suite; avoid assertions that just repeat
dataclass fields, enum values, schema literals or trivial constructor behavior.

Organize tests by the component being checked, not by unit/integration level:

- `tests/test_client/`: supported model clients, using the same three check types.
- `tests/test_game/<game>/`: game basics, VM/ST checks and evaluator validation.
- `tests/test_agent/`: real-time game/model runs and independently scored outcomes.
- `tests/test_benchmark/`: Episode orchestration, configuration, evaluator
  invocation and result persistence.

Current test directories are `test_client`, `test_agent`, `test_game/minecraft`
and `test_game/veloren`. Pytest uses `--import-mode=importlib` so same-named test
modules in different game directories can be collected together.
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
