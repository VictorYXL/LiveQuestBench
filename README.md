# LiveQuestBench

LiveQuestBench is an early-stage benchmark project for agents pursuing
long-horizon objectives in continuously evolving 3D games. The intended focus is
the interaction between immediate reaction, persistent resources and decisions
whose consequences affect later stages.

**Current status: Python scaffold with working model clients, not a runnable game
benchmark.** GitHub Copilot and OpenAI Responses clients are implemented. Copilot
has passed small live text, image and tool-roundtrip checks; OpenAI is covered by
offline protocol tests, not a live generation. There is no connected game, Agent
implementation, configuration loader, Episode runner or score-producing launcher
yet. These checks are not game benchmark results.

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
FFmpeg, X11 setup or game assets. Future per-game setup scripts handle explicit
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
    setup/
    guide/
    evaluators/
    structured_tools/
      actions/
      observations/
      tools/
agents/
  base_agent.py             Autonomous per-Episode Agent contract
  reference/                Future first-party reference Agent
  adapters/                 Future external Agent adapters
  llm/
    base_client.py          Message/response types and model client contract
    README.md               Provider usage and validation instructions
    providers/
      responses.py          Shared multimodal/tool Responses protocol
      github_copilot_client.py
      openai_client.py
core/                       Future orchestration and shared infrastructure
tests/
  core/                     Offline model-client checks
  integration/              Explicit opt-in live model checks
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
| [`BaseGame`](game/base_game.py) | `start`, `get_agent_interface`, `save_snapshot`, `close` | One game session, public interaction handle and private evidence acquisition |
| [`BaseAgent`](agents/base_agent.py) | `run`, `stop` | Autonomous execution using public task text and the permitted handle |
| [`BaseLLMClient`](agents/llm/base_client.py) | `chat`, `close` | Model requests, without taking over Agent history or tool execution |

Game configuration and fixture selection belong to concrete constructors for now.
`start()` initializes a fresh session; a reusable reset operation, measured-start
control and exact snapshot receipts will be added only as the first integration
establishes their requirements. No universal world serializer or session-reuse
policy is implemented.

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
providers. The two implemented providers share Responses serialization and
per-attempt usage callbacks; missing usage is never treated as zero. Aggregate
costs and Episode-level accounting remain future work.

Game and Agent operations remain abstract. The model base now implements the
common request lifecycle and requires provider-specific request/cleanup methods.
There are no no-op concrete games, agents or model clients.

## Model clients

See [the client guide](agents/llm/README.md) for authentication, text/image/tool
examples, retry semantics, live checks and limitations.

```bash
uv sync --locked --group test
uv run --locked --group test python -m pytest tests/core tests/integration -q
```

Live tests are skipped unless explicitly enabled. OpenAI offline tests do not
need an API key or balance. Actual OpenAI generation requires eligible API quota;
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

When real behavior is added, organize checks under `tests/core/`, `tests/game/`
and explicitly selected `tests/integration/` as needed. Do not create a large mock
framework or mirror every source module. The initial abstract scaffold has no
per-method unit suite.

Fast checks must not launch games, modify display sessions or make paid model
requests. Native game smoke checks are separate and opt-in. Import/syntax checks
do not qualify real gameplay, timing, reset, scoring or provider compatibility.

## Design record

The development workspace contains a longer discussion archive at
`output/survey/design.md`. That directory is currently Git-ignored, so this
README is the tracked-facing starting point; a fresh clone should not assume the
local archive exists. Research hypotheses and proposed protocols must not be
presented as implemented or independently validated behavior.
