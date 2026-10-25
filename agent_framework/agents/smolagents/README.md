# Hugging Face smolagents

Use `smolagents` as the Agent name in an experiment. This profile uses the
upstream tool-calling Agent, not CodeAgent. It does not execute generated Python
or enable web/shell tools, managed agents or parallel game actions.

## Installation

Install Git and uv. Set `AGENT_RUNTIME_DIR` to a dedicated installation
destination, then run from the repository root:

```bash
uv run --locked python -m agent_framework.agents.smolagents.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_SMOLAGENTS_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned checkout and Python 3.11 dependencies. Keep the
environment variable set for tests and experiments. Dependencies are not
installed during Episodes.

## Experiment configuration

```yaml
agents:
  - id: smolagents
    name: smolagents
    model:
      provider: github_copilot
      name: gpt-6-astra
      reasoning_effort: low
      max_output_tokens: 4096
```

Choose a model available to your account. The profile requires tool calling,
a supported Responses provider and explicit `reasoning_effort`; VM also
requires image support. See the
[experiment guide](../../../README.md#running-an-experiment).

The Agent retains its text-based tool history and receives the current public
observation. Old VM images are not retained in native memory. `final_answer`
ends the Agent's attempt but is not a game action or a task-success verdict.
The Episode wall-clock budget remains authoritative.

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k smolagents \
  --headless --recording -q -s
```

These tests consume model quota and cover real VM/ST interaction and stopping.
For Veloren, follow its [test guide](../../../game/veloren/README.md#tests) with
the same selector.

## Extending the integration

Follow the [Agent integration guide](../../../README.md#agent-integration).
Document additional planning, memory or tool capabilities as a separate profile,
and validate permissions, deadlines and cleanup in each supported game mode.

The pinned source and Apache-2.0 license information are declared in
[source.json](source.json). Game and asset licenses remain separate.
