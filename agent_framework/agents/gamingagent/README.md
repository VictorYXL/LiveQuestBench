# GamingAgent

Use `gamingagent` as the Agent name in an experiment. This profile uses
GamingAgent's perception, memory, reflection and reasoning with the benchmark's
fixed game tools. It is not a reproduction of an upstream game configuration
or published score.

## Installation

Install Git and uv. Set `AGENT_RUNTIME_DIR` to a dedicated installation
destination, then run from the repository root:

```bash
uv run --locked python -m agent_framework.agents.gamingagent.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_GAMINGAGENT_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned checkout, Python 3.11 dependencies and declared
compatibility patch. Keep the environment variable set for tests and
experiments. Dependencies are not installed during Episodes.

## Experiment configuration

```yaml
agents:
  - id: gamingagent
    name: gamingagent
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

Perception, reflection and reasoning use the configured model and share the
Episode budget. VM uses game images and public text; ST uses permitted state.
The world advances during all model calls, so an observation can age before an
action is chosen. Memory retains text descriptions rather than old images.
Private game scores are not supplied to the Agent.

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k gamingagent \
  --headless --recording -q -s
```

These tests consume model quota and cover real VM/ST interaction and stopping.
For Veloren, follow its [test guide](../../../game/veloren/README.md#tests) with
the same selector. Evaluate integration correctness separately from task success.

## Extending the integration

Follow the [Agent integration guide](../../../README.md#agent-integration).
Disclose changes to perception, memory, reflection and model usage as a separate
profile. Keep private scoring outside Agent inputs and validate each supported
mode.

The pinned source and declared patches are listed in
[source.json](source.json). The upstream MIT
[license notice](patches/LICENSE.txt) is retained. Game licenses are separate.
