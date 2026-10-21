# Hermes Agent

[`HermesAgent`](agent.py) preserves Hermes' native `AIAgent` conversation loop
and system prompt. [`worker.py`](worker.py) registers game tools through native
plugins and forwards model calls through `llm_execution` middleware.

[`config.yaml`](config.yaml) and worker options disable existing user context,
optional memory, background review, compression, streaming and progressive
tool discovery. This is a restricted game integration, not the full personal
assistant with all optional features.

[`source.json`](source.json) pins upstream commit
`47b23fa048536c413a53ae5ad391f9a911f5d4e5`, records the upstream MIT license,
and declares an empty patch list. No upstream source patches are needed.
The checkout is neither vendored nor a submodule. Framework licensing does
not grant game/asset redistribution rights.

## Installation

Install Git and uv. From the benchmark repository root:

```bash
uv run --locked python -m agent_framework.agents.hermes.setup \
  --root "$PWD/output/runtimes/hermes-agent"
export LIVEQUEST_HERMES_ROOT="$PWD/output/runtimes/hermes-agent"
```

Setup may download a managed Python 3.14 runtime and installs upstream's locked
dependencies into its own environment. The benchmark's runtime is unchanged.
Existing prepared checkouts remain usable by setting the environment variable
to their current path. Tests and Agent runs never install dependencies.
See [shared checkout and process rules](../../../README.md#shared-process-integration)
for revision checks and trust limitations.

## Construction and checks

```python
from agent_framework.agents.hermes import HermesAgent

agent = HermesAgent(
    client,
    output_dir=output_dir,
    tools=tools,
    observe=observe,
    model="gpt-6-astra",
    reasoning_effort="low",
    max_output_tokens=4096,
)
```

The caller supplies a consistently configured client, restricted bindings and
`AgentContext`. The experiment ID remains `hermes`.

Run the actual installed native loop with scripted model replies and fake tools:

```bash
LIVEQUEST_EXTERNAL_TEST=1 uv run --locked --extra minecraft --group test \
  python -m pytest tests/test_agent/test_agents.py -m external -k hermes -q
```

For real Minecraft checks, follow the [shared live-test instructions](../../../README.md#agent-validation)
and add `-k hermes`. These consume model quota.

The [shared process rules](../../../README.md#shared-process-integration) document
model/tool mediation, observation-history differences, cancellation, evidence
and unsupported native features. This restricted integration is not a claim
of compatibility with every upstream feature or future revision.
