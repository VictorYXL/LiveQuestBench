# Hermes Agent

Use `hermes_agent` as the Agent name in an experiment. This profile uses Hermes
with the benchmark's public observations and fixed game tools. Personal user
context, optional memory, background review, compression and progressive tool
discovery are disabled. It is not the full personal-assistant configuration.

## Installation

Install Git and uv. Set `AGENT_RUNTIME_DIR` to a dedicated installation
destination, then run from the repository root:

```bash
uv run --locked python -m agent_framework.agents.hermes.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_HERMES_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned runtime and locked dependencies. It may download
Python 3.14 for Hermes without changing the benchmark's Python environment.
Keep the environment variable set for tests and experiments.

## Experiment configuration

```yaml
agents:
  - id: hermes
    name: hermes_agent
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

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k hermes \
  --headless --recording -q -s
```

These tests make real model calls and consume quota. For Veloren, follow
its [test guide](../../../game/veloren/README.md#tests) with the same selector.
Task success is scored independently of integration correctness.

## Extending the integration

Follow the [Agent integration guide](../../../README.md#agent-integration).
Document any enabled memory or additional capabilities as a distinct profile,
preserve public game permissions and validate stopping and cleanup.

The pinned source and MIT license information are in
[source.json](source.json). Game and asset licenses remain separate.
