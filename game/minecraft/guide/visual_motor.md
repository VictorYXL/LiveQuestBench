# Minecraft VM controls

The public task text and actual screenshots are the source of game information.
No inventory transcription, coordinates, semantic navigation, console commands
or scorer state are exposed.

## Observation

`await interface.observe()` returns a fresh `CapturedFrame`: frame identifier,
window identifier, capture-start/end host monotonic nanoseconds and a PIL RGB
image. Timestamps bound host image readback, not a native game tick. The caller
encodes the image for its model client. Captures contain only the bound Minecraft
window; there is no desktop fallback.

## Motor input

`await interface.act(commands)` accepts a list of objects with exactly `name` and
`arguments`. Available operations:

| Name | Arguments |
| --- | --- |
| `key_down`, `key_up` | `key`: a supported key name |
| `mouse_down`, `mouse_up` | `button`: `left`, `middle`, `right` |
| `mouse_move_relative` | Integer `dx`, `dy`, each -32768 through 32767 |
| `mouse_move_to` | Integer window-relative `x`, `y`, within the current window |
| `mouse_scroll` | Integer `steps`, -20 through 20 |
| `wait` | Integer `milliseconds`, 0 through 10000 |
| `release_all` | Empty object |

A batch contains 1 through 64 commands and at most 10000 milliseconds of explicit
waiting. Structural arguments are validated before execution; window geometry,
focus and pointer ownership are checked at execution time. Concurrent interface
calls are serialized. Calls waiting for the interface are rejected after `end`.

Keys include `a`-`z`, `0`-`9`, `space`, `enter`, `escape`, `tab`, `backspace`,
`delete`, `insert`, arrows `left`/`right`/`up`/`down`, `home`, `end`,
`page_up`, `page_down`, `left_shift`, `right_shift`, `left_ctrl`, `right_ctrl`.
Alt/Super/Meta and game commands are not exposed.

Held keys/buttons **persist across calls**, including during model reasoning,
until explicitly released, an executor failure, or game termination. A successful
call acknowledges X11 input submission, not a guaranteed in-game effect.
Cancellation/failure releases held inputs but cannot undo already-applied game
effects. Do not automatically retry a partially executed batch.

For example, moving forward for one second means `key_down("w")`, a
1000-millisecond `wait`, then `key_up("w")`, encoded in the command format above.
The wait delays the next command; it does not pause Minecraft. The VM smoke test
performs this sequence, waits briefly after release, looks down with relative
mouse motion, then holds the left mouse button for two seconds and releases it
to swing/mine beneath the player. This is an input smoke test, not a dirt
collection task: it checks horizontal movement and downward view, but does not
require item acquisition. Private before/after saves are retained for inspection.
A custom test fixture must allow the movement sequence. Its default recording
includes these actions.

Headless runs save Xvfb diagnostics to `xvfb.log` in the run directory instead
of printing them to the terminal. Display-number probing can report occupied
displays before selecting a free one; unsupported XF86 special-key symbols can
also produce nonfatal keyboard-map warnings. Startup failures still raise an
error pointing to this log. Existing desktop displays are not reconfigured.

The default native client starts with fresh standard controls:
WASD moves, Space jumps, Shift sneaks, Ctrl sprints, mouse movement looks,
left button attacks/mines, right button uses/places, E opens inventory,
1-9 selects a hotbar slot, Q drops an item, and Escape opens the menu.
The optional authenticated Prism path retains its instance's bindings.
Opening a menu in this
multiplayer session does not pause the server.

Use an isolated virtual display or a dedicated existing desktop display;
do not interact manually while automation runs. XTest is display-global and
focus checking is not a security boundary. Observations/actions are unavailable before `begin` and after
`end`.

## Lifecycle and private evidence

For a custom integration, the caller owns this sequence:

```text
start -> save_snapshot(before) -> begin -> Agent execution
      -> end -> save_snapshot(after) -> close
```

