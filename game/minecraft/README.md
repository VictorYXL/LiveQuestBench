# Test Minecraft with LiveQuestBench

The production launcher runs the explicit VM/ST examples in
[`config/minecraft/`](../../config/minecraft/); see the
[experiment usage and result semantics](../../README.md#running-an-experiment).
Benchmark recordings live under each Episode's `recording/`: `video.mp4`
and `chat/`. Standalone game tests retain their own output layout;
`MinecraftGame(recording_path=...)` can select an explicit video destination.
`MinecraftGame` requires an existing `world_path` and explicit `player_state`.
The resource-island fixture supports the migrated island catalog and integration tests.
The coupled forge/hunt task uses a separate authored native fixture.
There is no default/generated world or benchmark-time scene-construction command.

## Migrated island tasks

All eleven tasks from `GameAgentResearch/benchmark/tasks/island/` are migrated to
**both** `config/minecraft/tasks/visual_motor/` and
`config/minecraft/tasks/structured_tools/`, retaining these IDs:

| Task ID | Endpoint requirement |
| --- | --- |
| `island.collect_logs` | 3 oak logs |
| `island.collect_dirt` | 3 dirt |
| `island.collect_cobblestone` | 3 cobblestone |
| `island.craft_wooden_pickaxe` | 1 wooden pickaxe |
| `island.craft_stone_pickaxe` | 1 stone pickaxe |
| `island.smelt_iron_ingot` | 1 iron ingot |
| `island.craft_iron_pickaxe` | 1 iron pickaxe |
| `island.collect_diamond` | 1 diamond |
| `island.build_plank_wall_2x2` | New 2×2 oak-plank wall |
| `island.build_plank_cube_2x2x2` | New solid 2×2×2 oak-plank cube |
| `island.build_plank_enclosure_5x5x2` | New 5×5 perimeter, height 2, empty interior |

Each source filename is preserved (`<source task name>.yaml`). Every task has a 2,100-second
budget and a survival start at `(0.5, 72, 0.5)`, full health/food, no experience,
and normal difficulty. Inventory tasks start empty; structure tasks receive
exactly 64 oak planks in slot 0. ST tasks expose the existing game-provided tool
profile's original tool set by default; the later combat additions are not
silently granted to these migrated tasks.

## Entry coupled task: forge, hunt and return

[`forge_hunt_return`](../../config/minecraft/tasks/structured_tools/forge_hunt_return.yaml)
has paired ST/VM definitions with a 600-second developmental budget. Craft a
stone or iron sword, defeat a named native Husk using a crafted sword type,
then return alive and settled to camp. Materials and food are finite; health,
inventory and the same world carry across stages. A physical divider protects
the initial workshop from direct line of sight, but is not an invulnerability
zone. The calibrated entry variant starts with ordinary iron armor and native
Easy difficulty; enemy AI and health are unchanged. Recovery is optional.

The private [expedition evaluator](evaluators/expedition.py) checks a passive
vanilla `player_killed_entity` advancement bound to the exact authored enemy
UUID. Its function records the credited player's UUID, held item, native
crafted-sword counters and game time at the kill. Success requires positive
craft count for the held sword type, no native player deaths, positive final
health and a grounded overworld return within 2 horizontal / 0.5 vertical
blocks, at saved motion <=0.1 blocks/tick. This establishes crafted-type
preparation before native kill credit, not a uniquely tracked individual
sword or exclusive last-damage attribution. The datapack gives no rewards,
equipment, healing, aim assistance or combat commands.

The separate [fixture](../../config/minecraft/fixtures/forge_hunt/) is copied
per episode; its datapack hashes and target registry are checked, and the
target must be loaded at full health before the public gate opens. Neither
the registry, startup query nor native evidence files are Agent observations.
The [source manifest](../../config/minecraft/fixtures/forge_hunt.source.json)
records source/export hashes, author identity and every authoring command.
It was authored from the unchanged resource island with
[the native fixture author](fixtures/forge_hunt.py):

```bash
MINECRAFT_EULA_ACCEPTED=true .venv/bin/python -m game.minecraft.fixtures.forge_hunt \
  config/minecraft/fixtures/island output/temp/forge-hunt-new-authoring
```

The author refuses an existing destination and requires an installed native
server plus explicit EULA acceptance. Export only its validated player-free
`world/`, not the temporary server directory or logs. No game binaries or
assets are included. This is an entry-level coupling diagnostic, not yet an
NPC, boss, multi-outpost or difficulty-calibrated long-horizon task.

The original unarmored Normal variant had two valid Baseline failures. The
armored Easy revision with explicit-point StrikeTool has a recorded ST success
and VM failure; this is preliminary calibration, not a stable success rate.
Public ST references pass. Historical evidence is retained separately.

### Two outposts and return cargo

[`two_outposts_return`](../../config/minecraft/tasks/structured_tools/two_outposts_return.yaml)
extends preparation into two native encounters, optional chest resupply and
transport of actual Outpost Records back to camp. A Husk and a daylight-neutral
spider use ordinary behavior, including wandering; the published coordinates
are initial positions, not a live location feed. Both exact native kill receipts
must name the player holding a crafted sword type. Returned paper must carry
the authored cargo tag; ordinary crafted or renamed paper does not qualify.
Health, hunger and equipment persist; no recovery action or kill order is forced.
The 900-second budget and intermediate tier are developmental, not calibrated
cross-Agent difficulty. The paired VM task uses only ordinary chest UI input.

[`two_outposts_courtyard/`](../../config/minecraft/fixtures/two_outposts_courtyard/) is a separate
player-free save with [source hashes](../../config/minecraft/fixtures/two_outposts_courtyard.source.json).
Solid foundations and ordinary walls with inward overhangs limit unintended
under-platform encounters and spider escape without disabling native AI.
Reproduce it using the author command above with `--encounters 2` and a fresh
destination. The passive datapack records kills; it does not deliver the cargo.

The final courtyard has one recorded Baseline ST success and one VM failure.
Both episodes completed with valid measurements, replayed scores and decoded
videos. A public ST reference also completed both native kills, chest transfers
and cargo return without dying. Together with the entry results above, these
are development feasibility checks, not a calibrated cross-mode difficulty curve.

### Barter-funded outposts

[`trade_outposts_return`](../../config/minecraft/tasks/structured_tools/trade_outposts_return.yaml)
and its [VM counterpart](../../config/minecraft/tasks/visual_motor/trade_outposts_return.yaml)
replace crafting with a real villager economy: start with two emeralds,
30 coal and one bread, buy an iron axe, clear both outposts and return their
records in the same life. The weaponsmith buys 15 coal for one emerald and
sells an axe for three; the farmer sells six bread for one emerald. Spending
too much on food can leave the weapon purchase unfunded. Selling more coal
and buying food cost interaction time; recovery and kill order remain choices.

These are selected ordinary Java 1.20.4 novice offers, checked against the
pinned native factories and server readback, not invented barter recipes.
Stone trading stalls, fixed stock, no reachable restocking job sites, and the
initial budget are authored fixture conditions. Neither enemy health/AI nor
trade settlement is replaced. The passive datapack joins an exact-villager
`villager_trade` receipt to subsequent exact-target kill receipts, using native
event order and the held purchased weapon type. It does not give items or
prove uniquely tracked individual-axe provenance. The 900-second task is a
provisional harder expedition, not a built-in vanilla quest, a resident-defense
qualification, or a completed MC-C3 family.

Recorded Baseline ST completed this chain successfully; VM completed the native
weapon purchase but failed later in combat. Both admitted episodes have valid
measurements, replayed scores and decoded videos. An earlier ST attempt failed
before play during renderer initialization and is retained separately, not
counted as an Agent failure. The public ST reference also succeeds. These are
small development samples, not stable success rates or a calibrated tier.

The separate [world](../../config/minecraft/fixtures/trade_outposts_courtyard/)
and [provenance](../../config/minecraft/fixtures/trade_outposts_courtyard.source.json)
are authored by [the trade overlay utility](fixtures/trade_hunt.py) from the
unchanged two-outpost fixture. The server binary and vanilla mechanics remain
unchanged; the Fabric control bridge, passive evidence datapack and authored
save mean this is **not an unmodified, mod-free evaluation environment**.

### Evaluator mapping and deviations

- The eight source `InventoryEvaluator` tasks use the existing native inventory
  evaluator with the original minimum endpoint counts. Craft/smelt verbs do not
  imply recipe-event or causal verification; the scorer reads saved inventory.
- The three `StructureEvaluator` blueprints are preserved in `[y][z][x]` order.
  The native scorer compares saved before/after worlds, requires newly placed
  oak planks, allows quarter-turn rotations, and requires exact recall,
  precision and IoU plus empty enclosure interiors.
- Unlike the source's implicit search scope, construction is explicitly bounded
  to the clear central area: **x/z −8 through 8, y 72 through 73**, inclusive.
  This restriction and the prohibition on extra placed oak planks in that area
  appear in each public construction prompt. The 578-cell scoring region fits
  within the generator's flat central square.
- The source single worker becomes the single benchmark agent. Source
  five-second warmup/settle settings are not extra agent time; the benchmark
  owns the ready/before/after lifecycle. No source task is excluded.

### Immutable native resource-island fixture

[`config/minecraft/fixtures/island/`](../../config/minecraft/fixtures/island/)
is a player-free native snapshot, not a completed gameplay world or runtime
generation recipe. Each episode copies it before writing player state. Do not
run Minecraft directly against the fixture or edit it in place.

Its source was
`GameAgentResearch/output/temp/island_native_validation_v2/world`, alongside
`island_manifest.json`, `island_checkpoints.json` and the compiled generation
datapack. That validation recorded zero bots/models and had no player files.
Migration did **not** rely on that claim alone: all **658 full native chunks /
64,684,032 block cells** were compared with the flat ocean base plus every
checksum-verified `fill`/`setblock` command from the recorded generator pack.
There were **zero block-name mismatches** and no block entities. All 316
resource-generation chunks were present.

The export contains 651 oak logs (1,822 logs across all species), 91,416 dirt,
19,134,109 stone, 421,913 coal ore, 283,758 iron ore and 91,530 diamond ore.
Ore and tree-log totals match the generation manifest. Native terrain
palettes/properties, lighting, heightmaps and biomes are preserved. Verification
compares block names, not leaf-distance properties.

The export omits incomplete/protochunks, entities, players, history, datapacks,
command storage/scoreboards, POI, extra-dimension saves and locks. Chunk
timestamps/tick queues and world time are reset. Frozen noon, clear weather,
disabled mob spawning/fire/random ticks and the 768-block world border are
retained. Unsaved chunks use the original vanilla flat-ocean generator (bedrock
at −64, stone through 54, sand through 56, water through 63), not a missing
island bootstrap datapack.

### Provenance and offline reproduction

[`island.source.json`](../../config/minecraft/fixtures/island.source.json)
records per-file fixture hashes, source region/level/task hashes, the complete
original generation manifest, compiled-pack/checkpoint digests, validation
coverage and material counts. The aggregate fixture SHA-256 is:

```text
048b6c7e39ee4de64dced31ecdf0ee89335c7c0297ec2616a001ea9deb5bb9bb
```

This hashes the sorted, compact JSON mapping of relative fixture paths to
SHA-256 values, followed by a newline. The source manifest file SHA-256 is
`d6618c65db10cd21a637ee1755004e3b4d2436b0ae21a608026cdd9d0b7d3f1a`.
The generator changed since generation: the source manifest records
`c22aa93a430cebdfa12f5ed81a3f1ba8c2bda3fda7583ecf533c3a7d51f317d2`,
while migration observed
`a552181ae67843dae82b543dadf467dcf1ee5fb7be4997be5509ee4857cff553`.
Both are recorded without claiming identity; pristine verification uses the
manifest-verified compiled commands, not the later source file.

To reproduce the bounded export offline into a **new** directory:

```bash
.venv/bin/python game/minecraft/fixtures/export_island.py \
  /path/to/GameAgentResearch output/island-reexport
```

The exporter needs the Minecraft Python dependencies, refuses an existing
destination, and rejects missing resource chunks, changed generation commands,
unexpected blocks or non-pristine terrain. It never starts a game or model.

### Migration qualification limits

Migration checks native NBT/Anvil integrity, all fixture hashes, terrain/resource
coverage, the clear scoring area and offline admission of both task catalogs.
It reuses the existing inventory and structure scorers without modifying their
runtime behavior. **No server/client, model, gameplay acceptance or large test
suite was run for this migration.** Resource-valid tasks do not establish that
an agent can finish within 2,100 seconds; native reset/load and end-to-end
success still require a separately authorized gameplay run.

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

No additional map download, model, API key or Agent is needed. Live tests
explicitly copy the repository's immutable
[`island`](../../config/minecraft/fixtures/island/) save, with
grass at Y=71 and player feet at Y=72 at the central spawn. Basic interface
checks are not evidence of long-horizon task difficulty.
VM and ST start from the same source world; previous Episode mutations are not reused.

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

There are focused non-game checks for inventory/structure evidence, explicit
startup consent and motor rejection/recovery, plus four actual game checks. The removed VM/ST schema and
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
another world instead of the bundled template. It must contain `level.dat`,
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

Display/recording settings and the `minecraft-1.20.4-st-native-v5` tool profile
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
Capture, recording and the atomic motor implementation are shared with Veloren
under [`game/backends/x11`](../backends/x11). Minecraft retains its
explicit window-title/class selectors and mode-local Agent binding; the shared
backend does not infer which game's window to control.

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

Batches contain 1-64 commands and at most 10000 ms of explicit waits **in total
per call**, not per wait. This is not a limit on continuous key-hold duration. Structure
is validated before execution; geometry, focus and pointer ownership are
checked during execution. Concurrent calls are serialized; calls waiting for
the interface are rejected after `end`.

The Agent-facing `action` tool returns an explicit JSON error for invalid
arguments: `success=false`, `error=invalid_action_arguments`, `message`,
`executed_commands=0` and `held_controls`. The entire batch is rejected before
execution; previously held inputs remain unchanged and may still be active.
Absolute mouse coordinates use window-local screenshot pixels. The entire batch
is checked against the current window dimensions before any command executes;
out-of-window coordinates return the same recoverable error with valid bounds.
Window/focus/connection failures still propagate as execution failures.
The Agent can correct its next call; no automatic splitting, shortening or retry
occurs. Valid calls retain the action-result array format. Runtime execution
failures still propagate, and direct `interface.act` calls retain exception
semantics.

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

Profile: **`minecraft-1.20.4-st-native-v5`**, extending v2 with optional
`AttackTool` and `UseHeldItemTool`. The former submits one current-crosshair
entity attack within three-block survival reach without auto-aim, navigation
or cooldown waiting; the latter holds native item use for 0.05-5 seconds and
then releases it. Native item rules apply. Cancellation releases held input.
V4 adds `StrikeTool` (one supplied-point aim plus one unobstructed three-block
native attack), `InspectContainerTool` (open/read an aimed-at reachable chest)
and `TakeContainerItemTool` (one native shift-click of an observed chest slot).
None tracks enemies, navigates, chooses supplies or repeats a combat policy.
Existing non-expedition task defaults retain the original tool set; explicit
allowlists may opt into the new tools. V5 adds opt-in `InspectMerchantTool`
(reachable native offers, payment slots and cursor) and `TradeTool` (one
quoted exchange into a chosen empty hotbar slot). Quotes bind the open screen
and current offer; price/stock changes require reinspection. Exact native
stack matching includes item tags. The skill selects no offer, never repeats
purchases or equips the output, and retains partial effects on interruption.
Non-trading expeditions retain their previous default tool set. V2 replaced
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

Agent-facing ST tools validate arguments before calling the native interface.
Invalid arguments return `success=false`, `error=invalid_tool_arguments`,
`message` and `executed=false`, allowing the Agent to correct its next call.
No game command is submitted or automatically retried. Direct interface
validation and runtime/communication failures still raise exceptions.

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
VM batches interrupted before a command or during an explicit wait use the
same gate exception and release held controls; they are not invalid-input errors.

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

### Inventory evaluator

[`evaluate_inventory`](evaluators/inventory.py) reads private before/after
inventories. Each item requirement must specify at least one nonnegative integer
threshold: `min_count` (final minimum), `max_count` (final maximum), or `min_delta`
(minimum net increase). Only explicitly supplied thresholds apply, combined with
AND; omitted thresholds impose no constraint. Null thresholds are invalid in
requirement mappings.

For the empty-inventory `island.collect_logs` task, use `min_count: 3` alone.
Use `min_delta: 3` when the objective is explicitly a net increase of three.
Net increase is not cumulative collection: consumed or dropped items reduce it.
The before inventory remains available for auditing even for final-state goals.
Requirements without thresholds now raise instead of implicitly requiring one item.

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
