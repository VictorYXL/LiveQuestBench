# Minecraft

LiveQuestBench supports Minecraft Java 1.20.4 through two evaluation modes:

- **VM:** native game pixels and bounded keyboard/mouse input.
- **ST:** permitted game state and fixed tools controlling the native player.

Both modes use the same game version, render the controlled player's view and
run against an isolated server. The default setup does not require a Microsoft
login or Prism Launcher. Minecraft usage and distribution terms still apply.

See the [project guide](../../README.md) for Agents, model credentials,
experiment execution and result interpretation.

## Installation

Use Linux x86_64 and run from the repository root:

```bash
bash game/minecraft/setup.sh
```

Setup prepares project dependencies, a Java 21 JDK, graphics dependencies and the
native Minecraft runtime. Initial setup requires internet access. Use
`--skip-system` if the required system packages have already been provisioned.
Both tracks require graphics support, including in headless mode.

Read the [Minecraft EULA](https://aka.ms/MinecraftEULA). Only if you accept it:

```bash
export MINECRAFT_EULA_ACCEPTED=true
bash game/minecraft/setup.sh --check --verify-server
```

The check does not launch a game. EULA consent is not an account login or a
license grant. Game binaries and assets are downloaded during setup rather than
distributed with the benchmark.

### Installation settings

| Variable | Purpose |
| --- | --- |
| `LIVEQUEST_MINECRAFT_HOME` | Select a dedicated Minecraft installation |
| `MINECRAFT_JAVA` | Select the Java 21 executable |
| `MINECRAFT_SERVER_JAR` | Select the server JAR |

Use the same settings for installation, tests and experiments. Rerun setup
after native-client changes; updating Python dependencies alone does not rebuild
the game integration.

### Selecting an existing runtime without rebuilding

Both offline ST and VM select
`$LIVEQUEST_MINECRAFT_HOME/client-1.20.4`; when unset, the installation home is
`~/.local/share/livequestbench/minecraft`. Selection is explicit: the launcher
does not search other installations or fall back after a failed check.
The versioned directory name alone does not establish compatibility. Admission
requires the current native source/build-input digest, the recorded absolute
client root, unchanged launch metadata and present dependencies/support files.

If admission reports changed source, select an already prepared, matching
installation rather than overwriting a cache that may serve running sessions:

```bash
export LIVEQUEST_MINECRAFT_HOME="/absolute/path/to/prepared-minecraft-home"
# Read-only client admission: no launch, build, download, or model call.
.venv/bin/python -c 'from game.minecraft.runtime.client import check_client, client_root, source_digest; check_client(); print(client_root(), source_digest())'
```

Use the **same environment** for a subsequently authorized experiment. Record
the selected `ready.json` and `launch.json` SHA-256 values with its source digest;
do not copy or edit receipts to force compatibility, or move an absolute-path
installation. Client admission does not verify startup, gameplay, every
dependency's binary hash, Java/display/server readiness, or EULA consent.
An offline installation-wide check is available via
`.venv/bin/python -m game.minecraft.runtime.install check --track all`
(omit `--verify-server` to avoid fetching official metadata).

If no matching installation exists, setup really is required: choose a **new**
dedicated `LIVEQUEST_MINECRAFT_HOME` and explicitly authorize provisioning
before running setup. Never rebuild a live installation or relabel historical
native results as evidence for a newer client.

## Run an experiment

Choose a configuration from
[Minecraft experiments](../../config/minecraft/experiments/).
Inspect its Agents, tasks and repetition count before running it.

Set `EXPERIMENT_CONFIG` to your selected configuration and `RESULTS_DIR` to a
dedicated result destination:

```bash
uv run --locked --extra minecraft python run_benchmark.py \
  --config "$EXPERIMENT_CONFIG" --output "$RESULTS_DIR" \
  --headless --recording
```

Prepare the chosen Agent and model credentials first. For a small first run,
select one reference task and set `repetitions: 1`; follow the
[experiment guide](../../README.md#running-an-experiment).

## Tests

Run offline checks:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft -q
```

Enable native lifecycle, ST and VM checks after installation and EULA acceptance:

```bash
LIVEQUEST_MINECRAFT_TEST=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft/test_game.py::test_installation_world_and_recording \
  tests/test_game/minecraft/test_st.py::test_st_observation_and_tools \
  tests/test_game/minecraft/test_vm.py::test_vm_observation_and_movement \
  -q -s --headless --recording
```

These checks use actual games but no model calls. To run the broader native
suite, select `tests/test_game/minecraft` instead. Check pytest's outcome:
partial artifacts do not mean a test passed, and skipped native tests do not
verify the runtime.

Use `--no-recording` to omit video. Use `--no-headless` on an authorized X11
desktop to watch the controlled window. Do not use that display manually while
automation is running; only one game should control it.

For real model/Agent tests, follow the selected
[Agent guide](../../README.md#agents). Those tests consume provider quota.

## Tasks and fixtures

Task definitions are grouped by mode:

- [ST tasks](../../config/minecraft/tasks/structured_tools/)
- [VM tasks](../../config/minecraft/tasks/visual_motor/)

| Selection | Typical objectives |
| --- | --- |
| L1 | Short movement, item selection, basic crafting, pickup and simple interaction |
| L2 | Production chains, building, farming, cooking and short combat workflows |
| L3 | Resource-constrained production, cargo return and multi-encounter expeditions |
| Exploratory L4 | Exploration and recovery of expedition records |

Levels organize the development catalog; they are not a guarantee of calibrated
difficulty. Exact supplies, budgets, tools and success conditions are declared
in each task.

The bundled [fixtures](../../config/minecraft/fixtures/) are starting worlds,
not writable play sessions. Every Episode uses a copy. Do not launch Minecraft
directly against a source fixture or modify it in place.

### Add a task

1. Copy a task using the desired mode and evaluator.
2. Set a unique `id`, public objective and time budget.
3. Select a `fixture.world_path` and explicit starting player state. Paths are
   resolved relative to the task YAML.
4. Configure the evaluator and, for ST, the allowed tools.
5. Add the task to an experiment and validate both initial state and scoring.

Use a complete, player-free native save for a new fixture. Check that the
starting point is safe and the resources and target geometry are present.
Keep a source manifest and confirm redistribution rights. Do not alter the
world during measured play to make the task succeed.

An optional `fixture.player_state.respawn_position: [x, y, z]` initializes a
native forced spawn point in the starting dimension. This avoids world-spawn
surface selection in roofed scenarios; native death, item loss and respawn
remain unchanged. Omit it to preserve ordinary world-spawn behavior.

### Choose scoring that matches the goal

Minecraft teams opting into `native_efficiency` report native resource, travel
and damage diagnostics separately from success. Fixtures may additionally
include the passive `livequest-target-trace.json` observer for skeleton AI
targets. Its counts are sampled enemy observations, not attack counts, targeted
seconds or evidence that a teammate causally prevented damage.

| Evaluator | Suitable goals | Important limit |
| --- | --- | --- |
| `inventory` | Final item counts or net increases | Possession does not prove crafting or a particular pickup |
| `structure` | A declared block blueprint in a bounded region | Does not establish functional mechanisms or visual quality |
| `replica` | Copy an observed model into a separate empty region without changing the original | Requires the initial visible model to match every declared target cell; completion alone does not prove information use |
| `state` | Position, health, food, equipment and supported native effects | Endpoint state does not prove a route or full action history |
| `shielded_cargo` | Original chest cargo, living settled return and an actual skeleton-arrow shield block | Requires the passive native advancement observer; raising a shield alone is insufficient |
| `firebreak` | Native fire-free dwell, original roof/support retention and settled safe-pad arrival | Observed original-type losses remain lost after rebuilding; passive evidence has native-tick resolution |
| `expedition` | Designated encounters, preparation, cargo and return | Requires compatible fixture evidence and explicit conditions |

Initial `player_state.inventory` entries may declare integer `damage` for a
single tool. This writes vanilla item wear before readiness and verifies it
against native initialization; it does not grant repair or replacement during play.

For inventory requirements, `min_count`, `max_count` and `min_delta` are
independent constraints; specify at least one. A net increase is not cumulative
collection: consumed or dropped items reduce it.

Structure blueprints use `[y][z][x]` order. Define an explicit scoring region,
materials, air requirements and matching thresholds. Ensure all required
chunks exist in the source world. State every relevant condition in the public
objective, including any prohibition on extra construction.

Replica admission also checks the actual initial model and empty build pad.
The target must cover the entire model, including air cells; a mismatched model
or prefilled pad is invalid task evidence, not an agent failure.

For goals requiring a kill, trade or ordered preparation, use the appropriate
event-backed task pattern. Do not infer the event from final inventory alone.
Missing or corrupt scoring evidence must be treated as a measurement error.

## Controls and observations

### VM interface

VM receives the game window's pixels, capture timing, public task and static
control instructions. It does not receive a hidden coordinate feed, inventory
transcription or semantic navigation.

The `action` tool supports bounded key/button down/up, mouse movement, scrolling,
waits and release-all. A call contains up to 64 commands and at most 10 seconds
of explicit waits in total. Absolute mouse coordinates are relative to the
current game image.

Held inputs can persist while the model thinks. Release them deliberately.
Invalid argument batches are rejected without execution; a successful input
receipt does not by itself prove the intended game effect. Cancellation releases
controls but does not undo prior effects.

### ST interface

ST includes player position, health/hunger, inventory, held item, view direction,
nearby entities and a local block observation. The block observation extends
15 blocks from its center and is not restricted to visual line of sight.
Unknown or unloaded cells are not empty space.

Task-specific tools cover:

- Bounded movement, jumping, aiming, hotbar selection and stopping.
- Digging, placing, recipe queries, crafting and smelting.
- Container inspection and transfers.
- Attacking, held-item use and native merchant exchanges where admitted.
- Native respawn.
- Opt-in `InspectVitalsTool` reads the player's native air supply and active
  effect durations without changing controls, effects or the episode clock.

Automatic navigation is available only when admitted by the task. It is not
appropriate when route choice itself is the intended planning challenge.
Combat tools do not automatically track enemies or choose a combat strategy;
trading tools do not choose purchases for the Agent.

Use the task's tool schemas and the
[public control instructions](prompts/) for exact arguments and bounds.
ST recordings show the native player, but video is not added to ST observations.

## Death, timing and results

Death follows native Minecraft rules. VM can use the respawn UI; ST exposes
`RespawnTool`. Respawn is Agent-chosen, not automatic, and does not reset the
Episode clock, enemies or resources. The world's rules determine spawn location
and inventory loss. A no-death task remains failed after respawning.

The world advances during reasoning, network waits and actions. At the end of
play, control is revoked and the game is saved for evaluation. Snapshots are
acknowledged save boundaries, not perfectly atomic views of every entity.
Actions can have partial effects before interruption.

Results include private before/after evidence, task scoring and native death
counts. Follow the [result guide](../../README.md#reading-results) to distinguish
game failure from execution or measurement errors.

## Troubleshooting

- **Runtime missing or changed:** rerun setup with the same installation
  settings used for execution.
- **Java errors:** verify a Java 21 JDK is selected, not only a JRE.
- **Missing display:** use `--headless` from SSH, or an authorized X11/XWayland
  desktop for visible execution.
- **Incomplete assets or libraries:** rerun setup with network access and
  inspect the reported client log.
- **Native startup freezes in `SharedLibraryUtil.getLibraryPath`:** inspect
  `client-startup-threads.log`. The Fabric client backports the `dlinfo`
  resolution strategy from [LWJGL/lwjgl3#1148](https://github.com/LWJGL/lwjgl3/issues/1148)
  through Minecraft's existing JNA dependency, avoiding the concurrent
  `dl_iterate_phdr`/`dlopen` loader-lock inversion. The pinned rendering libraries
  and startup deadline are unchanged; rerun setup to rebuild an older client.
- **Unexpected results from a custom world:** verify the initial player state,
  world rules, resource availability and evaluator requirements.

For another game integration, see
[adding games](../../README.md#add-a-game). For a new Agent, see
[Agent integration](../../README.md#agent-integration).
