# Veloren integration: implementation and acceptance

Date: 2026-10-22. This is an engineering integration record, not a benchmark
leaderboard, formal task calibration or reproduction of VelorenBench results.

## Runtime correction, 2026-10-25

The first larger Azure batch exposed setup synchronization and entity-selection
defects that the original acceptance runs did not exercise. Fixture initialization
now waits up to 30 seconds for the declared player state after native setup
readiness, without changing health tolerances, repairing state during the wait or
retrying mutations. Transport failures still propagate; timeout diagnostics report
the last observed mismatch.

Encounter initialization now requires a unique newly observed entity with the
declared exact body before checking its private native Enemy binding. The old
upstream helper could select a late-arriving administrator as the new enemy.
Existing scene, body, health, inventory, equipment and scoring requirements remain
unchanged.

Public native steps retain their client-update bounds, but no longer have a
second fixed 60-second wall-clock transport timeout at either RPC layer. Waiting
consumes the existing Episode budget; its cutoff cancels pending tools and
releases native input. Read, setup and cleanup operations retain their transport
timeouts. The world is not paused and task budgets are not extended. This is a
versioned adapter correction, not evidence of equivalent timing across machines.
Affected old and corrected runs must retain separate source provenance.

## Scope and reuse

- Added `game/veloren` with the existing `BaseGame` lifecycle, mode-local public
  interfaces, game-owned prompts, private runtime ownership and before/after
  evaluators.
- VM uses actual native-window images and bounded atomic XTest input. ST uses
  explicitly projected native state and six fixed native skills.
- Reused the installed VelorenBench Python 3.13 harness through a private worker;
  the benchmark-facing Python minimum remains 3.11.
- Reused its validated server, administrator fixture helper, assets, JSONL
  transport, native action receipts and authoring primitives. The original dirty
  VelorenBench checkout and original native build were not changed.
- Copied the matching native build into an independent output directory and
  compiled an explicitly patched ordinary renderer. The patch permits physical
  input only with launch opt-in plus a private session/actor-fenced gate.
- Shared X11 capture, recording and motor binding implementation now live in
  `core/backends/x11`. Minecraft retains its explicit window selectors and public
  mode-local bindings.
- Renamed Minecraft Agent acceptance to
  `tests/test_agent/test_agents_minecraft.py`; added the corresponding
  `test_agents_veloren.py`, reusing the Agent roster and bounded-stop helper.

## Runtime provenance

The inspected upstream checkout was `68b7326` and already had unrelated changes.
The executed harness/source identity comes from its installed runtime binding,
not the dirty checkout's HEAD alone.

| Component | SHA256 |
| --- | --- |
| Original validated runtime JSON | `a66f4a9af38132d49fb43e021f829a1396cb346d70931a178873ad3e875741c5` |
| Bound native source manifest | `f303e8aa0d93c19089db8b070ecefe04dc2afea1e84d1ccf3dee522bd4141ba1` |
| Final physical-input patch | `bfc5fcc95635724896cdf995b01a8a97b2458aa85b1369d7665b0cfb76afb8e7` |
| Final compiled renderer | `6f822454c7f7c8d19e262177bf5f050ffd2af2a5b54cf7fdcb38068f88e7eb89` |

Prepared local runtime:
`output/temp/veloren-native-20261022/runtime.json`.
The checked-in setup script verifies the bound sources, applies the declared
patch in a separate build, compiles offline and emits a hashed runtime receipt.
Reapplying setup to the final prepared tree succeeded without changing the
renderer identity. This verifies reuse of an existing prepared installation;
fresh-machine download/provisioning remains the upstream installation workflow.

No binaries or assets are committed. The patch's native GPLv3 license is retained;
harness and asset licenses remain separate.

## Defects found and corrected

1. The first build invocation did not use the native workspace as its working
   directory, so Cargo did not load its required workspace environment.
   Building from the isolated source directory corrected the compilation error.
