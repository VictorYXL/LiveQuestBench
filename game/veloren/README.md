# Veloren

An ordinary native Veloren player behind the same administrative lifecycle as
Minecraft: `start`, `begin`, `end`, `get_agent_interface`, `save_snapshot`, `close`.
This is a new engineering profile, not a reproduction of published VelorenBench
task qualification or Agent scores.

The production launcher runs the explicit VM/ST examples in
[`config/veloren/`](../../config/veloren/); see the
[experiment usage and result semantics](../../README.md#running-an-experiment).
The same private endpoint evaluators validate configuration before a scheduled
run and score native before/after evidence afterward.

## Setup

The current installer reuses an **already prepared and validated VelorenBench
installation and its matching native build cache**. It is not a fresh game
downloader. Obtain/build those using the upstream project's installation workflow
first. The integration preserves the original repository, installation, assets,
server, helper and Python environment. No game binary or asset is vendored here.

Host requirements are Linux/X11, Xvfb for headless mode, a Vulkan driver usable by
the renderer, FFmpeg for recording, `patch`, `uv`, and the upstream pinned Rust
toolchain/cache. The prepared upstream harness uses Python 3.13 in its own
environment; LiveQuestBench itself stays on Python 3.11.

```bash
uv sync --locked --extra veloren --group test
bash game/veloren/setup.sh \
  --installation /absolute/path/to/veloren-installation/installation.json \
  --build-cache /absolute/path/to/veloren-installation/build-cache \
  --root /absolute/path/to/new-livequest-veloren-build
export LIVEQUEST_VELOREN_RUNTIME=/absolute/path/to/new-livequest-veloren-build/runtime.json
```

The independent output root needs space for the source/compiler cache and binary.
The installer verifies the source against the bound native source manifest,
applies the declared patch, builds the renderer offline using the original
toolchain settings, and hashes the resulting executable and patch. Reusing this
output root is supported only if its source is exactly the declared patched tree.
The upstream runtime is still validated by its original loader on every launch;
the replacement renderer is separately and explicitly hashed. There is no
fallback to the unpatched renderer.

The inspected upstream checkout was VelorenBench `68b7326`, with uncommitted
upstream changes left untouched. The actual runtime uses its validated installed
harness and bound native source manifest, **not** whatever happens to be checked
out. Preserve that original installation and the generated runtime receipt.
The native source is GPLv3; the patch retains the [native license](patches/LICENSE).
Harness, assets and all other upstream components retain their own licenses.
This source-only integration does not grant asset redistribution rights.

## Modes and ownership

```python
from pathlib import Path
from benchmark.config import load_task
from game.veloren.game import VelorenGame

task = load_task(Path("config/veloren/tasks/vm/move_2_metres.yaml"))
game = VelorenGame(
    output_dir=Path("output/my-unique-veloren-episode"),
    fixture=task.fixture,
    track="visual_motor",  # or "structured_tool"
    headless=True,
    recording=True,
)
try:
    await game.start()
    before = await game.save_snapshot(game.output_dir / "before")
    public = game.get_agent_interface()
    await game.begin()
    # Supply only `public` and game.get_instructions() to the Agent.
    await game.end()
    after = await game.save_snapshot(game.output_dir / "after")
finally:
    await game.close()
```

`start()` requires an explicit fixture mapping and creates fresh private server
userdata, a private authoring helper and an ordinary renderer-owned player.
`fixture.map_asset` selects a concrete installed map; `world_seed`,
`time_of_day`, `day_length` and `calendar: none` declare the world settings.
The native map file hash and generated server-settings hash are recorded.
Missing maps or detected native map/settings fallback fail initialization.

[`initialize_fixture`](fixture.py) builds a Rock platform at the declared
absolute origin and size, moves the player to the declared point, sets health
and time, and validates a grounded, stationary opening with the requested
inventory, equipment and view direction. There are no `movement`/`spawn`
shortcuts or offsets inferred from a varying spawn point. Inventory differences
are applied with native cleanup/gift operations; the existing cleanup drops
unwanted supplies 100 m from its starting location and clears skills/buffs.
Equipment is checked exactly against the pinned starter character, not silently
replaced or treated as an arbitrary editable loadout. The currently admitted
initial look is `[0, 1, 0]`; other orientations are rejected before launch.

The built-in fixture declares the installed `world.map.veloren_0_18_0_0` map,
seed 130626853, noon, a 30-minute day, no calendar events, a 12x12 Rock platform
at `[18704, 10800, 401]` and a player at `[18706.5, 10806.5, 402]`.
Task VM/ST files declare the same world and player conditions.
These remain small integration tasks, not a long-horizon task distribution.

**Map files are not complete snapshots.** Native `FileOpts::Load`/`LoadAsset`
load world-map data; character DB, terrain modifications and RtSim state are
separate and omit some live components. The current loader uses the composite
configuration above, not a claimed full-engine checkpoint. Stable authored
starting conditions do not imply identical ambient entities, setup ticks,
session IDs or subsequent simulation trajectories. The prepared runtime and
assets remain part of the game identity.

VM observations are current XComposite PNG pixels and capture timestamps.
Actions use the shared bounded atomic XTest keyboard/mouse vocabulary, with
stateful down/up events and bounded waits. The renderer window is matched by
title and native process ID. The native patch permits physical input only after
an explicit launch opt-in and a privately fenced lifecycle request.
It restores normal camera, keyboard/mouse and HUD processing; original semantic
`visual_input` and other native skills are **not** exposed to the VM Agent.
Native focus events still update cursor capture while the actor-input gate is
closed. Disabling the physical gate also releases native queued ability inputs;
OS release events alone are not treated as proof of that cutoff.
The shared key whitelist is bounded: Alt/Super/Meta, function keys and punctuation
are not currently exposed. In particular, the default Alt block binding and
comma cursor toggle are unavailable; inventory (`I`) supplies the ordinary
cursor-bearing UI. No hidden skill substitutes for these unsupported bindings.

ST's `veloren-native-fixed-tools-v1` projects explicit actor state: session/update
identity, position, velocity, grounding, survival/resources/equipment, inventory,
native nearby entities and known recipes. This is local native sensing, not a
visual line-of-sight guarantee. The native observation's global map, terrain
queries, administrator control state and private fixture/scoring records are not
forwarded. Coordinates are native x/y horizontal and z up.

| Tool | Native operation | Bound / semantics |
| --- | --- | --- |
| `MoveTool` | Relative forward/backward/left/right movement | 1-120 variable-duration client updates, no path planning |
| `TurnTool` | Native yaw change | -180 to 180 degrees |
| `JumpTool` | Native jump | Actual grounding/stamina constraints |
| `PickupTool` | Nearest in-range item | Does not navigate or choose a route |
| `UseItemTool` | Observed integer inventory slot | Native item effect, not a scripted reward |
| `CraftTool` | Known recipe | Amount 1-10; native material/station requirements |

Tools are serialized and native failures remain explicit receipts. Malformed
requests and communication failures raise errors. There is no generic server
command, administrator operation, arbitrary native RPC or whole-task skill.
Observe remains available while a native action runs; it does not issue an action.

## Time, stopping and evidence

The server and renderer continue while models think, networks wait and tools run.
Native `tick` is a **client-update counter with variable elapsed time**, not a
fixed server tick or 60 Hz clock. All benchmark boundaries use host monotonic
nanoseconds. Actions may have partial effects before cancellation.

`end()` revokes public access, interrupts a pending public call, clears held
controls and obtains native stop acknowledgement. It does not roll back effects
or pause the server. Physics, AI and existing consequences can continue after the
gate. Before/after snapshots are private native-client readbacks at explicit
ready/ended boundaries, not atomic server saves; capture timing and checksums are
recorded alongside the full private observation. Do not merge these results with
Minecraft's tick-freeze protocol as if the timing conditions were identical.

[Endpoint evaluators](evaluators/endpoints.py) support:

- horizontal displacement with positive final health;
- inventory count and minimum count change for native item identifiers;
- final health and minimum health change.

Inventory thresholds `min_count` and `min_delta` are independently optional;
provide at least one nonnegative integer. Health thresholds `min_health` and
`min_delta` are also independently optional; provide at least one finite number,
with a nonnegative `min_health`. A negative health delta explicitly permits a
bounded loss. Supplied thresholds are combined with AND.

Omitted thresholds impose no constraint (`None` in the Python API). In particular,
`min_count` alone allows inventory consumption as long as the final count meets
the goal, and `min_health` alone allows damage. Previously, both implicitly
required a nonnegative delta; callers that need that condition must now specify
`min_delta=0`. Empty threshold sets raise instead of succeeding unconditionally.
Final-state checks still read and validate both endpoints for audit integrity.
The displacement task keeps its explicit relative-distance and living-at-end
conditions; no inventory or health-delta constraint is added.

Simple inventory IDs use the native asset string. Composite IDs use sorted,
compact JSON of the native definition ID; unrelated composite items are not
discarded or miscounted.

Evidence must have correct endpoint phases, matching session and actor identity, ordered
capture windows and matching checksums. Missing or corrupted evidence is an
error, not a task failure or score of zero. Endpoints do not prove path length,
intermediate survival, exact event ordering, crafting provenance or sustained
resource ownership; those need trajectory/event evaluators.
These initial evaluators require the same native actor identity at both
endpoints. Cross-respawn/actor-replacement scoring is not qualified; an identity
change is reported as invalid evidence, not silently scored as a failed task.

Use dedicated displays. An explicit desktop may be selected with
`headless=False, display_name=":..."`; never use that desktop manually during an
episode. XTest is session-global, not a malicious-Agent security sandbox.
Recording samples the actual native window including its HUD and UI.

## Tests

```bash
export LIVEQUEST_VELOREN_TEST=1
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_game/veloren -q -s --headless --recording

# Prepare the selected Agents using their own READMEs first.
export LIVEQUEST_LIVE_COPILOT=1
export LIVEQUEST_COPILOT_TOKEN_FILE=/absolute/path/to/authorized-token.txt
uv run --locked --extra veloren --group test python -m pytest \
  tests/test_agent/test_agents_veloren.py -q -s --headless --recording
```

The game checks prove real VM movement, mouse look, inventory UI and held primary
input release; all six ST skills (including truthful out-of-range/empty-slot/
missing-material failures); active-action cutoff, public gates, native update
progression, private scoring, process cleanup and video decoding. Private native
frame metadata is used only by these administrative checks, never as VM input.
The small offline evaluator check covers exact thresholds and corrupted evidence.
Agent tests use real `gpt-6-astra` calls, the same six integrated Agents, and a
two-metre displacement task. A task failure may pass engineering acceptance only
if the actual model, native loop/tool exchange and benchmark-controlled cleanup
are verified. Missing dependencies/runtimes produce skips, not acceptance.
The dedicated DeepSeek and GamingAgent stop cases interrupt after the first completed game tool.
The earlier validated headless run passed its 13 Agent cases and the three game/evaluator
checks. See the [acceptance record](../../output/survey/veloren_integration_20261022.md)
for exact source hashes, task outcomes, corrected input defects and retained
evidence. These results qualify the small integration task, not the full game or
long-horizon benchmark performance.

Raw game and Agent artifacts are under `output/test/`. They retain model messages,
real images, interactions, runtime provenance, native journals, endpoint scores,
boundary timestamps, cleanup reports and optional decoded videos.
