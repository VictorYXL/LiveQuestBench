# Game and Agent readiness audit

Date: 2026-10-22. Scope: current Minecraft/Veloren backends and six integrated
Agents, before implementing the production benchmark orchestration layer.

## Conclusion

The current supported headless VM/ST configurations are operational in fresh
real-game/model tests. They are ready to support benchmark-runner development.
This is not certification of all tasks, desktop configurations, provider/model
combinations or long-running reliability.

The architecture is substantially consistent, but the implementation is **not
uniformly styled or fully type-annotated**. Necessary native differences should
not be removed merely to make files look alike.

## Fresh execution evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Combined game/evaluator suite | 10 passed in 224.10 s | [Game log](../temp/game-audit-20261022.log) |
| Original complete Agent matrix | 28 passed in 1955.90 s | [Agent log](../temp/agent-audit-20261022.log) |
| DeepSeek regression after stop-classification fix | 6 passed, 24 deselected in 337.89 s | [Focused log](../temp/deepseek-stop-audit-20261022.log) |
| Combined collection after added stop cases | 40 tests collected | 10 game/evaluator + 30 Agent cases; collection is not runtime qualification |
| Worker syntax and whitespace | `node --check` and `git diff --check` passed | Not substitutes for real execution |

The game suite contains six real-game cases and four small offline
consent/evidence/evaluator checks. The original Agent matrix contains 24
game/profile/Agent cases and four intentional stops. The focused run repeats
DeepSeek's four normal combinations and adds two real-game stop cases.
Consequently, **30 distinct current Agent cases are covered**, not 34 distinct
Agent configurations or one 40-case execution command.

All Agent runs used `gpt-6-astra`, reasoning `low`, max output 4096, one request
attempt, a 180-second Episode budget, owned headless displays and recording.
Game/model tests used the previously authorized credential file through the
client; credential contents were not printed.

| Agent | Minecraft VM | Minecraft ST | Veloren VM | Veloren ST |
| --- | --- | --- | --- | --- |
| ToolCallingAgent | Pass | Pass | Pass | Pass |
| DeepSeek harness | Pass after wrapper fix/recheck | Pass | Pass | Pass |
| Hermes | Pass | Pass | Pass | Pass |
| Orak | Pass | Pass | Pass | Pass |
| smolagents | Pass | Pass | Pass | Pass |
| GamingAgent | Pass | Pass | Pass | Pass |

"Pass" means integration acceptance, not general task capability. The current
six stop cases cover DeepSeek/Orak/smolagents/GamingAgent in Minecraft ST and
DeepSeek/GamingAgent in Veloren ST. They do not exhaust every Agent's stop path.

A final direct check of the latest result for all 30 case identities confirmed:
integration passed, actual configured response model, real tool interactions,
PNG observations for every VM case, and return code 0 without forced termination
for every external Agent worker. The tests also validated recording decoding,
world/client progression and post-end public-access denial.

## Defects found and fixed

### 1. Combined pytest collection failed

Running both game directories together failed with `import file mismatch` because
both contain a module named `test_game.py`. Earlier per-game commands had not
exposed the collision.

Added `--import-mode=importlib` to the existing
[pytest configuration](../../pyproject.toml). Both real game suites subsequently
ran together successfully. No renaming or extra package-marker files were needed.

### 2. DeepSeek treated expected native cancellation as an exception

The original
[DeepSeek Minecraft VM result](../test/deepseek-visual_motor-f8c911fce2694819a0d4b1dfcbd61215/result.json)
reached the benchmark deadline with 2/3 oak logs and 11 dirt blocks, after 31
completed tool calls and 3598 world ticks. The last request was cancelled at the
deadline. This was a legitimate unsuccessful task trajectory, not a broken
model/tool connection.

Separately, the
[worker log](../test/deepseek-visual_motor-f8c911fce2694819a0d4b1dfcbd61215/external/worker.log)
showed an actual wrapper defect: its native turn reason was
`aborted / user`, caused by the benchmark's SIGTERM handler, but the wrapper
raised "Native turn did not complete" and exited 1. The parent correctly reported
`stopped`, yet the worker-level classification was misleading.

