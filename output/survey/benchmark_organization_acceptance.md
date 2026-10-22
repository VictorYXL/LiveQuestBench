# Benchmark Organization and Publication Acceptance

## Final ownership

- `benchmark/runner.py` keeps experiment scheduling, Episode lifecycle and
  bounded Agent retirement together; no additional runner framework was added.
- `benchmark/factory.py` replaces the former `registry.py`. It selects game,
  Agent and model implementations without interpreting game-specific fixture
  fields or scoring evidence.
- `game/bindings.py` contains shared restricted controls, allowlist enforcement
  and the private GameBinding contract.
- Each game's `binding.py` owns fixture admission, tool admission, evaluator
  selection, initial-evidence checks and private scoring.
- `game/backends/x11/` owns the shared display, capture, input and recording
  implementations previously located under `core/`, then temporarily under
  `benchmark/`. All current imports use the game-owned location.
- The unused `prepare` callback and its no-op implementations were removed.
  Game startup completes initialization before the initial evidence boundary.

A syntax-tree dependency check found no imports of benchmark modules anywhere
under `game/`. Shared code depends on the existing public Agent tool types,
not benchmark configuration. There is no dynamic plugin registry or config
inheritance mechanism.

## Verification

1. Focused offline runner, fixture and scorer suite: **15 passed, 3 deselected**.
   Added direct per-game admission checks that bypass the benchmark factory,
   reject unknown tools/evaluators, and create no runtime output during admission.
2. Production Minecraft VM/ST experiment with recording: both tasks succeeded,
   both with native inventory increasing from zero to three oak logs.
   VM: 22 requests, 21 tool calls, 22 distinct PNGs.
   ST: 5 requests, 4 tool calls.
3. Production Veloren VM/ST experiment with recording: both tasks succeeded.
   VM: 7.671875 horizontal metres, 100 health.
   ST: 21.986328125 horizontal metres, 100 health.
   Both used two model requests and one tool call. As before, leaving the
   platform is not disallowed by the distance-plus-alive evaluator.
4. Real production CLI/native-Agent/deadline/SIGINT suite:
   **3 passed in 150.70 seconds**.
5. Minecraft source-world hashes remained unchanged. All four videos were
   nonempty. Both recorded Veloren native servers stopped without forced
   termination, and their recorded PIDs were absent afterward.
6. Python compilation and tracked-file whitespace checks passed.
   **64 tests collected**; no full 64-test execution or full native-Agent matrix
   rerun is claimed.

Evidence retained locally:

- [Minecraft run](../benchmark_acceptance/minecraft-game-owned-bindings/summary.json)
- [Veloren run](../benchmark_acceptance/veloren-game-owned-bindings/summary.json)

Pylance initially returned no Minecraft-binding diagnostics, but later
diagnostic calls timed out and signature discovery returned no call sites.
These results do not establish strict type certification; the executed checks
above are the validation evidence.

## Publication scope

The authorized commit includes the previously uncommitted executable Benchmark,
explicit Task/Experiment configuration, native Minecraft fixture, composite
Veloren initialization, evaluator threshold changes, this ownership cleanup,
tests and directly related documentation. Three implementation/acceptance
reports are retained as source-controlled evidence.

Historical trajectories, recordings, game installations, external Agent
environments and credentials remain outside the commit. The larger ignored
survey index and unrelated research reports are not added merely to publish
this engineering milestone.

See [runner acceptance](benchmark_runner_implementation.md) and
[fixture acceptance](explicit_fixtures_acceptance.md) for preceding decisions,
original execution evidence and remaining scientific/runtime limitations.
