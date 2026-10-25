# LiveQuestBench

LiveQuestBench evaluates agents pursuing multi-stage goals in continuously
evolving 3D games: can an agent coordinate immediate actions with longer-term
plans when thinking takes time and resources spent now may be needed later?

**Status: an executable development benchmark, not a frozen research release.**
Minecraft and Veloren, six Agent implementations, and three model providers
are integrated. Engineering checks include recorded native runs and offline
regressions. Coverage is configuration/runtime-specific: earlier integration runs
do not certify every new task, and reference-behavior qualification and budget
calibration remain necessary before scientific evaluation.

## Games and evaluation modes

| Game | Current catalog per mode | Setup and task details |
| --- | --- | --- |
| Minecraft | 31 entries: 10 objectives each in L1-L3 and one exploratory L4 objective | [Minecraft README](game/minecraft/README.md) |
| Veloren | 30 entries: 10 objectives each in L1-L3 | [Veloren README](game/veloren/README.md) |

- **VM (`visual_motor`)**: actual game pixels and bounded keyboard/mouse control.
  No hidden inventory transcription or object coordinates are supplied.
- **ST (`structured_tool`)**: explicitly permitted native state and fixed tools.
  The tools and sensing permissions are documented by each game.

Report VM and ST separately: they change both observations and action
capabilities. Scores are not a pure comparison of visual reasoning.
Historical entry coupled tasks have recorded Baseline runs in both modes and
successful public-tool reference trajectories. After native difficulty/armor
and courtyard adjustments, entry Baselines succeeded in Minecraft ST and
Veloren VM; the other two modes failed. Multi-encounter extensions add finite
resupply/cargo or gathering prerequisites. Minecraft's two-outpost Baseline
succeeded in ST and failed in VM. Veloren's two-enemy Baselines failed despite
successful public-control references; that task remains a challenging
development candidate, not a calibrated medium tier. One targeted Hermes ST
run succeeded. These checks do
not establish stable difficulty or complete the proposed NPC/Boss ladder.
Temporary qualification subsets belong under
`output/temp/`; production experiments provide each mode's `all` catalog and
accepted level subsets such as `structured_tools_L1.yaml` and `visual_motor_L1.yaml`.
The current catalog includes native villager trading, crafting, resource retention, construction,
navigation, recovery and native combat. Small diagnostics and overlapping variants are not
independent long-horizon capabilities; a raw catalog average is not a balanced
research leaderboard. One executable task YAML counts as one task: the catalog
contains 122 active tasks (62 Minecraft and 60 Veloren). Redundant or nested
diagnostics were retired from the active catalogs without changing historical
results. Minecraft's retained short reconnaissance condition contributes two
task YAMLs; it does not meet the intended long-horizon L4 admission gate.
The paired Minecraft lost-expedition tasks have Baseline and evidence-backed
feasibility checks, with no observed full success. They are development L4
tasks, not a calibrated difficulty tier.

## Getting started

Use Linux and Python 3.11 or newer. Install the project dependencies:

```bash
uv sync --locked --extra minecraft --extra veloren --group test
```

Then prepare the games using their READMEs. Python dependencies alone do not
install a working game runtime.

- Minecraft requires its prepared native client/runtime and explicit
  `MINECRAFT_EULA_ACCEPTED=true`.
- Veloren requires its prepared matching runtime and
  `LIVEQUEST_VELOREN_RUNTIME` pointing to the generated runtime JSON.
- Headless operation uses a virtual X11 display. Desktop operation needs an
  authorized existing display. Both modes still render the game.
- Recording requires FFmpeg; native rendering requires the dependencies
  documented by the game.

### Agents

| `agents[].name` | Implementation and installation |
| --- | --- |
| `tool_calling` | [Built-in tool-calling baseline](agent_framework/agents/tool_calling_agent/README.md) |
| `deepseek_harness` | [DeepSeek Harness](agent_framework/agents/deepseek_harness/README.md) |
| `hermes_agent` | [Hermes Agent](agent_framework/agents/hermes/README.md) |
| `orak` | [Orak](agent_framework/agents/orak/README.md) |
| `smolagents` | [smolagents](agent_framework/agents/smolagents/README.md) |
| `gamingagent` | [GamingAgent](agent_framework/agents/gamingagent/README.md) |

External Agents need their separately prepared, pinned runtimes. Their README
documents supported execution paths, patches and differences from upstream.
These integrations preserve native Agent loops; they are not claims to
reproduce upstream benchmark scores.

Names follow upstream spelling, lowercased with spaces/hyphens represented by
underscores. GamingAgent is one word, so its identifier is `gamingagent`.
Use a unique `agents[].id` to distinguish different settings of the same Agent.