The [worker](../../agent_framework/agents/deepseek_harness/worker.mjs) now records
whether the benchmark requested stop and accepts only the corresponding native
user-abort as `stopped`, with a clean exit. Unexpected aborts still fail. This
changes our wrapper only, not the pinned upstream source.

Added explicit DeepSeek ST stop cases to both real-game Agent suites and required
clean DeepSeek worker exits in the Minecraft suite. The six-case focused run
passed. Its Minecraft normal VM rerun succeeded at the task; the original failed
trajectory remains preserved and must not be erased or relabeled as success.

Key regression results:

- [Minecraft normal VM](../test/deepseek-visual_motor-1dda267ed63949b384d95e232aab6a2a/result.json)
- [Minecraft intentional stop](../test/deepseek-structured_tool-3f6b2d5307094f6ea19be940f1b604bf/result.json):
  integration passed, task failed, worker exited 0.
- [Veloren intentional stop](../test/veloren-deepseek-structured_tool-0fceef93b709420197945070e98a5b59/result.json):
  integration passed, task succeeded before interruption, worker exited 0.

## Structural/style review

### Consistent and appropriate

- Both games implement the same administrative
  [BaseGame](../../game/base_game.py) lifecycle and expose restricted interfaces.
- All Agents implement [BaseAgent](../../agent_framework/agents/base_agent.py).
  Five external Agents reuse
  [ProcessAgent](../../agent_framework/agents/process_agent.py); the in-repository
  baseline owns its own native loop.
- External Agent directories consistently hold a wrapper, worker, source pin,
  explicit setup entry and README. Extra patches/locks are present where needed.
- Python workers share [WorkerBridge](../../agent_framework/utils/worker.py).
  DeepSeek's JavaScript worker is a justified native-runtime difference.
- VM uses the same [X11 interface](../../core/backends/x11/interface.py), capture
  and recording implementation in both games.
- Game prompts, public bindings and private evaluators remain game-owned.
- Both Agent suites share the Agent roster and bounded-stop helper, while keeping
  game-specific fixture/scoring assertions.

### Not fully uniform; not current runtime blockers

- Constructor naming differs: Minecraft uses `display`, Veloren `display_name`.
  Fixture types differ intentionally, but generic configuration dispatch will
  need explicit game-specific construction rather than assumed identical kwargs.
- JSON-writing helpers differ in name, explicit encoding and atomic-replacement
  behavior. Do not promise one shared crash-durability contract yet.
- Type completeness varies. Veloren session/structured code and some upstream
  adapter methods use bare dictionaries, unparameterized tasks/futures or missing
  return annotations. Existing code also contains long lines and varying import
  grouping; no repository formatter/linter policy currently enforces uniformity.
- Acceptance reports and assertions are not fully identical: Minecraft records
  server world ticks, Veloren native client updates; worker-exit assertions differ
  for some older wrappers. These are not interchangeable timing measurements.
- Both concrete games provide `get_instructions`, but the current minimal
  BaseGame contract does not declare it. This should be addressed deliberately
  when implementing a typed generic runner.

Two focused Pylance diagnostic queries reported no error diagnostics; one
reported the unused parameter in the base `_prepare_home` hook. This is not a
workspace-wide strict type certification.

### Intentional semantics, not style defects

Minecraft freezes world ticks at its terminal snapshot boundary; Veloren closes
public input but the world continues, and its snapshot is a client readback.
ST skill names, units, coordinate systems and receipts are also game-specific.
The future runner must preserve these disclosed differences rather than assuming
identical atomic endpoints or action vocabularies.

## Handoff

No new games/Agents, new dependencies or production benchmark runner were added.
Related README test documentation was corrected. Existing integration changes,
including Veloren, remain uncommitted; this audit did not commit or push.
All three test commands completed. No test service was left running deliberately.
