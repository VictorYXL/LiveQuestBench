# Veloren

LiveQuestBench evaluates native Veloren gameplay in two modes:

- **VM:** game pixels and bounded keyboard/mouse input.
- **ST:** permitted native state and fixed game tools.

Tasks cover movement, gathering, crafting, equipment, recovery, combat and NPC
interaction. The server continues to evolve while the Agent reasons and acts.
See the [project guide](../../README.md) for experiments, Agents and models.

## Installation

First prepare a [VelorenBench](https://github.com/wyaaaattwho/VelorenBench)
installation and its matching native build cache using that project's setup
instructions. LiveQuestBench reuses that installation; its setup command is not
a standalone game downloader.

Requirements:

- Linux/X11, Xvfb for headless sessions, and a usable Vulkan driver.
- FFmpeg for recording, plus `patch` and `uv`.
- The upstream pinned Rust toolchain and build cache.
- The upstream harness's Python 3.13 environment; LiveQuestBench uses its
  separate project environment.

On Ubuntu, install `x11-utils` for `xdpyinfo` and `libxkbcommon-x11-0` for the
renderer. The keyboard library is loaded at runtime: successful compilation
alone does not prove that it is installed.

Set `VELOREN_INSTALLATION` to the upstream installation JSON,
`VELOREN_BUILD_CACHE` to its matching cache, and `VELOREN_RUNTIME_DIR` to a new,
dedicated destination:

```bash
uv sync --locked --extra veloren --group test
bash game/veloren/setup.sh \
  --installation "$VELOREN_INSTALLATION" \
  --build-cache "$VELOREN_BUILD_CACHE" \
  --root "$VELOREN_RUNTIME_DIR"
export LIVEQUEST_VELOREN_RUNTIME="$VELOREN_RUNTIME_DIR/runtime.json"
```

Keep the upstream installation available after setup. Use a separate build
destination rather than modifying the original cache, and allow sufficient
space for a native build. Rebuild if setup reports an incompatible runtime.

The integration disables the upstream automatic protection controller so that
combat decisions remain with the Agent. Ordinary enemy AI, damage, blocking
and the game's native downed/death mechanics remain active.

Route evidence version 2 records accepted native terrain-collision increments,
not interpolated points between rendered frames. Route tasks require a rebuilt
runtime; the original distance-gap validity check remains unchanged. This
observer does not alter physics, controls, or the game clock.

Combined peer fixtures retain both readiness barriers: Group setup cannot
finalize supplies, and original supplies are created and pre-aged before deferred
enemies spawn. Cached journal projections retain original drop and merge events
across that boundary. These source integrations require native requalification;
offline unit regressions do not validate previously qualified runs on new source.

Veloren native source and bundled map retain their applicable GPLv3 terms.
The [native license notice](patches/LICENSE) is retained. Other components and
assets have their own licenses; do not assume blanket redistribution rights.

## Run an experiment

Select a configuration from
[Veloren experiments](../../config/veloren/experiments/).
For a first run, choose `mountain_workshop_circuit`, one Agent and one repetition using the
[smoke-test example](../../README.md#running-an-experiment).

With `EXPERIMENT_CONFIG` and `RESULTS_DIR` set to your chosen experiment and
dedicated result destination:

```bash
uv run --locked --extra veloren python run_benchmark.py \
  --config "$EXPERIMENT_CONFIG" --output "$RESULTS_DIR" \
  --headless --recording
```

Prepare the selected Agent and model credentials before launching.
Use a dedicated virtual display or authorized X11 desktop. Do not interact
manually with a display under Agent control.

## Tests

Run offline checks first:

```bash
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_game/veloren -q
```

After preparing the runtime, enable native ST/VM lifecycle checks:

```bash
LIVEQUEST_VELOREN_TEST=1 \
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_game/veloren/test_game.py -q -s --headless --recording
```

These tests exercise real game interaction, stopping, private scoring and
recording without model calls. Select the full `tests/test_game/veloren`
directory for broader checks. Use `--no-recording` to omit videos, or
`--no-headless` to use an existing desktop.

For real Agent tests, prepare the selected
[Agent](../../README.md#agents) and authorized Copilot credentials, then enable
`LIVEQUEST_VELOREN_TEST=1` and `LIVEQUEST_LIVE_COPILOT=1`:

```bash
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_agent/test_agents_veloren.py -k tool_calling \
  -q -s --headless --recording
```

Model tests consume quota. Replace the selector to test another installed Agent.
A valid task failure differs from an integration error; skipped tests do not
verify a working runtime.

## Tasks and fixtures

- [ST task definitions](../../config/veloren/tasks/structured_tools/)
- [VM task definitions](../../config/veloren/tasks/visual_motor/)
- [World fixtures](../../config/veloren/fixtures/)

| Selection | Typical objectives |
| --- | --- |
| L1 | Movement, pickup, supplied-input crafting, equipment and recovery |
| L2 | Resource gathering, terrain routes, encounters, gliding and trading |
| L3 | Preparation under resource constraints, return journeys, companions and contracts |

Levels organize the development catalog, not calibrated difficulty guarantees.
Each task declares its exact budget, starting state, permitted tools and goal.

`market_hunt_return` uses a roofed merchant shop and a separate eastern hunting
yard; `dual_legoom` uses a rock divider with an east-side route. These are task
scene revisions, not changes to NPC AI, budgets or scoring. Preserve task hashes
when comparing layouts. Encounters can start 10-96 metres away; distant targets
are identified privately during setup, without extending ST's 32-metre public
projection or exposing hidden state to VM.

### Add a task

1. Copy a task with the desired mode and scoring pattern.
2. Set a unique ID, public objective and time budget.
3. Declare the map and initial conditions in `fixture`.
4. Select evaluator settings and the ST tools, if applicable.
5. Add the YAML path to an experiment.
6. Verify native initialization, reachability and scoring in each supported mode.

Coordinates use **x/y horizontally and z vertically**. `fixture.world_path`
selects a native map, relative to the task YAML or as an absolute path. A map is
not a complete live-world checkpoint: initial player state, terrain preparation
and other fixture settings must also be declared.

For two-player fixtures with `peer_group: true`, both native players attach and
verify Group membership before the original encounter is spawned. The setup
administrator then disconnects before the initial snapshot and gameplay. This
avoids pre-play attacks during peer attachment without protecting, healing or
repositioning players after play starts.
The immutable setup-journal prefix is validated before spawning the encounter;
initial snapshots validate its new suffix rather than repeatedly parsing the
entire construction history while an enemy can attack. The native journal and
its scoring events are unchanged. Deferred encounter target and player binding
reads use that same validated prefix, off the worker event loop, and select only
the latest native binding snapshot; an absent target is not recovered from an
older snapshot. This removes repeated full-journal reads between spawning the
enemy and retiring the administrator. It does not relax opening position or
health verification or guarantee a successful opening on every fixture.

Choose an existing fixture pattern for platforms, terrain obstacles, stations,
supplies, encounters or a native settlement. Supplies can expire according to
native game rules; expose relevant deadlines in the objective rather than
silently replenishing resources.

For native teams, the owner defers the first creation of declared supplies
until all peer clients have attached and acknowledged setup readiness. The
administrator disconnects during peer attachment, then reconnects only for
that original drop and its private readback before admission. This avoids
spending the source's native lifetime on renderer attachment. It does not
recreate an expired source, pause expiry, alter pre-age settings, extend the
deadline, or bypass identity and remaining-lifetime checks. Single-player
supply initialization keeps its existing ordering.
Once deferred supply initialization starts, failure or cancellation before
creation and binding complete leaves that session inadmissible: a repeated
request cannot recreate supplies whose native drop may already have happened.
The setup-attempt flag is retained in receipts.

For dialogue, trading, skills, gliding or companions, start from a task that
already admits those features. Do not assume that every task exposes every
available tool.

### Match scoring to the objective

| Scoring pattern | What it establishes |
| --- | --- |
| Displacement | Movement relative to the starting position and final survival |
| Inventory / health | Declared final values or net changes |
| State | Simultaneous equipment, recipe, inventory, health and arrival conditions |
| Encounter | Player contribution, designated native target deaths and declared survival conditions |
| Expedition / contract | Supported ordered preparation or native contract-completion evidence |

Endpoint inventory does not prove a particular recipe, pickup or transaction.
Position does not prove the route taken. Use event-backed task patterns for
goals that require order, ownership or an attributed combat/contract event.

Inventory `min_count` and `min_delta` constraints are independent; specify at
least one. Health constraints likewise distinguish final health from change.
Arrival conditions should state horizontal/vertical tolerance, grounding and
speed where required.

Jump and glide goals use sampled native movement evidence, which can miss
brief transitions. Do not describe sampled effects as exact server event counts.
State all measured requirements in the public task and test their physical
feasibility through the admitted controls.

## Controls and observations

### VM

VM provides the controlled window's current pixels and capture timing, not a
hidden map, inventory transcription or coordinate feed. Actions are bounded
keyboard/mouse commands with at most 10 seconds of explicit waits per call.
Held inputs can persist across calls and model reasoning.

Use the [public control instructions](prompts/) for key bindings and limits.
Some native keys, including Alt, are outside the permitted keyboard vocabulary;
do not assume every desktop control is available. No semantic skill is silently
substituted for an unsupported key.

### ST

ST supplies player position, motion, health/resources, equipment, inventory,
nearby native entities, known recipes and nearby interactable objects. This is
local native sensing, not a visual line-of-sight guarantee or a whole-world map.

| Tool family | Purpose |
| --- | --- |
| Movement and view | Bounded movement, turning, jumping and aiming |
| Items and preparation | Pickup, item use, crafting and equipping |
| Combat | Wielding, bounded attacks, blocking, rolling and stopping |
| Optional task tools | Dialogue, trading, gliding, skills and pet commands |
| Respawn | Request native recovery while dead |

Movement and attacks use bounded client updates, whose real duration can vary.
Tools do not select routes, track targets or complete a combat/trade policy for
the Agent. Use each task's admitted tool schemas for exact arguments and limits.

Invalid arguments are rejected explicitly. Native refusals, such as missing
materials or an out-of-range target, are not task successes. Interrupted actions
may already have effects and must not be assumed safe to retry.

## Death, timing and results

ST exposes `RespawnTool`; VM uses native controls. Respawn is Agent-chosen and
retains native waypoint/spawn, inventory and equipment-durability rules. It does
not reset enemies, grant items or restart the Episode budget. Existing no-death
conditions still apply after recovery.

The world continues during model calls, tool execution and after public control
ends. Final snapshots are private readbacks, not an atomic server pause. Their
timing semantics differ from Minecraft's save-boundary protocol.

Results include task scoring, native death counts, request timing and usage,
with optional transcripts and video. Missing evidence or a changed player
identity is a measurement error, not a zero score. See the
[result guide](../../README.md#reading-results).

## Troubleshooting

- **Renderer exits immediately:** inspect its log and confirm graphics drivers
  and `libxkbcommon-x11-0` are installed.
- **Missing `xdpyinfo`:** install `x11-utils` before upstream setup.
- **Runtime mismatch:** use the matching installation and build cache, then
  rebuild in a separate destination.
- **No display or Vulkan device:** use an authorized X11 display and a Vulkan
  driver supported by the renderer; headless mode still needs graphics support.
- **Fixture initialization fails:** check map availability, coordinates,
  clearance, initial supplies and native item/recipe identifiers.

For a new Agent or game integration, follow the
[extension guides](../../README.md#adding-tasks-and-games).