### Model clients

| Provider | Required configuration |
| --- | --- |
| `github_copilot` | `COPILOT_GITHUB_TOKEN` or explicit `LIVEQUEST_COPILOT_TOKEN_FILE` |
| `openai` | `OPENAI_API_KEY` |
| `vllm` | A separately running compatible server and `base_url`; optional `VLLM_API_KEY` |

Never put credentials in experiment YAML or commit them. Copilot uses direct
Responses requests, not an SDK Agent session; availability depends on account
entitlement and upstream API behavior. Hosted providers use Responses;
vLLM uses Chat Completions.

The baseline supports all three providers. Current external process profiles
require a Responses provider and explicit `reasoning_effort`.
For VM, choose a model that accepts images; ST still requires tool calling.

## Running an experiment

The full-catalog experiments are:

- [Minecraft VM](config/minecraft/experiments/visual_motor_all.yaml)
- [Minecraft ST](config/minecraft/experiments/structured_tools_all.yaml)
- [Veloren VM](config/veloren/experiments/visual_motor_all.yaml)
- [Veloren ST](config/veloren/experiments/structured_tools_all.yaml)

Each lists all tasks for its game/mode with **10 repetitions**.
The full catalogs and paired `L1`/`L2`/`L3` subsets for both games list all six supported Agents
with GPT-6-Astra.
These are development sweep configurations, not claims that the full all-Agent
campaign has run. Level acceptance uses separate one-repetition Baseline runs.
For a quick check, make a separate experiment with fewer representative tasks,
`repetitions: 1` and appropriate task budgets.

```yaml
id: veloren_smoke
game: veloren
tasks:
  - path: ../tasks/structured_tools/move_2_metres.yaml
repetitions: 1
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

The example's task path assumes an experiment in
`config/veloren/experiments/`. References are relative to the declaring YAML,
or absolute; moving a YAML does not automatically fix its relative paths.

```bash
uv run --locked --extra minecraft --extra veloren python run_benchmark.py \
  --config config/veloren/experiments/structured_tools_all.yaml \
  --output world/20261023.smoke \
  --headless --recording
```

Agents, tasks and repetitions execute **serially**, in their listed order.
Every executed Episode gets a fresh game and Agent. The planned count is:

```text
number of Agents × number of tasks × repetitions
```

Model-request `max_attempts` does not create extra Episodes. Each Agent entry
currently has one `model`; internal multi-model cooperation is not implemented.
Legacy top-level `agent` and `model` settings are not accepted.

Useful options:

- `--headless` (default) or `--no-headless` for an existing display.
- `--recording` (default) or `--no-recording` to disable video.
- `--recording-fps 10` (default), supported range 1-60.
- `--record-chat` (default) or `--no-record-chat` to disable benchmark chat
  and detailed execution recording. This is independent of video recording.

Model settings default to `max_output_tokens: 4096`, `max_attempts: 3` and
`timeout_seconds: 120`. Hosted providers optionally accept `reasoning_effort`.
Only vLLM accepts `base_url`, `temperature` and `enable_thinking`; it does not
accept `reasoning_effort`.

Transient network/service failures, incomplete generations and JSON decoding
failures may resend the same request, up to the attempt limit. Empty responses,
other invalid response shapes, explicit quota exhaustion and cancellation are
not automatically retried. Retries do not replay game actions or reset the
world; the Episode deadline continues. Unknown token usage/cost stays unknown.

## Incremental runs and interrupted experiments

You can run the same command again or run different experiment files serially
against the same output root. The decision is made **per Episode**:

1. **Completed valid evaluation:** reuse it, including a valid task failure.
2. **Existing incomplete Episode:** delete that Episode directory and rerun
   from a fresh game and Agent. Partial logs/video in that directory are lost.
3. **No Episode directory:** run normally.

A completed evaluation means consistent `results/result.json` and
`results/evaluation.json`, with completed measurement and cleanup.
New Minecraft and Veloren runs also save independent private death accounting in
`results/metrics.json` and `result.json.metrics`. Counts span the initial and
terminal snapshots, not a new life after respawn; they do not change task success.
Minecraft uses native death-statistic differences; Veloren retains identity-bound
native death events and server timestamps. Missing evidence is an error, not zero.
Merely having `results/result.json` is not enough: it also exists during
execution and after errors. Corrupt/inconsistent
completed evidence raises an error instead of silently being accepted.
Legacy root-level result files remain readable, but outputs predating chat
recording have incompatible fingerprints and require a new output root or
Agent ID. Existing evidence is not migrated or overwritten.

The runner checks the saved task, Agent/model and launch settings before
reusing or replacing an existing result. If they differ, it stops with a
configuration conflict: use a new output root or Agent ID. Older outputs
without the new configuration fingerprint also require a new output root.
Changing repetitions or selecting additional tasks does not invalidate already
completed matching Episodes.

Only one runner may write to an output root at a time. Different experiment
files retain separate launch records under `runs/`; the root-level metadata
shows the **latest invocation**, not an aggregate across all eight or more
experiment files. Episode results remain under their Agent/task directories.
Use distinct task IDs across games if sharing a root; a same-path configuration
conflict is rejected, never merged.

For SSH disconnects, run the serial launcher inside tmux. Resume restarts an
incomplete Episode, not its conversation or game state. After a machine crash
or forcibly killed runner, first check for leftover owned game/Agent processes
and stop them before resuming; the output lock is not a process-recovery service.
Normal task failure/deadline continues the experiment. Execution, measurement
or cleanup errors stop the current invocation; fix the issue and rerun.

Do not use incremental smoke runs as a substitute for a frozen evaluation.
Code or native-runtime changes are recorded in each launch's provenance but
do not automatically invalidate completed Episodes. After a meaningful
implementation/scorer change, use a fresh output root for comparable results.
Copy incomplete evidence elsewhere before resuming if needed for debugging.

## Reading results

```text
output_dir/
  config.json                  Latest invocation's complete resolved configuration
  summary.json                 Latest invocation's results, including reused Episodes
  provenance.json              Latest invocation's code/environment identity
  launch.json                  Latest invocation's operational settings
  runs/
    <launch-id>/               Preserved configuration, summary, provenance and launch
  tool_calling_astra/
    move_2_metres.structured_tool/
      episode_1/
        results/
          result.json
          evaluation.json
        before/
        after/
        recording/
          video.mp4            Unless --no-recording is set, in either mode
          chat/                Unless --no-record-chat is set
            agent.jsonl
            agent.log
            query.jsonl
            query.log
            images/            Referenced images, normally VM only
        game/                  Native runtime files and logs
        agent/                 External Agent artifacts when applicable
