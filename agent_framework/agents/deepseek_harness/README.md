# DeepSeek Harness

Experiment agent name: `deepseek_harness`. This profile exposes public game
observations and tools, not shell, filesystem, generated-code, subagent or
telemetry capabilities.

Install Git, uv and Node.js `^22.19.0 || >=24.0.0` with npm/npx. Set
`AGENT_RUNTIME_DIR` to a dedicated installation destination:

```bash
uv run --locked python -m agent_framework.agents.deepseek_harness.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_DEEPSEEK_ROOT="$AGENT_RUNTIME_DIR"
```

In your experiment:

```yaml
agents:
  - id: deepseek
    name: deepseek_harness
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Choose a supported Responses provider and a tool-capable model; VM also requires
image support. Keep the environment variable set during runs.
See [usage and integration](../../../README.md).
The pinned upstream source and MIT license are declared in [source.json](source.json).
