# LiveQuestBench

LiveQuestBench evaluates agents pursuing multi-stage goals in continuously
evolving 3D games: can an agent coordinate immediate actions with longer-term
plans when thinking takes time and resources spent now may be needed later?

The benchmark supports Minecraft and Veloren, a built-in tool-calling baseline,
and external Agent integrations. It is a development benchmark, not a frozen
research release. Qualify tasks and budgets before using them for comparative
research.

## Games and evaluation modes

| Game | Task families | Guide |
| --- | --- | --- |
| Minecraft | Gathering, crafting, construction, navigation, trading and combat expeditions | [Minecraft](game/minecraft/README.md) |
| Veloren | Gathering, crafting, equipment, recovery, navigation, combat and NPC interaction | [Veloren](game/veloren/README.md) |

- **VM (`visual_motor`)**: game pixels, public task instructions and bounded
  keyboard/mouse control. Hidden state is not supplied.
- **ST (`structured_tool`)**: explicitly permitted game state and fixed,
  game-specific tools.

Compare VM and ST separately: both observations and action capabilities differ.
The world progresses during model requests, network waits and tool execution.
Task completion, resource use and the consequences of delay must therefore be
considered together.

## Getting started

Use Linux, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/).
From the repository root:

```bash
uv sync --locked --extra minecraft --extra veloren --group test
```

Prepare the desired game using its guide. Python dependencies alone do not
install a working game:

- Minecraft requires its native runtime and explicit EULA acceptance.
- Veloren requires a prepared matching runtime selected by
  `LIVEQUEST_VELOREN_RUNTIME`.
- Headless sessions use Xvfb; visible sessions require an authorized X11 display.
  Both render the actual game.
- Recording requires FFmpeg.

### Agents

| `agents[].name` | Guide |
| --- | --- |
| `tool_calling` | [Built-in baseline](agent_framework/agents/tool_calling_agent/README.md) |
| `deepseek_harness` | [DeepSeek Harness](agent_framework/agents/deepseek_harness/README.md) |
| `hermes_agent` | [Hermes Agent](agent_framework/agents/hermes/README.md) |
| `orak` | [Orak](agent_framework/agents/orak/README.md) |
| `smolagents` | [smolagents](agent_framework/agents/smolagents/README.md) |
| `gamingagent` | [GamingAgent](agent_framework/agents/gamingagent/README.md) |

Prepare external Agents before running experiments. Each guide describes the
supported profile and installation requirements. Use a unique `agents[].id` for
each configuration you want to compare.

### Model clients

| Provider | Configuration |
| --- | --- |
| `github_copilot` | `COPILOT_GITHUB_TOKEN` or `LIVEQUEST_COPILOT_TOKEN_FILE` |
| `openai` | `OPENAI_API_KEY` |
| `vllm` | A compatible server and `base_url`; optional `VLLM_API_KEY` |

Keep credentials outside experiment YAML and version control. Copilot access
depends on account entitlement and API availability.

The baseline supports all three providers. External Agent profiles require a
Responses-compatible hosted provider and explicit `reasoning_effort`. Choose a
model with tool calling and, for VM, image input support.

## Running an experiment

Choose an experiment from:

- [Minecraft experiments](config/minecraft/experiments/)
- [Veloren experiments](config/veloren/experiments/)

The `all` configurations include the full catalog; `L1`, `L2` and `L3`
configurations select task subsets. Bundled experiments specify six Agents and
**10 repetitions**. Inspect the configuration before launching a large run.

For a smoke test, create a separate experiment with one task and one repetition:

```yaml
id: veloren_smoke
game: veloren
tasks:
  - path: ../tasks/structured_tools/move_2_metres.yaml
repetitions: 1
agents:
  - id: baseline
    name: tool_calling
    model:
      provider: github_copilot
      name: gpt-6-astra
      reasoning_effort: low
      max_output_tokens: 4096
      max_attempts: 3
```

