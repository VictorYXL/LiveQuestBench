# Test Minecraft with LiveQuestBench

## Public instructions and developer documentation

[`prompts/`](prompts/) contains task-independent, model-facing descriptions of
the game, controls, timing and observation encoding.
[`MinecraftGame.get_instructions()`](game.py) loads these text files for all Agents;
the public task is supplied separately. These prompts do not include fixture
coordinates, target items or task-specific strategies.

The fixed layout is `game/<game_name>/prompts/`:

- `introduction.txt`: common game introduction and interaction rules.
- `visual_motor.txt`: VM-specific controls and observation format, when needed.
- `structured_tool.txt`: ST-specific tools and observation format, when needed.

Common introduction comes first, followed by the selected mode's text.
A game without mode-specific instructions needs only `introduction.txt`;
do not add empty mode files or infer support for a track from file existence.
Minecraft provides both mode files. These files are shared by all Agents, not
stored in Agent packages. The public task remains separate. Agents receive the
loaded text through `AgentContext` and do not import this game.

The existing [VM interface](visual_motor/interface.py) and
[ST interface](structured_tools/interface.py) each expose `agent_tools()` and
`agent_observation(interface)`. VM handles PNG encoding and bounded motor
commands; ST handles fixed native tools and lossless state encoding.
These functions use only the restricted interface, with no planner, task solution,
scoring or lifecycle management. Both modes reuse their own tool schemas. In VM,
the command vocabulary and bounds have one definition used to generate the
model-facing schema and validate execution. No separate binding module,
second action specification or lifecycle bypass is introduced.

This README contains developer documentation for integration, lifecycle, tool
semantics, failures, installation and private evidence. It is not loaded into
Agent requests. Keep interface facts consistent with tool schemas and public
instructions, without copying developer-only material into model input.

Both modes use **one Minecraft Java 1.20.4 runtime**: isolated local server,
initial player state, lifecycle, native snapshots and scoring.

- **VM:** native Minecraft graphics and keyboard/mouse input, using a pinned
  Fabric development client.
- **ST:** structured observations and fixed tools controlling that same native
  client through a private bridge.

Both default to a local **offline server bound to `127.0.0.1`**. No automatic
fallback or public unauthenticated server is created.
**Neither local mode needs a Microsoft login, a Prism installation or an account
file.** Both keep Minecraft's own renderer and player's interface. There is no
Mineflayer participant or spectator camera.

## 1. Prepare the environment

Run from the repository root on Linux x86_64, as your normal user:

```bash
game/minecraft/setup.sh
```

Setup installs project/test dependencies, prepares a Java 21 JDK and graphics packages,
builds the pinned native-client environment/control mod and verifies the server
JAR. The first setup needs internet access, downloads
client libraries/assets and can take several minutes. Later Episodes launch
Java directly without running a Gradle build.
Neither mode requires Node.js or npm.
Use `--skip-system` when system packages have already been provisioned.

You can select a track for installation/preflight:

```bash
game/minecraft/setup.sh --track structured_tool
```

Both tracks now share the same native/graphics dependencies, including in
headless mode. Use `--track visual_motor` for VM. Setup neither launches a game nor accepts
its EULA. No manual title-screen launch is required.

Both setup and tests can run from SSH/remote VS Code. Each test creates an isolated
Xvfb display automatically. Proprietary binaries/assets are downloaded during
setup, not committed to this repository. Offline authentication does not waive
Minecraft's usage/distribution terms or grant redistribution permission.

## 2. Accept the EULA and check installation

