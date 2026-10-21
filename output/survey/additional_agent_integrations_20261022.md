# Additional native Agent integrations

Date: 2026-10-22, UTC+08:00.
Scope: prioritize recognizable open Agents, especially game systems, preserve
native execution where possible, and validate model/game/lifecycle integration
independently of task success.

## 1. Selection evidence

Official GitHub metadata was queried again during this work. Stars are a dated
attention signal, not performance, scientific adoption, or compatibility.
This is a bounded selection, not a claim to have found every popular Game Agent.

| Candidate | GitHub stars observed | Source license | Disposition |
| --- | ---: | --- | --- |
| [Voyager](https://github.com/MineDojo/Voyager) | 7,275 | MIT | Not admitted: original generated-program and pause/reset semantics do not match the fixed-tool continuously running condition |
| [Mindcraft](https://github.com/mindcraft-bots/mindcraft) | 5,906 | MIT | Deferred: native Mineflayer state, commands and autonomous behaviors need a substantial new environment binding |
| [Cradle](https://github.com/BAAI-Agents/Cradle) | 2,594 | MIT | Deferred: direct UI/game management, pausing and skill curation are not a thin VM/ST translation |
| [GamingAgent](https://github.com/lmgame-org/GamingAgent) | 994 | MIT | Deferred: promising native perception/memory/reasoning modules, but its runner/backend/model-serving integration needs a separately qualified adaptation |
| [Orak](https://github.com/krafton-ai/Orak) | 171 | MIT | Implemented as a labeled native zeroshot fixed-tool game extension, not the original Minecraft/Voyager configuration |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 43,659 | MIT | Popular general framework considered; not implemented in this bounded batch |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | 30,202 | MIT | Popular general framework considered; not implemented in this bounded batch |
| [smolagents](https://github.com/huggingface/smolagents) | 29,961 | Apache-2.0 | Implemented using its native ToolCallingAgent, not CodeAgent |

Orak was selected for extension fit, **not** because it is the most popular
game project. smolagents supplies a widely recognized general tool Agent with
an existing native runtime. Adding unsupported wrappers just to increase the
catalog would not satisfy the user's integration requirement.

### Source scope and fidelity

- Orak pin: `c14e5a01f998c222c76e09da2564aa8b72ebc75e`.
  Its [runner](https://github.com/krafton-ai/Orak/blob/c14e5a01f998c222c76e09da2564aa8b72ebc75e/src/mcp_agent_client/runner/eval.py)
  and [BaselineAgent](https://github.com/krafton-ai/Orak/blob/c14e5a01f998c222c76e09da2564aa8b72ebc75e/src/mcp_agent_client/base_agent.py)
  were inspected and then executed from a dedicated checkout.
- smolagents pin: `96f33faaf028479119ec8d34507b47694cf14e34`.
  Its [ToolCallingAgent](https://github.com/huggingface/smolagents/blob/96f33faaf028479119ec8d34507b47694cf14e34/src/smolagents/agents.py)
  and [Model/Tool conversion](https://github.com/huggingface/smolagents/blob/96f33faaf028479119ec8d34507b47694cf14e34/src/smolagents/models.py)
  were inspected and executed without source patches.
- GamingAgent pin inspected:
  `996d848ae5e3bf68433d663f38ef4da5bdfe5332`.
  [BaseAgent](https://github.com/lmgame-org/GamingAgent/blob/996d848ae5e3bf68433d663f38ef4da5bdfe5332/gamingagent/agents/base_agent.py)
  owns the perception/memory/reasoning step.
  [run_game_episode](https://github.com/lmgame-org/GamingAgent/blob/996d848ae5e3bf68433d663f38ef4da5bdfe5332/lmgame-bench/single_agent_runner.py)
  owns the loop, calls reset/render, lowercases action strings and consumes
  environment reward/performance outputs. Wrapping only `get_action()` would
  omit part of the released system. No runtime qualification is claimed.
- Earlier source evidence for
  [Voyager's bridge](https://github.com/MineDojo/Voyager/blob/55e45a880755d0c8c66ca7fb5fe7962ac8974f89/voyager/env/bridge.py),
  [Mindcraft's Agent](https://github.com/mindcraft-bots/mindcraft/blob/f6a9556cf756e6bd88a75cc2fa0d5aed7599b101/src/agent/agent.js)
  and [Cradle's runner](https://github.com/BAAI-Agents/Cradle/blob/d7752fccf890d8d3818cd1d435f3705f604a1339/cradle/runner/rdr2_runner.py)
  informed exclusions. Current metadata was refreshed, but those systems were
  not reimplemented or rerun. Earlier source limitations are not an impossibility
  proof.

## 2. Implementation and reproducibility

The existing layout is preserved:

```text
agent_framework/
  agents/
    base_agent.py
    process_agent.py
    orak/
      agent.py
      worker.py
      source.json
      setup.py
      requirements.in
      requirements.lock
      patches/0001-lazy-optional-services.patch
      patches/LICENSE.txt
      README.md
    smolagents/
      agent.py
      worker.py
      source.json
      setup.py
      requirements.lock
      README.md
  utils/
    source.py
    worker.py
```

The two new classes inherit `ProcessAgent`; no parallel lifecycle framework,
fake game backend, replacement native decision loop or generic Agent factory
was added. Python workers share `WorkerBridge`; Hermes now reuses its transport
while keeping Hermes-specific native interruption and plugin behavior.

### Orak

Preserved: `BaseRunner.play`, `BaselineAgent.__call__`, zeroshot module dispatch,
local memory updates and native action parsing. Generic prompt modules insert
the task, game-owned instructions and native memory fields. The model adapter
serializes real provider function calls into the native `### Actions` format;
the native pipeline parses them and the environment adapter executes only the
parent's admitted tools.

The patch defers unused provider imports and vector-store/embedding initialization.
It does not change decision or runner logic. This avoids unrelated credential
files and unrequested embedding services on the zeroshot path. The MIT notice
is retained with the patch. No auxiliary model roles, long-term retrieval or
generated-code skills are claimed as qualified.

`GameTransport` calls the real parent-owned public interface. Its native
`evaluate` callback provides no benchmark score; only the Agent's own completion
flag. This is an environment transport adapter, not a simulated successful game.

### smolagents

Preserved: native `ToolCallingAgent.run`, ReAct prompts, history, parser, tool
dispatch and final-answer mechanism. Public Model/Tool extensions mediate the
configured client and fixed game schemas. Native CodeAgent is not instantiated.
Its declared `final_answer` is a local control tool with no game access; this
tool alone cannot satisfy integration acceptance.

Settings: one tool thread, no managed agents/base tools/planning, non-streaming,
1,000 native steps and explicit disabling of stop strings through the native
`REMOVE_PARAMETER` configuration. The benchmark wall-clock budget is authoritative.
These are disclosed configurations, not silent default substitutions.

Both workers use Python 3.11 with checked-in transitive version locks in separate
environments. Orak's lock covers the selected native path; smolagents' lock is
derived from the pinned upstream base dependency manifest. Installation never
occurs inside a run. Checkouts, dependencies, recordings and private saves remain
outside tracked source.

### Source admission and model/observation limitations

Setup applies only declared patches to clean pinned source. Admission constructs
the expected tree in a temporary Git index and compares all tracked working
files with pin-plus-patches. It does not reset or modify a user's actual index.
Dependencies, ignored files and generated builds remain trusted rather than
cryptographically verified; dedicated runtime roots are required.

All real model requests go through the injected parent client with explicit
model, reasoning and output settings. Provider credentials never enter workers.
Native call formatting is not forced into identical memory policies:

- Orak retains its local text-state/action/result projection.
- smolagents retains its own text-formatted action/observation history.
- Each model request gets one fresh public observation; VM gets one current
  image, not a structured-state substitute or retained image history.
- Text-formatted histories do not preserve provider reasoning-continuation
  records as structured provider-native assistant/tool turns would.

These are disclosed differences from the existing baseline/Hermes/DeepSeek
profiles. They must be controlled or stratified in scientific comparisons.

## 3. Acceptance contract

The same [real-game test file](../../tests/test_agent/test_agents.py) now contains
ten ordinary cases (five Agents x two modes) and two operator-stop cases for
the new workers. No fake model replies or mocked game tests were added.

Engineering acceptance requires:

1. The actual response model is `gpt-6-astra`, with the declared low reasoning,
   4096-token output ceiling and one transport attempt.
2. The Agent performs a real game tool round trip and records its result.
   A final answer, import success, tool admission alone, or a skipped test is
   insufficient.
3. Native world time advances during the attempt; access is closed after the
   benchmark gate.
4. Native tools pass admission and workers exit without forced killing or leaks.
5. Operator-stop cases establish shutdown and final evidence after the first
   real game interaction, independently of task completion.

The inventory scorer still measures the original three-log task honestly.
`integration_status=passed` may coexist with `status=task_failure`.
Infrastructure/model/parameter/adapter errors fail tests. Incompatible source
or native protocol is no longer turned into a skip. Missing optional prepared
runtimes still skip explicitly, and do not constitute validation.

## 4. Defects found through real execution

Initial six new-Agent cases: **4 failed, 2 passed, 6 deselected in 313.33 s**.
Orak's regular VM and ST cases passed. The failures were not blamed on Agent
capability:

1. **Responses assistant-history encoding.** smolagents completed its first
   model/game round trip, then received HTTP 400 on its next model request.
   Native history was textual assistant content, which the shared serializer
   incorrectly emitted as `input_text`. A separate minimal real API request
   confirmed a rejection referring to `input_text`/`output_text`. After emitting
   `output_text` for assistant history, the same real request returned `OK.`
   from `gpt-6-astra`. Provider-native saved output replay is unchanged.
2. **Operator-stop test wait semantics.** The new two-task wait used the
   `ALL_COMPLETED` default, so it waited for the Agent to finish rather than
   stopping after the first tool. Fixed to `FIRST_COMPLETED`.
3. **Gate/stop race.** The corrected stop tests then failed twice in 70.31 s:
   the real game gate rejected the next observation before the worker received
   its stop request. Added `AgentAccessClosed`, a `RuntimeError` subtype, at the
   public game boundary. Only an intentional cutoff with successful game end
   maps this specific denial to a stopped exit. Other exceptions still propagate.

Initial failures and native run artifacts were retained. This sequence is why
successful task samples alone cannot establish cancellation or transport validity.

## 5. Final verified results

Final command, with all four external runtime environment variables pointing
to their prepared pins and authorized Copilot credentials supplied explicitly:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py -q -s --headless --recording
```

**12 passed in 906.30 seconds (15:06), no skips.** The ten ordinary cases all
collected three logs; the two intentionally stopped cases did not complete the
task and still passed integration acceptance. No task-failure score was rewritten.

| Agent | Mode | Operator stop | Integration | Task score | Game calls | Seconds to gate |
| --- | --- | --- | --- | --- | ---: | ---: |
| ToolCallingAgent | VM | No | Passed | 3 logs, success | 7 | 67.818 |
| ToolCallingAgent | ST | No | Passed | 3 logs, success | 4 | 23.614 |
| DeepSeek harness | VM | No | Passed | 3 logs, success | 11 | 82.106 |
| DeepSeek harness | ST | No | Passed | 3 logs, success | 4 | 23.860 |
| Hermes | VM | No | Passed | 3 logs, success | 24 | 168.993 |
| Hermes | ST | No | Passed | 3 logs, success | 5 | 32.720 |
| Orak fixed-tool zeroshot | VM | No | Passed | 3 logs, success | 7 | 48.790 |
| Orak fixed-tool zeroshot | ST | No | Passed | 3 logs, success | 4 | 27.821 |
| smolagents ToolCallingAgent | VM | No | Passed | 3 logs, success | 4 | 41.708 |
| smolagents ToolCallingAgent | ST | No | Passed | 3 logs, success | 4 | 28.103 |
| Orak fixed-tool zeroshot | ST | Yes | Passed | 0 logs, failure | 1 | 15.074 |
| smolagents ToolCallingAgent | ST | Yes | Passed | 0 logs, failure | 1 | 11.817 |

All twelve persisted results were checked for `integration_status=passed`,
actual response model `gpt-6-astra`, real public game interactions and video
artifacts. FFmpeg decoded every recording during the tests. All ten external
process attempts were admitted, exited with code zero and needed no forced
termination. Both stop cases recorded `stopped` with
`native_reason=benchmark_game_gate_closed`, and retained valid final snapshots.
World time advanced in all cases (234 to 3,378 ticks).

The lean offline Minecraft checks also passed: **3 passed, 4 deselected in
0.30 seconds**. Pylance reported no errors in inspected changed files; one
unused-parameter hint corresponds to the intentionally game-inert final-answer
handler. A fresh disposable Orak clone verified clean patch application, repeated
preparation and rejection when the declared patch was removed. That disposable
clone was deleted after the check.

### Persistent local runtime locations

- Orak: `output/temp/orak-20261022`
- smolagents: `output/temp/smolagents-20261022`
- Previously prepared DeepSeek/Hermes roots remain unchanged.

Set `LIVEQUEST_ORAK_ROOT` and `LIVEQUEST_SMOLAGENTS_ROOT` to these absolute
paths to reuse the installations. Alternatively use each Agent's documented
setup command to create a fresh dedicated runtime root.

### Final run directories

These are local generated evidence under `output/test/`, not dependencies
required by a fresh checkout:

```text
tool_calling-visual_motor-67a8b9eb649249ee8e8cab3c3128a3d5
tool_calling-structured_tool-4518270501ac424a8d1b5ba229800026
deepseek-visual_motor-10d71d1398c24089aa82ef4cb6adf1aa
deepseek-structured_tool-872da57adaa74072be7d3bdb74bc90d5
hermes-visual_motor-e3735aeeb38d44bcaabe0a79530a25f2
hermes-structured_tool-761d1ba3064a43718343818492046367
orak-visual_motor-d9ba1223bcae49e392f94259fa94c33d
orak-structured_tool-e8b461c8e120453aab26393583b218ed
smolagents-visual_motor-bc472e4431884615856ea5997be2d13a
smolagents-structured_tool-47cebe8aadcd4285b3ff551a73bc8c5c
orak-structured_tool-127deda202e842bb8511dd890f9b400f
smolagents-structured_tool-ddd394205dbb43c4a27570563996cf92
```

### Version fingerprints

| File | SHA-256 |
| --- | --- |
| Orak declared patch | `956cd9f7fa30966972985ff869f317e5ccdbbf8156abd3cc4ced35b7dd506cf1` |
| Orak dependency lock | `6df3bc9e42518a210c6e80a8f162f96c31178836ffdc8b8966fbacaa7bb56f8b` |
| smolagents dependency lock | `cf44f4c96fb8e2951d6b2d9b654d5a3e138c30b6c9c10e7a9ee6cb4f6a1b1d5c` |

## 6. Remaining scope

This qualifies two explicit integrations and preserves the existing three,
not every feature of either upstream project or every provider/model setting.
It does not establish task difficulty, long-horizon planning performance or an
Agent ranking. These are single integration examples on the same smoke fixture.

The next game-specific candidate worth a bounded implementation attempt is
GamingAgent's native runner plus perception/memory/reasoning pipeline. A future
Mindcraft/Cradle admission should explicitly decide whether the original skills,
observations and timing can be retained or whether a labeled variant/new
condition is required. Do not silently weaken current VM/ST permissions to add
a more popular name.