The relative task path assumes the experiment is saved in
`config/veloren/experiments/`. Paths are relative to the YAML declaring them;
absolute paths are also accepted. Select a model available to your account.

Set `EXPERIMENT_CONFIG` to your experiment file and `RESULTS_DIR` to a dedicated
destination, then run:

```bash
uv run --locked --extra minecraft --extra veloren python run_benchmark.py \
  --config "$EXPERIMENT_CONFIG" \
  --output "$RESULTS_DIR" \
  --headless --recording
```

Agents, tasks and repetitions execute serially. Each Episode uses a fresh game
and Agent. The planned count is:

```text
number of Agents × number of tasks × repetitions
```

Model-request retries do not create additional Episodes or reset the world.
The Episode deadline continues during retries.

| Option | Purpose |
| --- | --- |
| `--headless` / `--no-headless` | Use a virtual display or an existing desktop |
| `--recording` / `--no-recording` | Enable or disable video |
| `--recording-fps` | Set video sampling rate, from 1 to 60; default 10 |
| `--record-chat` / `--no-record-chat` | Enable or disable detailed Agent/model transcripts |

Headless mode, video and chat recording are enabled by default. Do not interact
with the controlled display during a run.

Each Agent entry accepts one model configuration. Hosted providers accept
`reasoning_effort`; vLLM instead accepts `base_url`, `temperature` and
`enable_thinking`. Set request limits and task budgets explicitly for comparisons.

## Incremental runs and interrupted experiments

Run the same command again to resume an experiment:

- Completed, valid Episodes are reused, including valid task failures.
- Incomplete Episodes are restarted with a fresh game and Agent.
  **Their existing partial evidence is deleted**; preserve it elsewhere first
  if needed for diagnosis.
- Missing Episodes are run normally.

Changed task, Agent/model or recording settings can cause a configuration
conflict. Use a new result destination or Agent ID for different conditions.
After changing code, runtime or scoring, use a fresh destination even if the
configuration is unchanged.

Only one runner may write to a result destination at a time. Resume does not
restore an interrupted conversation or live game state. After a crash, check
for remaining game/Agent processes before restarting.

A valid task failure does not stop the experiment. Execution, measurement or
cleanup errors stop the invocation and require investigation.

## Reading results

Start with `summary.json` in your chosen result destination, then inspect the
relevant Episode:

| Result | Meaning |
| --- | --- |
| `status: completed`, `measurement: valid` | A usable measurement; `task_outcome` distinguishes success and failure |
| `status: error` | An execution, measurement or cleanup problem; inspect `errors` |
| `cancelled` or `not_run` | Not a completed measurement |

Each Episode retains:

- `results/result.json`: outcome, timing, model usage and execution status.
- `results/evaluation.json`: game-specific scoring details.
- `results/metrics.json`: additional metrics, including native death counts for
  Minecraft and Veloren.
- Initial and terminal snapshots used by the private evaluator.
- Video and Agent/model transcripts when recording is enabled.

Model accounting reports request duration, Token totals returned by the
provider, and unknown usage. Request duration includes service/network waiting;
it is not pure model computation time. Exact monetary cost may be unavailable.
Death counts cover the Episode, not only the final life after respawn.
Progress information depends on the task; do not assume every task has a
complete milestone timeline.

Configuration and provenance records accompany each launch. When reusing
Episodes, consult their originating launch records; the top-level summary
describes the latest invocation, not every experiment ever run in that
destination.

Report infrastructure errors and missing measurements alongside success rates.
Keep VM and ST separate, and consult each game's scoring limits. A video or
Agent completion claim does not replace evaluator evidence.

Before sharing results, review transcripts, environment metadata and native
logs for sensitive information.

## Testing

Run focused offline checks without launching a game or model:

```bash
uv run --locked --extra minecraft --extra veloren --group test python -m pytest \
  tests/test_benchmark -m "not game and not live" -q
```