Always call `close` in a `finally` block, including after partial startup.
Initialize a fresh game and Agent for each Episode. The Agent receives only the
public task and `MotorInterface`, not server administration, world saves or the
evaluator. This cooperative Python API is not a sandbox for hostile code.

`start` loads a fresh world copy, freezes world ticks and verifies the configured
initial player state. VM also verifies actual mouse-look and hotbar input
acceptance: the first cursor event after mouse capture can be discarded.
It restores the configured orientation with a private initialization command
and restores slot 1, then rechecks the full initial state before returning.
No such administrative correction occurs during measured play.
A connected player alone does not prove loading screens are gone.
`begin` verifies again and unfreezes. World time continues
while the Agent thinks or waits. `end` gates new input, interrupts motor waits,
releases held input and requests a tick freeze without closing the client.

Snapshots are allowed only at initial/terminal frozen boundaries. The harness
disables automatic saving, confirms `save-all flush`, copies the world, records
hashes and host monotonic timestamps, and restores automatic saving.
**Vanilla tick freeze does not freeze players or their network packets.**
These receipts are not atomic all-entity snapshots at an exact native tick or a
strict deadline. Startup advances the world before freeze; the initialized live
before snapshot is the scoring baseline. Failed/partial snapshots are not valid
scoring evidence.

Inventory evaluation checks native saved counts and deltas; it does not prove
item provenance or a particular skill's use. Missing/malformed evidence raises.
Independent window recording is host-sampled, not native-frame-exact; failures
propagate. The runner must distinguish game failure from infrastructure or
measurement failure.

## Installation overrides

| Variable | Meaning |
| --- | --- |
| `MINECRAFT_JAVA` | Client/server Java 21 executable; also selects Java for setup |
| `MINECRAFT_SERVER_JAR` | Server JAR or explicit installation destination |
| `MINECRAFT_PRISM_ROOT` | Existing Flatpak Prism directory, only for explicit online VM |
| `LIVEQUEST_MINECRAFT_HOME` | Managed client build/cache/downloads/locks; default `~/.local/share/livequestbench/minecraft` |

Without an explicit JAR, the managed download is preferred, followed by an
existing GameAgentVisual download under `GAMEAGENTVISUAL_HOME` or
`~/.local/share/gameagentvisual`. Verify reused artifacts with
`game/minecraft/setup.sh --check --verify-server`.

Default setup uses Gradle 8.6 (SHA-256 verified), Fabric Loom 1.6.12,
Fabric Loader 0.15.11 and Yarn 1.20.4+build.3. A client-only control mod exposes
the ST bridge only when explicitly enabled; it is inactive in VM. There is no
replacement renderer or step-based simulation controller. A dedicated vanilla
server continues running while the Agent thinks.

Setup exports the development launch configuration/classpath; Episodes start
the owned Java process directly, not Gradle or a desktop launcher. Each Episode
has its own client directory and standard options; dependency caches are shared.
Local startup neither reads account files nor takes the legacy account-login lock.
The environment receipt identifies the client as `fabric-development`.
Setup validates build-source fingerprints and dependency presence before launch.

Only for the optional authenticated Prism path, private client profiles are
outside run artifacts and removed at cleanup.
Credential files have restricted permissions. Assets, libraries and metadata
are copied into writable private caches so refreshed indexes can download
missing objects without changing the original installation.

## Provenance

The VM implementation adapts GameAgentVisual `xianya/init_mincraft`, commit
`696257de4ba7788f68026084b794d1265677f75b`. Its checkout is not a runtime dependency.
Default local authentication is offline with a consistent offline player UUID.
The Fabric development-launch approach removes the Prism/account prerequisite
without changing Minecraft's renderer or the public motor interface.
`authentication="online"` retains the separately prepared Prism path.
ST shares the same native client, using its private structured control bridge.
This provenance statement grants no new license or permission to redistribute
Minecraft binaries/assets.
