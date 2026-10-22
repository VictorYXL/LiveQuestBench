# Veloren

An ordinary native Veloren player behind the same administrative lifecycle as
Minecraft: `start`, `begin`, `end`, `get_agent_interface`, `save_snapshot`, `close`.
This is a new engineering profile, not a reproduction of published VelorenBench
task qualification or Agent scores.

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
from game.veloren.game import VelorenGame

game = VelorenGame(
    output_dir=Path("output/my-unique-veloren-episode"),
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

`start()` creates a fresh private standard-world server, private fixture helper
and ordinary renderer-owned player. The default `movement` fixture constructs
and verifies a 12x12 elevated Rock platform through upstream authoring helpers.
The optional `spawn` fixture uses the settled ordinary spawn instead.
These are smoke-test fixtures, not long-horizon benchmark tasks. The upstream
small-world mode is deliberately not used: its observed water spawn did not
satisfy the authored fixture's grounding contract.

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
