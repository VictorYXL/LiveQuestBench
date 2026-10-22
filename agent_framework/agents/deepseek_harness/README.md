# DeepSeek harness Agent

[`DeepSeekHarnessAgent`](agent.py) preserves the native DeepSeek harness loop
using core plugins, registered game tools and a custom `LlmAdapter` in
[`worker.mjs`](worker.mjs). The minimal composition does not load shell,
filesystem, generated-code, subagent or telemetry plugins. Complete model
responses are translated into native stream events; the planning loop is not
reimplemented.

[`source.json`](source.json) pins upstream commit
`687f282e8625c6b8d11ff58211a90524be2e4317`, records the upstream MIT license,
and declares an empty patch list. No upstream source patches are needed.
The checkout is neither vendored nor a submodule. Framework licensing does
not grant game/asset redistribution rights.

## Installation

Install Git, uv and Node.js compatible with `^22.19.0 || >=24.0.0`, including
npm/npx. From the benchmark repository root:

```bash
uv run --locked python -m agent_framework.agents.deepseek_harness.setup \
  --root "$PWD/output/runtimes/deepseek-harness"
export LIVEQUEST_DEEPSEEK_ROOT="$PWD/output/runtimes/deepseek-harness"
```

Setup uses pinned pnpm 11.28.5, filtered frozen dependencies, TypeScript
references and upstream Typert/tsdown bundling. Existing prepared checkouts
remain usable by setting the environment variable to their current path.
Installation is explicit; tests and Agent runs never install dependencies.
See [shared checkout and process rules](../../../README.md#shared-process-integration)
for revision checks and trust limitations.

## Construction and checks

```python
from agent_framework.agents.deepseek_harness import DeepSeekHarnessAgent

agent = DeepSeekHarnessAgent(
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
`AgentContext`. The experiment Agent name is `deepseek_harness`, matching
upstream DeepSeek Harness with a lowercase underscore-separated identifier.

Prepare Minecraft and model credentials using the
[shared live-test instructions](../../../README.md#agent-validation), then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k deepseek --headless --recording -q -s
```

The cases run the native Agent with actual Minecraft VM/ST and `gpt-6-astra`,
plus an explicit ST stop after the first completed game tool. The corresponding
Veloren suite also includes VM/ST and an explicit ST stop.
They consume model quota; there are no scripted-model Agent tests.

Benchmark-requested cancellation is reported as `stopped` and the worker exits
cleanly. Unexpected native aborts still fail; cancellation is not task success.

The [shared process rules](../../../README.md#shared-process-integration) document
model/tool mediation, observation-history differences, cancellation, evidence
and unsupported native features. This restricted integration is not a claim
of compatibility with every upstream feature or future revision.