2. The small-world spawn was floating in water and could not meet the authoring
   helper's grounding predicate. The integration now uses the standard world
   configuration, matching the upstream authored-fixture contract.
3. Merely restoring physical movement was insufficient. The native bridge also
   replaced camera/controller input and filtered normal HUD events. Those paths
   are restored only while the physical gate is enabled.
4. Expanded real tests found a remaining mouse defect despite successful keyboard
   movement. Xvfb delivered raw XTest motion, but the game retained a stale
   unfocused HUD state because focus events had been discarded during setup.
   A controlled real refocus changed camera yaw from 0 to approximately 0.6 rad,
   identifying the cause. The patch now preserves genuine focus events in
   physical-enabled launches even while actor input is gated.
5. Shutdown explicitly releases the native controller's queued ability inputs.
   Tests verify an actually held `Primary` input before cutoff and an empty
   native queue with physical input disabled afterward.
6. The static control instructions were corrected against the actual native
   bindings: inventory is `I`, not `B`. Expected native no-pickup/empty-slot
   refusals are returned explicitly, while unrecognized native protocol failures
   still fail the integration rather than being disguised as task failure.

The earlier movement-only Agent matrix passed 13 cases, but it was not sufficient
to qualify complete VM behavior. Its artifacts are retained and superseded by
the final renderer checks and repeated Agent matrix below.

## Verified game and regression checks

Final native game/evaluator suite, including fresh current-actor lifecycle fences:
**3 passed in 101.28 seconds**.

| Profile | Evidence directory under `output/test/` | Verified behavior |
| --- | --- | --- |
| VM | `veloren-visual_motor-a1db4f01ce274176b48e41ac01e10aaf` | Actual images; mouse yaw; visible inventory; 5.352 m displacement; held primary input and release; active-wait cutoff; closed public gate; 66 client updates; decoded video; clean worker/server exit |
| ST | `veloren-structured_tool-62e8a3f0d2d14f7a8207e1ce4f994d77` | All six fixed skills; expected native refusals/failure; actual cheese consumption; 9.944 m displacement; active-skill cutoff; 274 client updates; decoded video; clean worker/server exit |

Native frame metadata used to verify HUD/camera/controller effects is private
test evidence. It is not passed to the VM Agent, whose observations remain
XComposite images.

Additional regression validation:

- Existing Minecraft offline checks plus Veloren endpoint counterexamples:
  **4 passed**.
- Actual Minecraft VM shared-input/capture/recording regression: **1 passed in
  30.27 seconds**, directory `minecraft-vm-234fb55212174805be7e4166bc32aa6e`.
- Renamed Minecraft Agent test collection: **15 cases**, no test execution claim.
- Changed Python modules compile; `git diff --check` passes.

## Final real-Agent matrix

**13 passed in 779.56 seconds** on the final renderer hash recorded above:
six Agents in both modes, plus one intentional operator stop.

Each case uses actual `gpt-6-astra`, reasoning `low`, output limit 4096, one
transport attempt and a 180-second wall-clock budget after native admission.
The task is to move two horizontal metres while alive, release movement and
finish. A separate GamingAgent ST case deliberately interrupts after its first
completed game tool. Task scores do not determine engineering acceptance.

| Agent | VM acceptance / displacement | ST acceptance / displacement | Model calls VM / ST |
| --- | --- | --- | --- |
| ToolCallingAgent | passed / 18.521 m | passed / 21.844 m | 2 / 2 |
| DeepSeek harness | passed / 7.527 m | passed / 21.808 m | 2 / 2 |
| Hermes | passed / 8.104 m | passed / 15.648 m | 2 / 2 |
| Orak | passed / 8.174 m | passed / 4.862 m | 2 / 2 |
| smolagents | passed / 15.614 m | passed / 11.683 m | 2 / 2 |
| GamingAgent | passed / 19.015 m | passed / 15.882 m | 6 / 4 |
| GamingAgent intentional ST stop | not applicable | passed / 7.885 m | not applicable / 2 |

