# Orak fixed-tool game extension

[`OrakAgent`](agent.py) retains upstream `BaseRunner.play`,
`BaselineAgent.__call__`, the `zeroshot_agent` module sequence, local memory
updates and native `### Actions` parsing. The Wrapper supplies model transport,
public game prompt modules, observation/action conversion and bounded lifecycle.
It does not implement a replacement decision loop.

**This is an Orak fixed-tool extension, not a reproduction of Orak's original
Minecraft/Voyager profile.** That profile generates programs and uses a different
environment. This extension runs the native general zeroshot pipeline over the
benchmark's VM/ST interfaces. No generated code, Mineflayer participant, world
pause/reset, auxiliary critic/curriculum model or embedding service is admitted.
Planning, reflection and skill-management variants are not claimed as supported.

## Source and installation

[`source.json`](source.json) pins
`c14e5a01f998c222c76e09da2564aa8b72ebc75e` from `krafton-ai/Orak`.
Upstream is MIT; the [license notice](patches/LICENSE.txt) accompanies the patch.
The checkout is external, not a vendored tree or submodule.

The [declared patch](patches/0001-lazy-optional-services.patch) defers optional
provider imports and embedding/vector-store initialization until those services
are actually used. The zeroshot path does not use them. This avoids requiring
unrelated provider credentials or installing every game's dependencies.
The Agent algorithm and runner are unchanged. This patch does not certify
Orak's optional service paths; those require their own dependencies and checks.

```bash
uv run --locked python -m agent_framework.agents.orak.setup \
  --root "$PWD/output/runtimes/orak"
export LIVEQUEST_ORAK_ROOT="$PWD/output/runtimes/orak"
```

Setup installs Python 3.11 and the exact versions in
[`requirements.lock`](requirements.lock), resolved from
[`requirements.in`](requirements.in). It applies only the declared patch, rejects
unexpected source modifications and does not reset existing worktrees.
The runtime also verifies the entire tracked source against the pin plus patch.
Runs never install dependencies. Game/runtime binaries have separate licenses.

To refresh dependency resolution deliberately:

```bash
uv pip compile agent_framework/agents/orak/requirements.in \
  --python-version 3.11 --universal \
  --output-file agent_framework/agents/orak/requirements.lock
```

## Construction and real tests

```python
from agent_framework.agents.orak import OrakAgent

agent = OrakAgent(
    client, output_dir=output_dir, tools=tools, observe=observe,
    model="gpt-6-astra", reasoning_effort="low", max_output_tokens=4096,
)
```

Follow the [shared preparation and credential instructions](../../../README.md#agent-validation):

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k orak --headless --recording -q -s
```

This selects VM, ST and an actual ST operator-stop case. Tests require a real
configured model, real game tool round trips, world progression, gated access
after termination and worker cleanup. Task failure is recorded independently;
communication, model configuration and adapter failures still fail the test.

## Disclosed semantics

- The model is injected through the existing `chat_completion` extension.
  Provider function calls are serialized into the native `### Actions` envelope;
  the unchanged native parser/memory/runner dispatch the resulting fixed tools.
  A normal textual response ends the attempt; it is not proof of task success.
- Game-owned instructions and the task are injected, not copied into Agent
  prompt files. A generic prompt-module adapter supplies native memory fields:
  current/previous text state, prior action and last tool results.
- Text observations enter native memory. The shared bridge attaches a fresh
  permitted observation to each model request, including exactly one current
  VM image. Images are not retained in Orak's native history. No hidden state is
  substituted for images.
- Native prompt/memory formatting is retained rather than forced into the
  baseline's full chat history. Previous actions/results are text, not provider
  reasoning-continuation records. Account for this in comparisons.
- `GameTransport` is an interface adapter, not an environment simulator: every
  observation and action uses the parent-owned real game handle. The upstream
  `evaluate()` hook returns no score and only the Agent's completion flag.
  Private scoring remains with the benchmark.
- The native bound is 1,000 steps; the benchmark wall-clock budget usually
  binds first. Stop gates the real interface before terminating the worker.
  No game resource is owned or closed by this worker.
- Native provider pricing/logging is not used. The benchmark retains actual
  model requests, usage, messages, tool responses and final native memory.
  No provider keys are passed to the worker.

See [shared process semantics](../../../README.md#shared-process-integration)
for trust boundaries and settings validation.
