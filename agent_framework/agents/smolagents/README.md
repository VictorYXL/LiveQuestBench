# smolagents

Experiment agent name: `smolagents`. This uses the upstream tool-calling agent,
not CodeAgent. Generated Python, web/shell tools, managed agents and parallel
game actions are disabled.

Install Git and uv, then set `AGENT_RUNTIME_DIR` to a dedicated destination:

```bash
uv run --locked python -m agent_framework.agents.smolagents.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_SMOLAGENTS_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned Python 3.11 runtime:

```yaml
agents:
  - id: smolagents
    name: smolagents
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Use a supported Responses provider with tool calling and, for VM, image support.
Keep the environment variable set during runs. `final_answer` ends the agent;
the benchmark evaluates task success independently. See [usage](../../../README.md).
Pinned source and Apache-2.0 license: [source.json](source.json).
