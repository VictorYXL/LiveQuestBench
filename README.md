# LiveQuestBench

LiveQuestBench evaluates agents pursuing long-term goals in real-time 3D games.
The world continues while the agent thinks: timing, resources and earlier choices
affect what remains possible.

The suite contains **60 tasks** across Minecraft and Veloren:
spatial interaction, planning/resources, real-time execution,
information/adaptation, cooperation and within-episode learning. Each dimension
contains five tasks per game. Difficulty ratings are provisional.

- **VM (`visual_motor`)**: game images and bounded keyboard/mouse actions.
- **ST (`structured_tool`)**: permitted game state and fixed game-specific tools.

Compare the modes separately. Not every task supports both modes.

## Installation

Use Linux, Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --extra minecraft --extra veloren --group test
```

Install the game separately:
[Minecraft](game/minecraft/README.md) or [Veloren](game/veloren/README.md).
Headless rendering requires Xvfb; video recording requires FFmpeg.
Game, asset and external-agent licenses are separate; retain their notices and
follow their terms.

## Agents

The built-in [tool-calling baseline](agent_framework/agents/tool_calling_agent/README.md)
requires no additional installation. External integrations have separate setup guides:
[DeepSeek Harness](agent_framework/agents/deepseek_harness/README.md),
[Hermes](agent_framework/agents/hermes/README.md),
[Orak](agent_framework/agents/orak/README.md),
[smolagents](agent_framework/agents/smolagents/README.md) and
[GamingAgent](agent_framework/agents/gamingagent/README.md).

## Model clients

| Provider | Required settings |
| --- | --- |
| `github_copilot` | `COPILOT_GITHUB_TOKEN` or `LIVEQUEST_COPILOT_TOKEN_FILE`; entitled account |
| `openai` | `OPENAI_API_KEY` |
| `vllm` | Compatible server `base_url`; optional `VLLM_API_KEY` |

Keep credential values outside configuration files and version control.
Choose an available model with tool calling and, for VM, image support.
External-agent profiles require a Responses-compatible hosted provider and
explicit `reasoning_effort`.

## Running an experiment

Choose a configuration under `config/<game>/experiments/`. Set
`EXPERIMENT_CONFIG` to its path and `RESULTS_DIR` to your results destination:

```bash
uv run --locked --extra minecraft --extra veloren python run_benchmark.py \
  --config "$EXPERIMENT_CONFIG" --output "$RESULTS_DIR" \
  --headless --recording
```

Inspect the task list, agents and repetitions before running: full-suite
experiments can consume substantial model quota. For a small run, save this
example under `config/veloren/experiments/` and select an available model:

```yaml
id: single_task
game: veloren
tasks:
  - path: ../tasks/structured_tools/mountain_workshop_circuit.yaml
repetitions: 1
agents:
  - id: baseline
    name: tool_calling
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Paths are relative to the declaring YAML. Use `--no-headless` for an existing
desktop, `--no-recording` to disable video, or `--no-record-chat` to omit detailed
model transcripts. Never interact with the controlled display during evaluation.

Results start at `summary.json`; each episode has outcome, evaluation, metrics
and optional recordings. A valid task failure is distinct from an infrastructure
error. Review artifacts for sensitive information before sharing them.

Repeating a command reuses completed valid episodes. Incomplete episodes restart
from scratch and their partial artifacts are removed; archive them first if
needed. Use a fresh results destination after changing code, tasks or runtimes.

### Optional storage reduction

The experimental `--storage-profile compact` reduces duplicate logs and requires
chat recording; `legacy` remains the default. Keep the whole episode directory
together and use the same storage profile for compared runs.

After a compact episode finishes and cleanup succeeds, set `EPISODE_DIR` to its
directory and run archive operations **serially**:

```bash
uv run --locked python -m benchmark.archive create "$EPISODE_DIR"
uv run --locked python -m benchmark.archive verify "$EPISODE_DIR"
# Recheck applicable offline scoring/metrics before retiring originals.
uv run --locked python -m benchmark.archive retire "$EPISODE_DIR"
uv run --locked python -m benchmark.archive restore "$EPISODE_DIR"
```

`create` retains originals; `retire` deletes only verified raw logs. Use `restore`
before analysis that requires them. Archiving needs temporary disk space and
should run outside live evaluations. Inspect interrupted archives before retrying.

## Extending the benchmark

| Add | Integration steps |
| --- | --- |
| A game | Implement `BaseGame` and `GameBinding` under `game/`; register it in `benchmark/factory.py`; document installation, public controls and private scoring in the game README. |
| A task | Add YAML under `config/<game>/tasks/<mode>/`, declaring the objective, budget, fixture, evaluator and ST tools; add it to an experiment. Validate initialization, legal actions and scoring. |
| An agent | Implement `BaseAgent` under `agent_framework/agents/`; optionally reuse `ProcessAgent` for an external runtime. Register it in `benchmark/factory.py` and provide an agent setup README. |
| An LLM provider | Implement `BaseLLMClient` under `agent_framework/llm_client/`; register configuration in `benchmark/config.py` and construction in `benchmark/factory.py`. |

Keep observations and actions public, evaluator evidence private, and stop/cleanup
behavior explicit. New integrations must not pause the game during reasoning.

Run the reusable offline tests without game or paid-model calls:

```bash
uv run --locked --extra minecraft --extra veloren --group test \
  python -m pytest -m "not live and not game" -q
```