```

Start with `summary.json`, then open the relevant Episode:

- `status: completed` and `measurement: valid` mean a usable measurement.
  `task_outcome` distinguishes success from failure.
- `status: error` means execution, measurement or cleanup failed; inspect
  `errors` and native logs. It is not automatically a zero task score.
- `cancelled` and `not_run` are not completed measurements.
- `results/evaluation.json` gives the game-owned scoring details.
- `recording/chat/agent.jsonl` records Agent messages, observations, tool
  execution and termination events with timestamps; it replaces `trace.jsonl`.
- `recording/chat/query.jsonl` records normalized model inputs and responses
  or errors, including retries and cancellation, linked by query/attempt IDs.
  It records model calls, not a separate QueryAgent or raw HTTP traffic.
- The matching `.log` files are readable transcripts. Images use
  `{image: images/<hash>.<extension>}` placeholders and are stored once in
  `chat/images/`, without changing model inputs.
- Disabling chat recording preserves results, aggregate usage and native
  game/Agent artifacts, but omits detailed transcripts and exported images.
- Video helps diagnose interaction failures but does not replace private
  evaluator evidence. Check recording validity before claiming visual coverage.

VM relative mouse motion is clipped to the game window; tool receipts report
the applied displacement. Focus-loss checks still stop unsafe input.

Results group Agent configurations, tasks and modes separately. Success rates
use valid completed measurements and expose other statuses; always report the
missing/error counts too. A task failure may be a valid engineering smoke
result, but an unexercised tool path is **untested**, not verified.

`config.json` includes all Agent/model/task settings, resolved paths, original
experiment/task YAML text, source paths and hashes. It does not bundle game
binaries, map bytes or credentials. Each Episode records a relative
`output_path` and its originating `launch_id`; use that launch's metadata when
inspecting reused results. Historical output directories are not migrated.

Minecraft and Veloren have different snapshot/timing semantics. Read the game
README before comparing scores: continuous-world consequences, snapshot
boundaries and endpoint-only scoring limit what a result proves.

## Adding tasks and games

### Add a task to an existing game

1. Add a YAML under `config/<game>/tasks/visual_motor/` or `structured_tools/`.
   Start from an existing task using the desired evaluator.
2. Set a unique task ID, public objective, time budget, explicit fixture and
   evaluator parameters. ST can specify an allowed `tools` list; omitted means
   all public tools for that game. VM does not accept an ST allowlist.
3. Add its path explicitly to an experiment. There is no implicit task discovery.
4. Check reset conditions, that the goal is not already met, and that private
   scoring reflects the stated goal. Qualify the actual public control path
   before using the task for research.

World references are explicit: Minecraft uses a native save directory; Veloren
uses a native map file plus declared initial conditions. Keep source fixtures
immutable. A map alone is not a complete running-world checkpoint.

### Add a game

Implement [BaseGame](game/base_game.py) under `game/<name>/` and document its
setup, modes, controls and scoring limits in one game README.

- Provide `start`, `begin`, `end`, `close`, `get_agent_interface`,
  `get_instructions` and `save_snapshot`.
- Implement a game-owned binding returning
  [GameBinding](game/bindings.py): restricted public controls, private evaluator
  and initial-evidence verification.
- Add explicit game selection in [factory.py](benchmark/factory.py).
- Supply static introduction/mode instructions under `game/<name>/prompts/`.
  Pass task objectives separately; do not embed task solutions in control prompts.
- Add fixtures/tasks and qualify initialization, real observations/actions,
  deadline cutoff, snapshots and cleanup for each supported mode.

The runner owns Episode timing and lifecycle; the game owns its interactions
and evidence. Agents must not receive the administrative game object, private
snapshots or evaluator state. Reject unsupported modes instead of silently
substituting different capabilities.

## Agent integration

### Add an Agent

Implement [BaseAgent](agent_framework/agents/base_agent.py) under
`agent_framework/agents/<name>/`, with one README covering setup and adaptation.
Use the [baseline](agent_framework/agents/tool_calling_agent/README.md) as a
small reference, or [ProcessAgent](agent_framework/agents/process_agent.py) for
an external runtime.

### Python lifecycle contract

- `run(context)` owns the Agent's observation, reasoning and action loop.
- `stop(reason)` cooperates with cancellation/deadlines.
- `close()` releases Agent-owned resources.
- Use only the injected public interface/tools and instructions.
- Return an `AgentExit`; the game evaluator, not the Agent, decides task success.
- Register construction and admission in [factory.py](benchmark/factory.py).
- For external systems, pin the source/runtime, disclose patches and preserve
  their meaningful native execution loop rather than replacing it with the
  baseline loop.

An Agent may use memory, multiple internal roles or another transport, but its
actual model calls, permissions and computation must be disclosed and fit the
Episode budget. Current experiment factories support one configured model per
entry; extending an Agent alone does not add a multi-model YAML schema.

### Shared process integration

External Agent setup uses a dedicated checkout at the declared revision;
source validation rejects unexpected tracked edits and undeclared patches.
Do not point setup at an unrelated working checkout. Environment variables
select prepared runtimes; dependencies are not installed during Episodes.
The process bridge supplies only admitted tools and public observations,
records requests, and coordinates stopping with the benchmark. It is
cooperative isolation, not a security sandbox for untrusted code. Exact
supported native loops and restrictions belong in each Agent's README.

### Agent validation

First check setup/admission and offline lifecycle behavior. Then opt into a
small native VM/ST task and verify actual observations, actions, deadline/
operator stop, recording and cleanup. A normally scored task failure need not
fail integration acceptance; broken execution or missing coverage must not be
relabeled as model weakness.

```bash
# Small offline orchestration checks; no game or model calls.
uv run --locked --extra minecraft --extra veloren --group test python -m pytest \
  tests/test_benchmark -m "not game and not live" -q
```

Real tests are explicitly opt-in and can consume provider quota. See each game
and Agent README for preparation and targeted commands. The opt-in CLI suite
is [test_live.py](tests/test_benchmark/test_live.py); it checks a native Agent,
a scored deadline and SIGINT. Do not run large sweeps just to validate a
configuration edit.

## Repository guide

| Directory | Purpose |
| --- | --- |
| [config/](config/) | Tasks, immutable fixtures and experiment plans |
| [game/](game/) | Game runtimes, public controls and private evaluators |
| [agent_framework/](agent_framework/) | Agent implementations, model clients and shared integration utilities |
| [benchmark/](benchmark/) | Serial orchestration, lifecycle and result recording |
| [tests/](tests/) | Focused offline checks and opt-in real integration tests |
| `output/temp/` | Local smoke configurations and exploratory scripts |

Keep user documentation in this README and one README per game/Agent. Prefer
small tests for consequential runtime behavior over duplicating obvious
configuration/schema checks. Do not commit credentials, installed runtimes or
game assets without redistribution rights. Framework, upstream Agent, game
code and asset licenses are separate; consult the relevant game/Agent README
and retained notices before redistribution.