All cases received actual `gpt-6-astra` responses and completed a real game-tool
round trip. There were no failed model attempts or reported game-tool errors in
this matrix. Native Agent workers and game workers exited with code 0, no Agent
worker needed forced termination, servers were stopped and videos decoded.
All endpoints had positive health. All thirteen independently scored as task
success, including the intentional-stop case: its first movement already
satisfied the two-metre goal before the operator stopped the Agent. The
intentional stop was not relabeled as task failure. No case reached its deadline.

These deliberately simple scores are not evidence of long-horizon competence or
an Agent ranking. Normal failure handling was separately exercised by the real
ST skill checks: no nearby pickup, an empty inventory slot, and a recipe with
unmet requirements.

Local raw evidence directories under `output/test/`:

| Agent/case | VM directory | ST directory |
| --- | --- | --- |
| ToolCallingAgent | `veloren-tool_calling-visual_motor-ea9ac5fd78a349edb6f74a082a14df33` | `veloren-tool_calling-structured_tool-73ecc98dfeb241b999c80a8a0466acff` |
| DeepSeek harness | `veloren-deepseek-visual_motor-b0a442cfc6ae41d897ae24ff86dc67d0` | `veloren-deepseek-structured_tool-42a497f19ed940bc85d1834b9b09fdbe` |
| Hermes | `veloren-hermes-visual_motor-5fd9e8023da045e7af3dd7117674540d` | `veloren-hermes-structured_tool-b699628d58ba4f24aa59a722a4df1dc1` |
| Orak | `veloren-orak-visual_motor-ee1ca5b23b824ca486290b1e3607c77d` | `veloren-orak-structured_tool-2c96b8f6fa07457b843adb33ffd1ca40` |
| smolagents | `veloren-smolagents-visual_motor-6d0d181c0c004a769a88c1028feec844` | `veloren-smolagents-structured_tool-42f7b6c15fcf461e8f48070207ab7f7b` |
| GamingAgent | `veloren-gamingagent-visual_motor-d50bdb5f591a47e78a1a3519ec12c344` | `veloren-gamingagent-structured_tool-ef0c5cd6382c4a47ba3eb001cc1f51b9` |
| GamingAgent operator stop | not applicable | `veloren-gamingagent-structured_tool-b2f27d894b484c5b8e3233b7b9c874ee` |

The matrix log is `output/temp/veloren-final-agent-check.log`. Raw runtime/model
artifacts are retained locally, not committed with the source report.

## Boundaries and remaining limitations

- Current fixtures are an authored 12x12 elevated platform and ordinary spawn,
  not calibrated long-horizon goals. Platform placement is relative to settled
  spawn, so absolute coordinates can vary slightly between isolated sessions.
- Native client updates are variable-duration counters, not fixed-rate server
  ticks. The world evolves during inference and after public input cutoff.
- Endpoints are ordered private native-client readbacks with identity/checksum
  checks, not atomic world saves or trajectory proofs.
- Current endpoint scoring requires unchanged native actor identity. Cross-respawn
  scoring is not qualified; identity changes invalidate comparison rather than
  silently becoming task failures. Private gate/frame requests use a fresh native
  actor fence, not the original renderer-ready identity.
- Displacement, inventory and health evaluators do not establish route quality,
  intermediate events, crafting provenance or sustained resource ownership.
- ST nearby sensing is not guaranteed visual line of sight. Global/native
  administrator and fixture fields are excluded from public observations.
- The shared motor whitelist does not expose Alt/Super/Meta, function keys or
  punctuation. Native default Alt-block/comma-toggle controls are therefore not
  available; no semantic action silently replaces them.
- Actual acceptance used owned headless X11 displays with native rendering and
  recording. Desktop mode exists but has not been separately certified here.
- XTest and the local process wrappers are integration boundaries, not a sandbox
  against a malicious Agent.
