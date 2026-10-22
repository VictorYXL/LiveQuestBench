# ToolCallingAgent

[`ToolCallingAgent`](agent.py) is the vanilla tool-calling baseline. It implements
[`BaseAgent`](../base_agent.py) directly, without a process Wrapper, separate
planner, reflection, memory summarization, skill learning or `query_agent`.
It receives game instructions and restricted observation/tool bindings from
the caller; it does not import games or read prompt files.

## Loop

1. Use supplied game instructions as the system message (omit it if empty).
   Supply the public task, wall-clock budget and initial observation.
2. Ask the configured model with tool schemas.
3. Validate complete response, tool names, unique call IDs and argument-object
   shapes before executing the batch sequentially. Tools validate their own
   argument values. Return results under the original call IDs.
4. Acquire a fresh observation after the batch and repeat.
5. A nonempty text-only answer returns `AgentExitReason.RETURNED`, not a task
   success verdict. The runner scores independently.

The fixed history policy sends only the latest complete text observation (ST)
or image (VM). Earlier text observations/images become explicit omission notices,
not generated summaries. Task instructions and the wall-clock budget are always
retained, as are assistant text, tool calls/results and provider continuation
state. VM observation text accompanying images is retained. Full observations
remain in `messages` and may be recorded with `on_message`; request recording
captures the reduced input actually sent to the model.

This deterministic policy does not plan, retrieve memories or summarize history.
It can lose information visible only in older observations; action history can
still exhaust the context. A recognized context-capacity error is not retried:
the Agent returns `NATIVE_LIMIT` with `native_reason=context_limit_exceeded`.
The runner ends game access and scores the final state normally, so this reason
alone does not imply task failure. Unclassified provider errors still propagate
as execution errors. There is no automatic tool retry.

Results from the previous full-text-observation policy are a separate scaffold
version, not interchangeable measurements. Re-run affected ST baseline episodes
when comparing Agents; retain old trajectories as historical evidence.

## Construction

From the repository root, after preparing a VM Minecraft instance:

```python
from agent_framework.agents.tool_calling_agent import ToolCallingAgent
from game.minecraft.visual_motor.interface import agent_tools, agent_observation

agent = ToolCallingAgent(
    client,
    tools=agent_tools(),
    observe=agent_observation,
)
# The runner supplies AgentContext with the restricted interface and
# game.get_instructions(), and owns the game lifecycle and deadline.
exit = await agent.run(context)
```

For ST, use the same function names from
`game.minecraft.structured_tools.interface`. For another game, inject its
bindings instead. See the [public interface contract](../../../README.md#python-lifecycle-contract).

Create a fresh Agent per attempt. `stop(reason)` cancels active loop work;
`close()` drains owned work and is repeatable. The caller owns the model client
and game, including closing them. External cancellation and errors propagate.
The Agent does not enforce its own deadline or pause the game. The runner must
gate/end game access before awaiting Agent cleanup, on normal and error exits.

## Validation

Prepare the runtime and credentials using the
[shared live-test instructions](../../../README.md#agent-validation), then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents_minecraft.py -k tool_calling --headless --recording -q -s
```

Both cases use real Minecraft VM/ST and `gpt-6-astra`, not scripted replies.
Live checks consume quota and independently score inventory, not completion
claims. They are integration samples, not long-horizon rankings. The
[Minecraft README](../../../game/minecraft/README.md) covers setup and EULA.
