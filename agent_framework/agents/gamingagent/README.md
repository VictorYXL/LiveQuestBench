# GamingAgent

[`GamingAgent`](agent.py) runs LM Games' native `run_game_episode` and
`BaseAgent.get_action` harness: perception, trajectory memory, reflection,
reasoning, action-memory update and the next environment step. This is a
**fixed-tool game extension**, not a reproduction of a released GamingAgent
game configuration or benchmark score. It does not merely wrap `get_action()`
in a replacement decision loop.

[`source.json`](source.json) pins MIT-licensed `lmgame-org/GamingAgent` at
`996d848ae5e3bf68433d663f38ef4da5bdfe5332`.

## Installation

```bash
uv run --locked python -m agent_framework.agents.gamingagent.setup \
  --root "$PWD/output/runtimes/gamingagent"
export LIVEQUEST_GAMINGAGENT_ROOT="$PWD/output/runtimes/gamingagent"
```

Setup uses a dedicated checkout and locked Linux Python 3.11 environment.
[`requirements.in`](requirements.in) selects the native harness/runner's
dependencies; [`requirements.lock`](requirements.lock) pins their resolution.
Provider SDKs, emulators, native game packages and credentials are not installed
in this runtime. The native code is imported directly from the checkout.
Dependency installation never happens during an episode.

To deliberately regenerate the lock on Linux:

```bash
uv pip compile agent_framework/agents/gamingagent/requirements.in \
  --python-version 3.11 \
  --output-file agent_framework/agents/gamingagent/requirements.lock
```

This lock is not a certification of other Python versions or operating systems.

## Declared patch and extension points

[`0001-injected-transport.patch`](patches/0001-injected-transport.patch):

- Adds an optional API-manager factory to native `CoreModule`. The default
  provider manager is imported lazily and remains the default when not injected.
  Our factory supplies only model transport, not perception/planning logic.
- Defers game/emulator imports until native environment creation or an applicable
  game-specific episode branch. The benchmark supplies the environment instead.
- Lets an environment explicitly preserve action-string case. Existing games
  still lowercase actions; JSON tool arguments must retain their exact case.

The upstream MIT notice is retained in [`patches/LICENSE.txt`](patches/LICENSE.txt).
Admission verifies the entire tracked tree against the pin plus declared patch.
It rejects undeclared source edits; dependencies remain trusted, not sandboxed.

The supported native custom-module slot supplies a reasoning response parser:
provider function calls become a JSON action envelope for the native runner.
This replaces the default game-action regex, which strips JSON quotation marks.
Native `ReasoningModule.plan_action` and all memory/reflection logic remain in
use. Plain final model text is an Agent return condition, never a task score.

## Model, game and lifecycle boundaries

- All generation roles use the injected model, reasoning setting and output
  ceiling. Perception/reflection use `tool_choice=none`; reasoning alone can
  propose fixed game tools. All calls count toward the same wall-clock budget.
  Native module defaults are explicitly configured rather than silently
  ignoring their high-reasoning setting in transport.
- Harness enabled; native perception enabled; reflection enabled; trajectory
  capacity 20 native entries (observations and actions are separate entries);
  summary disabled; no grid scaffolding; maximum 1,000 native steps. The
  benchmark wall-clock limit normally binds first.
- VM uses native `both` mode: only the permitted frame and public accompanying
  text, never hidden structured state. Native OpenCV resizing and visual
  description are retained. ST uses native `text` mode, where perception passes
  through approved state and makes no separate visual-model call.
- Unlike the default process profiles, this profile captures an observation at
  native environment boundaries. The worker receives only public text/PNG data,
  persists the frame and feeds the native resized frame to the model bridge.
  No fresh image is silently substituted at each model call. The world keeps
  advancing during perception, reflection and reasoning, so observation age is
  part of the method. Native memory stores text descriptions, not old images.
- Game-owned instructions/task and generic role prompts are supplied at runtime.
  The wrapper contains no Minecraft strategy. It records those prompts and
  native module configuration in each attempt directory.
- Native `reset()` is a one-time attachment to the already initialized game,
  not permission to reset it. `render()` needs no additional call because the
  real client renders continuously. Only the public interface executes actions.
- Private score/reward/done signals are not provided to the Agent. The native
  runner's numeric accumulators receive NaN for unavailable reward/performance;
  persisted native results use JSON null and `score_status=not_exposed`.
  Only the benchmark's private before/after evaluator produces task scores.
- The native loop ends on its own final answer or step limit. The benchmark
  gates game access first, then requests worker termination. The common signal
  exception bypasses native `except Exception` recovery. Model, transport and
  game errors are not relabeled as ordinary task failure.
- This is cooperative process isolation, not an OS security sandbox. Only this
  pinned/profiled path is qualified, not upstream CLI games or optional services.

## Construction and real validation

```python
from agent_framework.agents.gamingagent import GamingAgent

agent = GamingAgent(
    client, output_dir=output_dir, tools=tools, observe=observe,
    model="gpt-6-astra", reasoning_effort="low", max_output_tokens=4096,
)
```

Prepare the real game/model as described in the
[root README](../../../README.md#agent-validation), then run:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py -k gamingagent --headless --recording -q -s
```

The three cases cover actual VM/ST interaction and ST operator stop. They verify
the native reflection/action memory and VM visual description in addition to
configured model identity, world advancement, real tools, access revocation,
video decoding and process cleanup. Task success is independently reported,
not required for integration acceptance. Native module logs, model requests,
captures and before/after evidence are retained for diagnosis.
