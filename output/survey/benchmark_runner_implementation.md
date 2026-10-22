# Serial Benchmark Implementation and Acceptance

**Later update:** [Explicit fixture acceptance](explicit_fixtures_acceptance.md)
supersedes this report's generated-world/fill-command/named-Veloren-fixture
configuration. The execution evidence below remains the original historical run.
The subsequent [organization update](benchmark_organization_acceptance.md)
renames `registry.py` to `factory.py`, moves game bindings and X11 into the game
layer, and removes the empty preparation hook.

## Scope and implemented decisions

The agreed Task/Experiment YAML examples are executable through the thin root
`run_benchmark.py` launcher. `benchmark/config.py` owns strict loading and explicit
file resolution; `registry.py` binds the two games, six existing Agents and three
model providers; `runner.py` owns serial scheduling and Episode boundaries;
`results.py` persists evidence, provenance, request accounting and grouped results.
No task-name registry, config inheritance, automatic discovery, Episode retries,
parallel scheduler or universal game-action vocabulary was introduced.

Task identity includes game, task ID and task type. The existing one-experiment-
per-game files retain both VM and ST references and one repetition each.
The experiment filenames were not silently renamed to `suite.yaml`.
No revision/family/supported-tracks metadata was added to Tasks.

The common game base now declares its existing public instruction method.
Minecraft exposes private ready-phase initialization commands; the binding
currently admits only explicit vanilla overworld fill cuboids, verifies server
acknowledgements and reads back native initial-world blocks/inventory.
This restriction is explicit rather than pretending arbitrary commands are
validated. Evaluator parameter validation is shared with actual scoring.
Native Agent loops and their pinned integration profiles remain unchanged.
The previous live-test bounded runner now reuses the production implementation.

ST allowlists restrict both advertised tool schemas and executable public tool
dispatch. VM remains on-demand. Administrative initialization/evaluator parameters
and snapshot paths are not included in AgentContext.

## Outcome and evidence semantics

- Separate execution status, measurement validity, task outcome and Agent exit.
- Start a monotonic budget immediately before begin; reasoning/network waits do
  not pause the running game. Budget-expired Agents are not started.
- Revoke game access before requesting retirement. Keep final evidence after an
  execution error or operator interruption when the game boundary succeeds.
- Preserve execution, scoring and cleanup errors; stop scheduling after errors,
  retaining all remaining scheduled rows as not-run.
- Refuse existing output directories. An admission failure also persists a
  summary and must not be silently overwritten on retry.
- Persist resolved configuration and exact YAML text/hashes, implementation
  hashes/revision, effective launch options, public observations, messages,
  provider-reported model identity, tool attempts, model request attempts,
  private snapshots, evaluation, recordings and per-Episode results.
- Group only by game/task/mode. Invalid or unstarted cases remain visible beside
  valid-completed denominators. Unknown usage/cost is never imputed as zero.
- CLI 0 means successful execution, not successful gameplay; 1 means an error;
  130 means operator SIGINT.

## Real built-in experiment execution

Both actual built-in Experiment files ran through the production CLI, with
headless rendering and recording. Every response-bearing trajectory reported
`gpt-6-astra` in provider response metadata.

| Game | Mode | Model requests | Tool calls | Private task outcome |
| --- | --- | ---: | ---: | --- |
| Minecraft collect_3_logs | VM | 11 | 10 | Success: initial 0, final 3 oak logs |
| Minecraft collect_3_logs | ST | 5 | 4 | Success: initial 0, final 3 oak logs |
| Veloren move_2_metres | VM | 2 | 1 | Success: 18.73828125 horizontal metres, alive |
| Veloren move_2_metres | ST | 2 | 1 | Success: 5.8603515625 horizontal metres, alive |

Evidence:

- [Minecraft summary](../benchmark_acceptance/minecraft-first/summary.json)
- [Veloren summary](../benchmark_acceptance/veloren-first/summary.json)

Both Minecraft modes kept exactly 3 oak logs in native saved inventory.
VM evidence contains 11 Minecraft and 2 Veloren distinct PNG observations.
All four Episodes have nonempty native-view video. Veloren VM moved off the
platform and descended; that remains a valid result under the explicitly
distance-plus-alive scorer, not proof of precise navigation or minimal motion.
No unsuccessful trajectory was replaced to improve these scores.

## Lifecycle and regression checks

1. Focused offline suite: **8 passed, 1 deselected**. Covers duplicate/invalid
   YAML, explicit paths, tool admission and executable restrictions, malformed
   scorer thresholds, normal/expired deadlines, cancellation, gate failure,
   execution/scoring/cleanup fault persistence, no overwrite, unknown usage,
   mode-separated denominators and shared native scorer counterexamples.
2. Real CLI lifecycle suite: **3 passed in 151.36 s**:
   - DeepSeek native ST, with only MoveTool admitted: two model requests, one
     actual tool call, successful task, admitted native worker, no forced termination.
   - Three-second deadline: completed execution with a valid unsuccessful score,
     stopped Agent and CLI exit 0, not an infrastructure failure.
   - OS SIGINT after the first live observation: CLI exit 130, cancelled result,
     final endpoint preserved and cleanup completed.
3. Final deadline regression: **1 passed in 48.28 s**. The measured boundary
   request was 0.001126559 s after the configured deadline; acknowledgement took
   0.043629206 s. Total active wall time was 3.044755765 s. These values disclose
   scheduling/cutoff latency, not an assertion of instantaneous termination.
4. Existing Minecraft DeepSeek ST operator-stop regression, now importing the
   production helper: **1 passed in 34.11 s**.
5. Repository collection: **58 tests collected**; no full 58-test or full
   30-Agent live matrix rerun is claimed. Changed Python modules compiled.

Additional live evidence:

- [DeepSeek CLI result](../test/benchmark-native-f600f74b2cd04f34afda65943334fad4/run/summary.json)
- [SIGINT result](../test/benchmark-interrupt-4ab37fe47fda4426bf3f80bfb3b69630/run/summary.json)
- [Final deadline result](../test/benchmark-deadline-b6e453f1c8574e378297660b7b583dee/run/summary.json)

All inspected Veloren worker cleanup receipts report return code 0; the six
recorded server PIDs from these acceptance runs were no longer present.
The native-Agent result explicitly records no forced termination.

The four built-in runs preceded later validator extraction and richer timing
logging; each retains its own original configuration/source hashes. Subsequent
changes were covered by focused offline and live regressions, not by silently
rewriting those initial results.

## Limits and remaining research work

This completes the first usable serial Benchmark execution layer, not the
scientific benchmark. The example tasks are short integration probes, not a
qualified long-horizon distribution. Larger task coverage, task calibration,
experimental freezing and holdout evaluation remain separate work.

Minecraft freezes its native world at the endpoint; Veloren continues evolving
after public input revocation and captures a non-atomic endpoint.
There is no extra game-terminal detector, resumable scheduler, monetary pricing,
untrusted-code sandbox or cross-mode aggregate score.
The CLI exposes all six existing Agent bindings, but this change newly exercised
only ToolCallingAgent and DeepSeek through the production launcher. Hosted
OpenAI and vLLM factories reuse existing clients; neither received a new live
provider qualification during this task.

Pylance's diagnostic endpoint returned empty results, but its syntax endpoint
could not recognize the new workspace files. Therefore this report does not
claim strict project-wide type certification. Compilation and executed tests
are the concrete validation evidence.

No game installations, upstream checkouts, unrelated historical outputs or
credentials were changed. The current work has not been committed or pushed.