Read the [Minecraft EULA](https://aka.ms/MinecraftEULA). Only if you accept it:

```bash
export MINECRAFT_EULA_ACCEPTED=true
game/minecraft/setup.sh --check --verify-server
```

For ST-only installations, add `--track structured_tool`; for VM only, add
`--track visual_motor`. Checks are read-only and do not launch the game.
`--verify-server` reads official Mojang metadata to verify the JAR.
**EULA consent is not an account login or license grant.**

The local offline test player is named `LiveQuestBot`.
Its offline UUID is used consistently for both modes,
initialization and scoring. Original account files and worlds are not modified.

## 3. Run basic tests

No map download, model, API key or Agent is needed. By default, live tests
generate a fresh flat world with grass at Y=71 and player feet at Y=72.
This `flat-smoke-v1` preset is for installation/interface checks, not benchmark
task difficulty or long-horizon evaluation.

Run offline checks first:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft -q
```

Then enable real game sessions:

```bash
LIVEQUEST_MINECRAFT_TEST=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft -x -q -s
```

| Test file | What it checks |
| --- | --- |
| `test_game.py` | Installation, startup gates, world copying/scoring, world-time progression, snapshot hashes and playable recording |
| `test_vm.py` | Fresh native-client images, hotbar selection, movement, mouse look and playable recording |
| `test_st.py` | Local state, crafting, digging, movement, cancellation, final inventory and first-person recording |
| `test_structure.py` | Native block placement scored from before/after saves, plus structure counterexamples and corrupt/missing evidence |

There are three focused non-game checks for inventory/structure evidence and explicit
startup consent, plus four actual game checks. The removed VM/ST schema and
profile-literal checks are not replaced by additional test scaffolding.
Without live opt-in, the four game checks skip; this does not establish that
the real game works.
For ST only, replace the directory with
`tests/test_game/minecraft/test_st.py`. All four live cases deliberately point
Prism at a nonexistent directory to detect accidental account dependencies.
Select `test_vm.py` similarly to check VM alone.
Both mode tests record `video.mp4` at 10 FPS by default, with brief viewing pauses
before and after their scripted actions. All game tests use the shared
`recording` fixture from [`tests/conftest.py`](../../tests/conftest.py).
Pass `--no-recording` to disable videos and video decoding checks, or
`--recording` to enable them explicitly. The native renderer, observations and
snapshot checks are unchanged. These options are independent of `--headless`.
For compatibility, `MINECRAFT_TEST_RECORDING=0` disables recording when neither
CLI option is supplied; an explicit CLI option takes precedence.

### Show a window while tests run

From a local desktop terminal or an existing remote-desktop session:

```bash
LIVEQUEST_MINECRAFT_TEST=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft -x -q -s --no-headless
```

`--no-headless` uses the current X11 `DISPLAY`: you can watch the actual controlled
player while the tests run. `--headless` (the default) uses a separate virtual
screen; both modes can save video. Do not move the mouse, press keys or steal
window focus during automated tests. Only one game may use a given display.
Windows close when their test finishes.

An SSH/remote VS Code terminal without `DISPLAY` cannot show a desktop window;
use `--headless` there, or run from your existing remote desktop. Native Wayland
is not supported; an authorized X11/XWayland session is needed.
For Python integrations, use `MinecraftGame(headless=False)` or pass an explicit
`display` to reuse an existing authorized X11 display.

### Optional existing world

Set `MINECRAFT_TEST_FIXTURE` to a complete pristine 1.20.4 native save to test
world-copy reuse instead of the generated preset. It must contain `level.dat`,
no saved players and no symlinks; these tests also require the safe starting
position `[0.5, 72, 0.5]` and a diggable block at `[1, 71, 0]`.
The existing prepared island is suitable. The source is never the writable world.

## 4. Inspect results

`-s` prints each live case's unique directory under `output/test/`:

- `minecraft-game-*`: before/after native saves, receipts and `video.mp4`.
- `minecraft-vm-*`: final native evidence of movement/hotbar/camera changes and
  `video.mp4` recorded at 10 FPS during the scripted actions.
- `minecraft-st-*`: before/after inventory evidence, including after cancellation,
  and `video.mp4` from the controlled player's native client, including HUD and
  inventory/crafting screens.

Each also contains environment/fixture/timing metadata and server logs.
VM/ST runs retain a private client working directory and `client.log`; these
contain no copied account credentials. Shared build dependencies stay in the
managed installation directory, not in every test output.
`MINECRAFT_TEST_OUTPUT` optionally selects a different output root; each test
still uses a unique child directory. Pictures are checked in memory, not dumped.
Offline scratch files are removed automatically; no extra JSON summary is written.

Use pytest's outcome, not file existence: failed runs may leave partial evidence.
ST tools now drive the player's own native client. Video includes the hand,
held item, HUD and actual inventory/crafting/furnace screens, not a spectator
approximation. Tool operations are programmatic native interactions, not a
human-like animation of every mouse click. Video remains human-only and is not
added to the structured Agent input.

Display/recording settings and the new `minecraft-1.20.4-st-native-v2` tool profile
are saved in `environment.json`. Do not compare previous Mineflayer-profile
results as identical conditions. Both modes use the same snapshot/evaluator path.
Snapshots are saved-state boundaries, not exact atomic native-tick cutoffs.

## 5. Prepare an LLM and connect an Agent

LLM checks are independent and optional. See the
[model client instructions](../../README.md#model-clients) for Copilot, OpenAI and local vLLM.
Keep `--extra minecraft` in `uv run`/`uv sync` commands in this environment.
Store credentials in your own environment; none are shipped with the repository.

The [Agent integration section](../../README.md#agent-integration) describes the native ToolCallingAgent
and pinned DeepSeek/Hermes integrations, including opt-in live model tests.
There is no end-to-end Benchmark launcher yet.
Integrations use [`BaseAgent`](../../agent_framework/agents/base_agent.py) and one
`MinecraftGame`, selecting `track="visual_motor"` or `track="structured_tool"`.
Both follow:

```text
start -> before snapshot -> begin -> Agent -> end -> after snapshot -> close
```

Always close in `finally`. Pass only `get_agent_interface()` to the Agent:
the [VM interface](#vm-interface) covers pixels/input; the
[ST interface](#st-interface) lists the fixed tool profile and semantics.
The game interface tests use scripted actions, not an LLM, and passing them is not an Agent
benchmark score.

## Troubleshooting

- **Native client missing or setup changed:** rerun
  `game/minecraft/setup.sh --track visual_motor`. It uses a checksum-verified
  Gradle distribution and a private dependency cache, without reading Prism.
- **Upgrading from Mineflayer ST:** rerun setup once to build the native control
  mod. Old Node dependencies are not used or automatically removed.
- **Desktop mode reports missing DISPLAY:** run from your desktop terminal or
  use `--headless`; setting a made-up display number will not create a desktop.
- **Client resources incomplete:** rerun setup with network access. Inspect
  `client.log` for startup errors; there is no silent fallback to another client.
- **Want the previous authenticated VM behavior:** explicitly construct
  `MinecraftGame(authentication="online", account="YourProfile")`. This optional
  legacy path still requires a separately prepared
  [Flatpak Prism](https://prismlauncher.org/download/linux/) 1.20.4 instance
  and a legitimate account; setup no longer provisions it. ST accepts offline only.
- **Custom installation paths:** see
  [installation overrides](#installation-overrides).

## VM interface

`await interface.observe()` returns a fresh `CapturedFrame`: frame/window IDs,
host monotonic capture-start/end timestamps and a PIL RGB image. These bound
host readback, not a native tick. Only the bound Minecraft window is captured;
there is no desktop fallback. No inventory transcription, coordinates, semantic
navigation, console commands or private scorer state are exposed.

`await interface.act(commands)` accepts objects with exactly `name` and
`arguments`:

| Operation | Arguments |
| --- | --- |
| `key_down`, `key_up` | Supported `key` |
| `mouse_down`, `mouse_up` | `button`: `left`, `middle`, `right` |
| `mouse_move_relative` | Integer `dx`, `dy`, each -32768 through 32767 |
| `mouse_move_to` | Integer window-relative `x`, `y`, within the current window |
| `mouse_scroll` | Integer `steps`, -20 through 20 |
| `wait` | Integer `milliseconds`, 0 through 10000 |
| `release_all` | Empty object |

Batches contain 1-64 commands and at most 10000 ms of explicit waits. Structure
is validated before execution; geometry, focus and pointer ownership are
checked during execution. Concurrent calls are serialized; calls waiting for
the interface are rejected after `end`.

Keys include `a`-`z`, `0`-`9`, `space`, `enter`, `escape`, `tab`, `backspace`,
`delete`, `insert`, arrows, `home`, `end`, `page_up`, `page_down`,
`left_shift`, `right_shift`, `left_ctrl` and `right_ctrl`. Alt/Super/Meta and
game commands are not exposed. The fresh native client uses standard bindings;
the optional authenticated Prism path retains its instance's bindings.

Held inputs persist across calls and reasoning until released, an executor
failure or game termination. A successful call acknowledges X11 submission,
not an in-game effect. Cancellation releases inputs but cannot undo effects;
do not automatically retry partially executed batches. Waits and menus do not
pause this multiplayer server.

The VM smoke test presses W for one second, releases it, looks down and holds
the left mouse button for two seconds. It checks movement/view and input, not
item acquisition. Before/after saves and optional recordings are retained.
This test example is developer documentation, not an Agent instruction.

XTest is display-global; focus checks are not a security boundary. Use a
dedicated desktop or virtual display without manual interference. Input and
observations are unavailable before `begin` and after `end`. Headless display
diagnostics go to `xvfb.log`; occupied-display probing and unsupported XF86
key symbols can produce nonfatal warnings. Startup failures raise with the log
location; existing displays are not reconfigured.

## ST interface

Profile: **`minecraft-1.20.4-st-native-v2`**, replacing
`minecraft-1.20.4-st-basic-v1`. Tool names are familiar, but backend, navigation,
recipe ordering and observation details changed; do not pool scores as the
same condition.

The client-side Fabric mod accepts private stdio control of the player's own
native client, not a Mineflayer bot or spectator. It is inactive in VM.
ST is still rendered; native inventory/crafting/furnace screens appear in
recordings. Programmatic recipe placement and slot clicks do not reproduce
human mouse travel. Recording is for human inspection, not ST input.

- `await interface.observe()` returns whitelisted state and host request/readback timestamps.
- `interface.tool_schemas()` returns fixed name/description/JSON-schema definitions.
- `await interface.call_tool(name, arguments)` validates and executes one tool.

State includes player identity, feet position, health/hunger, inventory, held
item/slot, look direction, aimed/supporting block, nearby entities and a block
palette cube. The radius-15 cube (31 cubed cells) is centered one block above
floored feet, without line-of-sight filtering. Unloaded/out-of-height cells are
unknown, not air. Descriptors include native state ID, collision, fluid,
replaceability and breakability. Entities are within 15 blocks; health is
limited to what the client has received. The shared Agent binding losslessly
run-length encodes the cube; its public format is documented in the instruction
file, without changing observation permissions.

Inventory slots 1-9 are hotbar and 10-36 storage. Armor/offhand, crafting-grid,
container and cursor contents are not transcribed in the player inventory.
Dropped items include name/count. Recipe queries use client-synced recipes.
Admin commands, raw protocol access, server files and unrestricted client
objects are not exposed.

| Tool | Behavior |
| --- | --- |
| `GetObservationTool` | Same projection as `observe`; omitted by the automatic-observation Agent binding |
| `MoveTool`, `JumpTool` | Bounded native movement/jump keys, then release |
| `LookAtPositionTool`, `SelectTool`, `StopTool` | Look direction, hotbar selection, release controls |
| `GoToPositionTool` | Walk to block center within 64 blocks; search limited to 4096 expansions; single-block steps/jumps/drops, no digging/building/parkour |
| `DigTool` | Aim at and break a reachable visible block, with native swing/damage |
| `PlaceTool` | Use held item on a reachable visible support face and check resulting block |
| `QueryCraftRecipeTool` | Output recipes, indices, ingredient alternatives and availability |
| `CraftItemTool` | Open inventory or aimed-at table; execute recipe count, not target inventory count |
| `SmeltItemTool` | Open aimed-at empty furnace, insert carried input/fuel, wait and collect output |

Schemas are authoritative. Recipe indices are sorted by native recipe ID;
without an index, the first recipe with available ingredients is selected.
There is no automatic collection, station setup/recovery, equipment selection
or material-chain planning.

Mutating calls are serialized and run on client ticks; observations can occur
while a tool is active. Final actions have a 60-second budget; digging also
has a preceding aim request. Long smelts can leave partial furnace contents.
The runner separately owns the Episode deadline.

## Lifecycle, failures and private evidence

Use a fresh game and Agent per Episode, and always `close` in `finally`,
including after partial startup. `start` copies a fresh world, freezes ticks
and verifies the initial player state. VM also checks actual mouse-look and
hotbar acceptance because the first cursor event may be discarded. Private
initialization restores orientation/slot 1 and rechecks state; no such
administrative correction occurs during measured play. A connected player
alone does not prove that loading screens have cleared.

`begin` verifies again and unfreezes; the world progresses during reasoning
and waits. `end` gates new calls, cancels active control and requests a freeze
without closing the client. ST waits for native release acknowledgement;
unacknowledged cancellation terminates the client and raises infrastructure
failure. Pending multi-tick work is removed without reconnect or respawn.
Death does not automatically respawn.

Public observation/action access outside running play raises `AgentAccessClosed`
(a `RuntimeError` subclass). During an intentional benchmark cutoff, an in-flight
Agent may encounter this gate before its stop request arrives. The runner may
classify that specific denial as stopped after successfully ending the game;
it must not suppress arbitrary runtime/infrastructure exceptions.

Normal ST action refusal returns `success=false`; bridge errors/timeouts raise.
Broken blocks, spent ingredients, in-flight packets and furnace contents are
not rolled back. The cooperative Python/stdio API is not a sandbox for hostile
Agent code.

Snapshots are permitted only at initial/terminal frozen boundaries. The harness
disables autosave, confirms `save-all flush`, copies the world with hashes and
host timestamps, then restores autosave. **Vanilla tick freeze does not freeze
players or their packets.** These are acknowledged save boundaries, not atomic
all-entity snapshots or exact tick/deadline cutoffs. Startup advances the world;
the initialized live before snapshot is the scoring baseline. Failed/partial
snapshots are not valid scoring evidence.

Inventory evaluation measures native saved counts/deltas, not item provenance
or a particular skill's use. Missing/malformed evidence raises. Recording is
host-sampled rather than native-frame-exact; recording errors propagate.
Distinguish game failure from infrastructure and measurement failure.

### Structure evaluator

[`evaluate_structure`](evaluators/structure.py) reads private native Anvil
regions, not Agent observations or tool-reported success. It is track-independent:

```python
from pathlib import Path
from game.minecraft.evaluators.structure import evaluate_structure

result = evaluate_structure(Path("run/before"), Path("run/after"), {
    "target": {"structure": [
        [["oak_planks", "oak_planks"]],
        [["oak_planks", "oak_planks"]],
    ]},
    "region": {"min": [-8, 72, -8], "max": [8, 76, 8]},
})
```

The blueprint is rectangular **[y][z][x]**. A block name requires that material;
`"air"` requires any vanilla air variant; `None` ignores the cell. At least one
non-air target is required. Only vanilla block identifiers and Java 1.20.4 saves
(DataVersion 3700) are supported. Block-state properties and block/entity NBT are
not matched: this cannot establish door orientation, a working mechanism,
enclosure safety or visual quality.

`region.min` and `region.max` are inclusive XYZ corners. Declare the scoring
area in the task configuration and ensure its chunks are fully saved in **both**
snapshots. The entire translated blueprint must fit inside it. Unlike the
upstream whole-save search, all matching and extra-material penalties are
restricted to this region; unrelated changes outside it cannot affect the score.
The reader raises on absent/incomplete chunks, malformed payloads or unsupported
versions; missing evidence is not air and is not a task-failure score.
Optional `dimension` defaults to `"minecraft:overworld"`; the vanilla Nether and
End paths/heights are also recognized. Custom dimensions/height overrides are
unsupported. Only the Overworld has been live-tested here.

Optional `match` settings (all flags default to `True`, thresholds to `1.0`):

- `rotation_invariant`: allow 0/90/180/270-degree rotations about Y, plus
  translation; no reflection or vertical rotation.
- `require_new_blocks`: a matched positive cell must differ from that same
  target block name in the before snapshot. An unchanged existing build cannot
  pass by default. This is an endpoint difference, not proof of who built it
  or whether a block was removed and replaced during the Episode.
- `require_empty`: enforce the blueprint's air cells.
- `min_recall`, `min_precision`, `min_iou`: finite thresholds in `[0, 1]`.
  For `M` matched positive cells, `T` target positive cells and `E` newly changed
  target-material cells outside the selected blueprint footprint:
  recall = `M/T`, precision = `M/(M+E)` (1 for zero denominator),
  IoU = `M/(T+E)`. These preserve upstream blueprint metrics, not arbitrary
  solid-volume IoU. Air violations independently fail a candidate.

The full rectangular footprint includes ignored cells. Extra target material
inside ignored cells is not penalized; changes to other materials are not a
collateral-damage check. `require_new_blocks=False` admits preexisting target
cells but still only counts **new** outside-footprint target material as extras.
At least one matching material anchor is needed even with zero thresholds.
Best-match ranking is deterministic: passed, recall, precision, IoU, then fewer
air violations; rotation/offset order breaks ties.

The result contains `success`, evaluator `version`, resolved settings/region,
coverage, `best_match` with metrics and mismatch coordinates, and a bounded change
sample. Successful evaluation covers every requested cell in both saves.
Regions are limited to 262,144 cells and searches to 5,000,000 candidate-generation
and scoring comparisons; exceeding either raises explicitly. Narrow the task's
scoring region rather than silently accepting a partial search.

Use the same Episode's completed `save_snapshot()` outputs and retain their
receipts. The scorer does not validate Episode identity or snapshot hashes for
the caller, and the save-boundary caveats above still apply. Do not give private
saves or scoring coordinates to an Agent unless permitted by the task contract.

## Installation overrides

| Variable | Meaning |
| --- | --- |
| `MINECRAFT_JAVA` | Client/server Java 21 executable; also used during setup |
| `MINECRAFT_SERVER_JAR` | Server JAR or explicit installation destination |
| `MINECRAFT_PRISM_ROOT` | Existing Flatpak Prism directory, only for explicit online VM |
| `LIVEQUEST_MINECRAFT_HOME` | Build/cache/downloads/locks; default `~/.local/share/livequestbench/minecraft` |

Without an explicit JAR, the managed download is preferred, then an existing
GameAgentVisual download under `GAMEAGENTVISUAL_HOME` or
`~/.local/share/gameagentvisual`. Verify reuse with
`game/minecraft/setup.sh --check --verify-server`.

Setup uses checksum-verified Gradle 8.6, Fabric Loom 1.6.12, Fabric Loader
0.15.11 and Yarn 1.20.4+build.3. It exports development classpath/configuration;
Episodes start Java directly, not Gradle or a launcher. Each Episode has a
private client directory and standard options; dependency caches are shared.
Setup checks build-source fingerprints and dependency presence. Receipts
identify the client as `fabric-development`.

Local startup neither reads account files nor takes the legacy login lock.
Only the optional authenticated Prism path uses private profiles outside run
artifacts, removed at cleanup. Credential permissions are restricted; assets,
libraries and metadata use private writable caches so downloads do not mutate
the original installation.

## Implementation provenance

VM adapts GameAgentVisual branch `xianya/init_mincraft`, commit
`696257de4ba7788f68026084b794d1265677f75b`; that checkout is not a runtime
dependency. Fabric development launch removes the default Prism/account
requirement without changing the renderer or public motor interface.
Offline authentication uses a consistent player UUID; explicit online VM
retains the separately prepared Prism path. ST shares the client with its
private bridge. There is no replacement renderer or step-based simulation
controller. This provenance grants no Minecraft binary/asset redistribution
rights.

The structure matcher and native block reader adapt the same Visual branch's
`benchmark/evaluator/StructureEvaluator/evaluator.py` and
`benchmark/evaluator/world.py`. The target/match vocabulary is preserved; the
bounded region and strict full-region evidence requirement are intentional
departures. The Research implementation at
`92b6d7f983dfe36929c851e8ae521a508cc60e82` was also inspected: it scores a final
nearby-block projection and only warns for `require_new_blocks`, so it was not
used as the scoring authority. This is source provenance, not a claim of an
upstream license grant; see the [evaluator study](../../output/survey/endpoint_evaluators_20261022.md)
for validation evidence and remaining scope.
