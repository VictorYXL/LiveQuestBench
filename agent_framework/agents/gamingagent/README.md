# GamingAgent

Experiment agent name: `gamingagent`. The profile retains upstream perception,
text memory, reflection and reasoning, using the benchmark's public game tools.
It is not a reproduction of an upstream published score.

Install Git and uv, then set `AGENT_RUNTIME_DIR` to a dedicated destination:

```bash
uv run --locked python -m agent_framework.agents.gamingagent.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_GAMINGAGENT_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned Python 3.11 runtime and compatibility patch:

```yaml
agents:
  - id: gamingagent
    name: gamingagent
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Use a supported Responses provider with tool calling and, for VM, image support.
All model calls share the episode budget; the world keeps advancing.
Keep the environment variable set during runs. See [usage](../../../README.md).
Pinned source: [source.json](source.json). Upstream [MIT notice](patches/LICENSE.txt).