The game guides provide opt-in native tests. Agent tests additionally require a
configured model and can consume provider quota. A skipped test is not proof of
a working installation.

## Adding tasks and games

### Add a task to an existing game

1. Copy a suitable task YAML into
   `config/<game>/tasks/visual_motor/` or `structured_tools/`.
2. Give it a unique ID, public objective, time budget, fixture and evaluator
   settings. State every success condition in the public objective.
3. For ST, declare the tools needed by the task. Omitted allowlists use the
   game's default profile; native respawn is standard in both current games.
   VM tasks do not accept ST allowlists.
4. Add the task path explicitly to an experiment.
5. Test initial conditions, public observations/actions and private scoring.
   Verify that the goal is achievable through the admitted controls.

Keep source fixtures immutable. Use event evidence when the objective depends
on order or intermediate achievements; final inventory or position alone
cannot establish those facts. Qualify each supported mode separately.

### Add a game

Use [BaseGame](game/base_game.py) and [GameBinding](game/bindings.py) as the
integration contracts:

1. Add a game package and a guide covering installation, supported modes,
   controls, fixtures and scoring.
2. Implement startup, begin/end, snapshots and cleanup. Document whether the
   world continues during reasoning and after control ends.
3. Expose only the permitted observations and actions to Agents. Keep
   administrative controls and scoring evidence private.
4. Supply task-independent instructions under `game/<name>/prompts/`.
5. Register the game in [the experiment factory](benchmark/factory.py).
6. Add tasks and tests covering initialization, real interaction, deadlines,
   scoring, recording and cleanup.

Reject unsupported configurations explicitly rather than substituting a
different observation or control mode.

## Agent integration

### Add an Agent

Create a package under `agent_framework/agents/<name>/` and implement
[BaseAgent](agent_framework/agents/base_agent.py). The
[built-in baseline](agent_framework/agents/tool_calling_agent/README.md) provides
a small reference. External runtimes can use
[ProcessAgent](agent_framework/agents/process_agent.py).

### Python lifecycle contract

- `run(context)` executes the Agent using the supplied task, instructions,
  public interface and budget.
- `stop(reason)` responds to cancellation and deadlines.
- `close()` releases Agent-owned resources.
- Return an `AgentExit`; task success is decided by the private evaluator.

Register the Agent in [the experiment factory](benchmark/factory.py), document
its setup and supported settings, and add an experiment entry. Preserve an
external Agent's decision process rather than replacing it with the baseline.
Disclose memory, model calls and additional computation used by the profile.

### Shared process integration

Install external Agents into dedicated checkouts using their setup commands.
Prepared source must match the declared revision and patches. Select it through
the documented environment variable; dependencies are not installed during
Episodes.

Agents receive public observations and admitted tools, not administrative game
handles or evaluator state. External integrations are not an OS security sandbox:
run trusted code in an appropriately isolated environment.

### Agent validation

First validate installation and offline lifecycle behavior. Then run a small
native task in every supported mode, checking model calls, actual game actions,
deadline/operator stop, result recording and cleanup.

Follow the selected Agent's guide for targeted test commands. A valid task
failure can still demonstrate correct integration, but an execution failure
must not be relabeled as model weakness.

## Repository guide

| Directory | Purpose |
| --- | --- |
| [config/](config/) | Tasks, fixtures and experiments |
| [game/](game/) | Game integrations |
| [agent_framework/](agent_framework/) | Agents and model providers |
| [benchmark/](benchmark/) | Experiment execution and results |
| [tests/](tests/) | Offline and opt-in integration tests |

## Licensing and responsible use

Framework, Agent, game and asset licenses are separate. Follow the game/Agent
guides and retained license notices before using or redistributing components.
Do not commit credentials or redistribute game binaries/assets without the
necessary rights. Offline game authentication does not waive licensing terms.
