# Explicit World Fixtures: Implementation and Acceptance

## Agreed contract

A Task must explicitly declare its fixture. Missing resources or unsupported
initialization fields are errors, never permission to generate a default world.
Game-specific loaders interpret the mapping; the benchmark does not invent a
universal world format or perform task-specific administrative commands.

The user initially requested full Veloren snapshot restoration, then clarified
that a composite parameter-defined fixture with a game-side initialization
interface is acceptable after the native persistence limitations were verified.
The implementation follows that later clarification. It does not claim a
complete live-engine checkpoint.

The Task schema now has a required top-level `fixture` mapping, replacing
`initialization`. Existing configuration files and all direct game constructors
in maintained tests were migrated.

## Minecraft

Both VM/ST Tasks require `world_path`, `instance`, `difficulty` and `player_state`.
Relative world paths resolve against the Task file, never the launcher cwd.
The game requires an existing native save and copies it to fresh owned storage.
There is no `None` fixture, generated-world fallback, or task-level fill command.

The repository includes a 2.2 MB native world under
[`config/minecraft/fixtures/collect_3_logs`](../../config/minecraft/fixtures/collect_3_logs/).
It contains `level.dat`, native region files and empty entity region files.
It is shared by both modes and already contains three oak logs at x=0, z=-2,
y=72..74. It was exported from the verified pre-Episode native save, not from
the original island map. Player/history/private command storage were excluded;
time is 0, day time is 6000, weather is clear and mob spawning is disabled.
The source receipt records the export and per-file hashes.

This is task-authored native world data, not a bundled game executable, texture
pack or proprietary binary distribution. Game acquisition/EULA obligations
remain independent.

## Veloren

[`game/veloren/fixture.py`](../../game/veloren/fixture.py) exposes:

- `validate_fixture`: exact field and supported-capability validation.
- `initialize_fixture`: native geometry, position, inventory, health and time setup.
- `verify_player`: native readback of declared player conditions.

The mapping explicitly selects the installed map asset, world seed, initial
time of day, day length, calendar policy, absolute platform origin/size/block,
player position/look/health/inventory and expected equipped items.
The server writes these world settings into isolated userdata and records
the concrete map/settings hashes. Missing assets and detected native fallback
warnings fail initialization. Calendar events no longer depend on the host date.

The current profile admits Rock platforms and initial look `[0, 1, 0]`.
Inventory can be rebuilt with existing native cleanup/gift helpers; equipment
is an exact requirement against the pinned ordinary-character loadout, not an
unimplemented arbitrary equipment editor. No alternate value is silently used.

Source verification distinguished three different concepts:

1. `world/src/sim/mod.rs::FileOpts` supports native `Load` and `LoadAsset` map files.
2. `server/src/persistence/mod.rs::PersistedComponents` does not persist all
   live player components, such as current health/velocity.
3. Terrain persistence is experimental and disabled by default; RtSim has
   explicitly skipped serialized state.

Therefore a Veloren map file alone cannot represent a full running-world
snapshot. The implemented contract is explicit initial scene construction for
a pinned runtime, not identical live ECS state or bitwise replay. Ambient
simulation, IDs, setup tick counts and later trajectories can vary.

## Executed checks

- **13 focused offline tests passed**, three real-game tests deselected in that
  command. Includes missing/default fixture rejection, path resolution, native
  template copying, a deliberately damaged first working copy followed by an
  intact second reset, unchanged source hashes, native-state mismatch rejection,
  runner faults and scorer regression.
- **5 Minecraft tests passed in 79.05 s**: offline checks plus real lifecycle,
  VM and ST loading, snapshots, input and source isolation.
- **2 real Veloren VM/ST tests passed in 103.02 s** using explicitly declared
  map/scene/player fields.
- **4 fixture tests passed in 47.32 s**, including a real changed-parameter case:
  platform and player shifted +16 metres in x, initial health 95 and inventory
  changed to exactly two cheese. Native readback matched the modified configuration.
- **Real CLI SIGINT regression passed in 46.13 s** with the new owned native
  server and explicit fixture. No native process cleanup failure was reported.
- Changed Python modules compiled; tracked-file whitespace checks passed.

The production CLI reran both built-in experiments with `gpt-6-astra`, headless
rendering and recording:

| Game | Mode | Private outcome |
| --- | --- | --- |
| Minecraft | VM | Success: 0 to 3 oak logs |
| Minecraft | ST | Success: 0 to 3 oak logs |
| Veloren | VM | Success: 7.923828125 horizontal metres, 100 health |
| Veloren | ST | Success: 22.1103515625 horizontal metres, 100 health |

Evidence:

- [Minecraft explicit-fixture run](../benchmark_acceptance/minecraft-explicit-fixture/summary.json)
- [Veloren explicit-fixture run](../benchmark_acceptance/veloren-explicit-fixture/summary.json)

Both Minecraft modes verified the same nine immutable native source files.
Both Veloren modes started at `[18706.5, 10806.5, 402]`, 100 health, with the
declared inventory/equipment/look and the same map SHA-256:
`2560ecb22feccc642aaf75addfaf22e3066defe8668ca052770ef902a2c5e2da`.
Both native servers stopped without forced termination; their recorded PIDs
were absent afterward. The ST trajectory left the platform; success follows
the existing distance-plus-alive evaluator, not a new navigation-quality claim.

The complete external-Agent matrix was not rerun. Historical outputs were
preserved. No commit or push was performed.
