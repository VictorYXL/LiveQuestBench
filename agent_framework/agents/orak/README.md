# Orak

Experiment agent name: `orak`. This is the upstream zeroshot profile with public
VM/ST tools and text memory, not the Voyager/code-generation profile. Auxiliary
critic, curriculum, embedding and skill-management services are not enabled.

Install Git and uv, then set `AGENT_RUNTIME_DIR` to a dedicated destination:

```bash
uv run --locked python -m agent_framework.agents.orak.setup \
  --root "$AGENT_RUNTIME_DIR"
export LIVEQUEST_ORAK_ROOT="$AGENT_RUNTIME_DIR"
```

Setup prepares the pinned Python 3.11 runtime and compatibility patch:

```yaml
agents:
  - id: orak
    name: orak
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Use a supported Responses provider with tool calling and, for VM, image support.
Keep the environment variable set during runs. See [usage](../../../README.md).
Pinned source: [source.json](source.json). Upstream [MIT notice](patches/LICENSE.txt).
