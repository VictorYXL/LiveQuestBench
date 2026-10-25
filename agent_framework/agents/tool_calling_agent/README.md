# Tool-calling baseline

Use `tool_calling` as the Agent name in an experiment. This built-in baseline
needs no separate Agent installation.

It repeatedly observes the game, asks the model to select public tools and
executes the selected actions. It has no separate planner, reflection system,
learned skills or memory summarization.

## Experiment configuration

After preparing a game and model credentials, add:

```yaml
agents:
  - id: baseline
    name: tool_calling
    model:
      provider: github_copilot
      name: gpt-6-astra
      reasoning_effort: low
      max_output_tokens: 4096
```

The baseline supports Copilot, OpenAI and vLLM. Choose a model available to you
with tool calling and, for VM, image support. vLLM uses different model settings;
see [model configuration](../../../README.md#model-clients) and the
[experiment guide](../../../README.md#running-an-experiment).

## Behavior and limits

- The model receives the public task, game instructions and current observation.
- Earlier full observations are omitted from subsequent requests; action and
  tool-result history are retained. No generated summary replaces old observations.
- Actions execute sequentially. The world continues during reasoning and waits.
- A final answer ends the attempt, but the private evaluator decides success.
- The Episode deadline applies to the entire loop. Context exhaustion may end
  an attempt before the deadline; it does not imply task success or failure.

These settings matter when comparing the baseline with Agents that use
different memory or planning strategies.

## Tests

Prepare Minecraft and authorized Copilot credentials, then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k tool_calling \
  --headless --recording -q -s
```

The tests run actual VM/ST sessions and consume model quota. For Veloren, follow
its [test guide](../../../game/veloren/README.md#tests) with the same selector.
Inspect task scores separately from integration and cleanup outcomes.

## Use as an integration reference

For a new Agent, follow the
[Agent integration guide](../../../README.md#agent-integration). Create a fresh
Agent per Episode, use only the supplied public controls, respond to stop
requests and release Agent-owned resources. The benchmark owns the game
lifecycle and task scoring.
