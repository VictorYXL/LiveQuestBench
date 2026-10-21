# Test Minecraft with LiveQuestBench

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

Default result with dependencies installed: **4 passed, 3 skipped**.
With live checks enabled and both modes prepared: **7 passed**.
For ST only, replace the directory with
`tests/test_game/minecraft/test_st.py`. All three live cases deliberately point
Prism at a nonexistent directory to detect accidental account dependencies.
Select `test_vm.py` similarly to check VM alone.
Both mode tests record `video.mp4` at 10 FPS by default, with brief viewing pauses
before and after their scripted actions. Set `MINECRAFT_TEST_RECORDING=0` to
disable their videos and save encoding cost; the native renderer is still used.

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
[client guide](../../agents/llm/README.md) for Copilot, OpenAI and local vLLM.
Keep `--extra minecraft` in `uv run`/`uv sync` commands in this environment.
Store credentials in your own environment; none are shipped with the repository.

There is no built-in autonomous Agent or end-to-end Benchmark launcher yet.
Custom integrations use [`BaseAgent`](../../agents/base_agent.py) and one
`MinecraftGame`, selecting `track="visual_motor"` or `track="structured_tool"`.
Both follow:

```text
start -> before snapshot -> begin -> Agent -> end -> after snapshot -> close
```

Always close in `finally`. Pass only `get_agent_interface()` to the Agent:
the [VM guide](guide/visual_motor.md) covers pixels/input; the
[ST guide](guide/structured_tool.md) lists the fixed tool profile and semantics.
The test suite uses scripted actions, not an LLM, and passing it is not an Agent
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
  [environment overrides](guide/visual_motor.md#installation-overrides).
