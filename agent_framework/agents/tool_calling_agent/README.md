# Tool-calling baseline

Experiment agent name: `tool_calling`. No separate installation is required.
It observes, requests model-selected public tools and executes them sequentially.
There is no separate planner, reflection stage or learned skill library.

```yaml
agents:
  - id: baseline
    name: tool_calling
    model:
      provider: openai
      name: YOUR_MODEL
      reasoning_effort: low
      max_output_tokens: 4096
```

Copilot, OpenAI and vLLM are supported; see [model settings](../../../README.md#model-clients).
The default keeps the current full observation and previous action/result
history. `observation_history` can retain more observations.

The world continues during reasoning and tool execution. A final answer ends the
attempt, but private scoring decides success. See the [project guide](../../../README.md)
for running experiments or adding another agent.
