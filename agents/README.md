# Agents

## Native tool-calling baseline

[`ToolCallingAgent`](tool_calling_agent.py) implements `BaseAgent` directly.
It does not need an external-Agent Wrapper. Its game-specific observation and
tool bindings use only the restricted interface supplied in `AgentContext`;
they do not receive the administrative game object.

The loop follows the basic observation/tool pattern of GameAgentVisual:

1. Supply public game instructions, task, time budget and initial observation.
2. Ask the configured model with the registered tool schemas.
3. Validate tool-call names, IDs and argument-object shape, then execute calls
   sequentially. Tool implementations validate their own arguments. Return each
   result under its original call ID.
4. Acquire a fresh observation after the entire batch and ask again.
5. A complete text-only reply ends the run with `AgentExitReason.RETURNED`.
   It is not a success verdict.

There is no `query_agent`, separate planner, reflection, skill learning, tool
retry, or automatic history summary. Text, tool results and provider continuation
state are preserved. Only the latest image is sent in each model request;
earlier images are replaced with an explicit omission notice, not a generated
description. The full image-bearing messages remain in `agent.messages` and
can be captured through `on_message`. This accommodates providers advertising
a one-image request limit.

### Construction and ownership

Provide a `BaseLLMClient`, an asynchronous observation function and `Tool`
definitions. Both observation and tool handlers receive the restricted
`context.interface`; no particular game or client provider is required by
the loop itself.

[`minecraft_tool_calling.py`](minecraft_tool_calling.py) supplies:

- VM: PNG screenshots and one `action` tool wrapping the existing bounded
  keyboard/mouse command batches. It provides no structured game state.
- ST: existing fixed native tools, excluding the redundant `GetObservationTool`.
  The observation is the existing whitelisted state. Its palette-cube array is
  losslessly run-length encoded as `[palette_index, repeat_count]` pairs, with
  x fastest, then y, then z. No cells or unknown states are removed.
- Public game/control instructions for each mode.

For example, after starting a game and obtaining its restricted interface:

```python
from agents.tool_calling_agent import ToolCallingAgent
from agents.minecraft_tool_calling import minecraft_tools, observe_minecraft

agent = ToolCallingAgent(
    client,
    tools=minecraft_tools(game.track),
    observe=observe_minecraft,
)
# The runner supplies AgentContext and owns begin/end and the deadline.
exit = await agent.run(context)
```

Create a fresh Agent per attempt. `stop(reason)` requests cancellation of the
active loop; `close()` drains Agent-owned work and permits repeated cleanup.
The injected client and game remain caller-owned and must be closed by the
caller. External cancellation and execution errors propagate. Stopping Python
work is not proof that game inputs have been released: the runner must gate/end
the game before waiting on Agent shutdown, including on errors and normal return.
The Agent does not pause the world during model requests or tool execution.

## Validation

Offline regression checks cover message/tool round trips, latest-image history,
provider state, invalid responses, cancellation, deadline ordering and Minecraft
bindings. No game or model calls occur unless explicitly enabled:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent -q
```

The two live cases in
[`test_tool_calling_agent.py`](../tests/test_agent/test_tool_calling_agent.py)
use the installed native Minecraft runtime and **`gpt-6-astra`** through the
existing GitHub Copilot client. Both use `reasoning_effort=low`, a 4096-token
per-response output limit, one request attempt, and a **180-second wall-clock
budget** beginning immediately before `game.begin()`. Setup and final evidence/
cleanup occur outside that budget. End-request timing is recorded; the native
freeze/packet boundary is not an atomic engine cutoff.

These are small integration tasks, not long-horizon benchmark results:
the isolated generated flat world contains a three-block oak-log column at
`(0, 72..74, -2)`, with peaceful difficulty and an empty initial inventory.
Setup uses the private test harness only, before the initial snapshot.
The Agent must break and pick up at least three oak logs, retaining them as logs.
Both initial and final native inventories are checked independently; an Agent's
completion claim is insufficient. VM receives no fixture coordinates or private
inventory information. Both modes receive the same public goal.

Prepare Minecraft and review/accept its EULA as described in the
[Minecraft guide](../game/minecraft/README.md). Then run:

```bash
export MINECRAFT_EULA_ACCEPTED=true
export LIVEQUEST_MINECRAFT_TEST=1
export LIVEQUEST_LIVE_COPILOT=1
# Use COPILOT_GITHUB_TOKEN, or explicitly assign an existing token file:
export LIVEQUEST_COPILOT_TOKEN_FILE=/absolute/path/to/copilot-token.txt

uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_tool_calling_agent.py -m game -q -s --headless --recording
```

The tests do not discover credentials in other repositories or replace the
requested model if unavailable. `--no-recording` disables video through the
shared test fixture; it does not disable Agent observations, trajectory images
or snapshots. `--no-headless` uses a dedicated existing X11 desktop.

Each run writes a unique directory under `output/test/`, or under the explicit
`MINECRAFT_TEST_OUTPUT` override, containing:

- `messages.jsonl`, including tool results and provider response identity;
- VM observation PNGs (no images are supplied to the ST model);
- optional `video.mp4`, verified by decoding after a successful run;
- private before/after native world snapshots;
- `result.json` with model settings/metadata, measured duration, Agent exit,
  request usage events, inventory counts/delta, and task or execution outcome.

Task failure fails the pytest case while retaining the score and evidence.
Execution errors remain errors, not task-success-shaped fallbacks. These live
checks consume provider quota. A successful sample does not establish a stable
success rate, a performance ranking, or general task coverage.
