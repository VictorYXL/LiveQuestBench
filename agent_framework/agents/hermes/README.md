# Hermes Agent

Experiment agent name: `hermes_agent`. This profile uses public game observations
and tools. Personal context, optional memory, background review, compression and
progressive tool discovery are disabled.

Install Git and uv, then set `AGENT_RUNTIME_DIR` to a dedicated destination:

```bash
uv run --locked python -m agent_framework.agents.hermes.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_HERMES_ROOT="$AGENT_RUNTIME_DIR"
```

Setup may download the upstream Python 3.14 environment without replacing the
benchmark environment. In your experiment:

```yaml
agents:
  - id: hermes
    name: hermes_agent
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Use a supported Responses provider with tool calling and, for VM, image support.
Keep the environment variable set during runs. See [usage](../../../README.md).
Pinned source and MIT license information: [source.json](source.json).
