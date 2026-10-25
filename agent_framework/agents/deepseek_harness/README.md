# DeepSeek Harness

Use `deepseek_harness` as the Agent name in an experiment. This integration
uses DeepSeek Harness with the benchmark's public observations and fixed game
tools. Shell, filesystem, generated-code, subagent and telemetry features are
not enabled.

## Installation

Install Git, uv and Node.js compatible with `^22.19.0 || >=24.0.0`, including
npm/npx. Set `AGENT_RUNTIME_DIR` to a dedicated installation destination, then
run from the benchmark repository root:

```bash
uv run --locked python -m agent_framework.agents.deepseek_harness.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_DEEPSEEK_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned upstream runtime and its dependencies. Keep the
environment variable set for tests and experiments. Do not use an unrelated
working checkout as the installation destination.

## Experiment configuration

Add an entry to your experiment:

```yaml
agents:
  - id: deepseek
    name: deepseek_harness
    model:
      provider: github_copilot
      name: gpt-6-astra
      reasoning_effort: low
      max_output_tokens: 4096
```

Choose a model available to your account. The profile requires tool calling,
a supported Responses provider and explicit `reasoning_effort`; VM also
requires image support. Follow the
[experiment guide](../../../README.md#running-an-experiment) for tasks, budgets
and credentials.

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k deepseek \
  --headless --recording -q -s
```

These tests use real games and models and consume quota. For Veloren, follow
its [test guide](../../../game/veloren/README.md#tests) with the same selector.
Check interaction and stopping as well as the independent task outcome.

## Extending the integration

Follow the [Agent integration guide](../../../README.md#agent-integration) when
adding features or changing the profile. Keep game permissions explicit and
validate each supported mode. Additional upstream features are not enabled
merely by installing their dependencies.

The pinned source and MIT license information are declared in
[source.json](source.json). Game and asset licenses remain separate.
