# Hugging Face smolagents

[`SmolagentsAgent`](agent.py) runs upstream `ToolCallingAgent.run`, including
its native ReAct loop, prompt templates, memory, parsing, tool execution and
`final_answer` mechanism. It uses public `Model` and `Tool` extension points.
This is **not CodeAgent** and does not execute generated Python.

[`source.json`](source.json) pins
`96f33faaf028479119ec8d34507b47694cf14e34` from `huggingface/smolagents`,
licensed Apache-2.0. No source patches are needed. Native web/shell tools,
managed agents, planning calls and parallel game execution are not enabled.
The upstream tool-calling method is retained with those explicit settings.

## Installation

```bash
uv run --locked python -m agent_framework.agents.smolagents.setup \
  --root "$PWD/output/runtimes/smolagents"
export LIVEQUEST_SMOLAGENTS_ROOT="$PWD/output/runtimes/smolagents"
```

Setup prepares a dedicated pinned checkout and Python 3.11 environment.
[`requirements.lock`](requirements.lock) pins the base dependencies from the
upstream revision's `pyproject.toml`; no optional provider/model runtimes are
needed for the injected model. The worker imports that checkout's `src` directly.
Neither the main project environment nor the upstream tracked source is modified.
Runs never install dependencies.

To refresh dependencies deliberately, using the prepared pinned checkout:

```bash
uv pip compile "$LIVEQUEST_SMOLAGENTS_ROOT/pyproject.toml" \
  --python-version 3.11 --universal \
  --output-file agent_framework/agents/smolagents/requirements.lock
```

## Construction and real tests

```python
from agent_framework.agents.smolagents import SmolagentsAgent

agent = SmolagentsAgent(
    client, output_dir=output_dir, tools=tools, observe=observe,
    model="gpt-6-astra", reasoning_effort="low", max_output_tokens=4096,
)
```

Follow the [shared game/model preparation](../../../README.md#agent-validation):

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py -k smolagents --headless --recording -q -s
```

The three selected cases use actual VM/ST and a native ST operator-stop test.
Success means the integration operates correctly, not that three logs were
collected. Scores remain truthful in the output artifacts.

## Disclosed settings and boundaries

- Upstream prompts receive the supplied game instructions through `instructions`.
  No task strategy or copied game introduction lives in this package.
- Native `final_answer` is retained as a declared local control tool. It echoes a
  string answer and has no game access. It is admitted/recorded alongside game
  tools, but does **not** count as a real game interaction for test acceptance.
- Native Tool metadata wraps the approved game schemas. Model requests use
  their original JSON schemas, preserving nested fields and motor bounds.
- The native model helper flattens text history using its own role conversions.
  The shared bridge appends the current public observation. Exactly one current
  image is supplied for VM; old images are not stored in native memory.
  Textual native tool history does not retain provider reasoning-continuation
  records. This differs from other Agents' history strategies.
- Stop strings are explicitly disabled through native model configuration
  (`REMOVE_PARAMETER`): the selected reasoning-model bridge does not support
  them. They are not silently dropped by the shared transport.
- `max_tool_threads=1`, `planning_interval=None`, `add_base_tools=False`,
  non-streaming and `max_steps=1000`. The benchmark wall-clock budget remains
  authoritative. Other settings and model combinations are not certified.
- The worker has no credentials or administrative game handles. The benchmark
  gates access before stop/cleanup. Signals bypass native retry handlers so
  cancellation is not mistaken for another model failure.
- Native recovery from model parsing/execution errors remains native behavior.
  Parent model/transport/game exceptions propagate as integration failures.

See [shared process rules](../../../README.md#shared-process-integration) for
source admission, ownership and the cooperative-isolation limitation.
