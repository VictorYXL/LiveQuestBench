# Orak

Use `orak` as the Agent name in an experiment. This integration runs Orak's
zeroshot profile with the benchmark's fixed VM/ST tools. It is not Orak's
Minecraft/Voyager code-generation profile.

Generated programs, auxiliary critic/curriculum models, embedding services and
planning/skill-management variants are not enabled.

## Installation

Install Git and uv. Set `AGENT_RUNTIME_DIR` to a dedicated installation
destination, then run from the repository root:

```bash
uv run --locked python -m agent_framework.agents.orak.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_ORAK_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned checkout, Python 3.11 dependencies and declared
compatibility patch. Do not use an unrelated working checkout. Dependencies
are not installed during Episodes.

## Experiment configuration

```yaml
agents:
  - id: orak
    name: orak
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

Orak retains its text-based memory rather than the baseline's conversation
history. VM supplies a current image, not a retained image sequence. The
benchmark wall-clock budget applies throughout reasoning and actions.

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k orak \
  --headless --recording -q -s
```

These tests consume model quota and cover real VM/ST interaction and stopping.
For Veloren, use its [test guide](../../../game/veloren/README.md#tests) with the
same selector. Integration errors and valid task failures are reported separately.

## Extending the integration

Follow the [Agent integration guide](../../../README.md#agent-integration).
Treat additional Orak variants as separate profiles with explicit model,
memory and tool permissions; validate their real game behavior before use.

The pinned source and declared patches are listed in
[source.json](source.json). The upstream MIT
[license notice](patches/LICENSE.txt) is retained. Game licenses are separate.
