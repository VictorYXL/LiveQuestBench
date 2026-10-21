# Minecraft Structured-Tool profile

Profile: **`minecraft-1.20.4-st-native-v2`**.

VM and ST now use the same native Minecraft client, server, renderer,
initialization, snapshots and cleanup. In ST, a small client-side Fabric mod
accepts a private stdio control channel. Tools operate the controlled player's
own client, not a Mineflayer bot or a spectator. No Microsoft login, Node.js,
separate manual client launch or public bridge port is required.

This profile supersedes `minecraft-1.20.4-st-basic-v1`. Tool names remain familiar,
but the execution backend, navigation, recipe ordering and observation details
have changed. Do not pool old and new scores as the same condition.

## Window and recording

`MinecraftGame(track="structured_tool", headless=False, recording=True)` shows
the controlled player on an existing X11 desktop. The default `headless=True`
creates an owned virtual display. Both render the same native graphics and
support recording; headless does not mean a renderer-free protocol client.

Video includes the player's hand, held item, HUD and native inventory/crafting/
furnace screens. Tools open and operate the real screens through Minecraft's
client interaction manager. They do not simulate human mouse travel between
every slot; for example, crafting uses the native recipe-placement request and
slot-click operations. Screens remain visible after a successful craft/smelt
until a subsequent action closes or changes them.

Video is for human inspection, never added to the ST Agent input. There is one
player connection and no recording-only spectator. Rendering and encoding cost
resources; retain recording/display settings when comparing runs. Sampling and
readback timestamps do not establish exact native tick cutoffs.

## Public interface

- `await interface.observe()` returns current whitelisted client state and host
  monotonic request/readback timestamps.
- `interface.tool_schemas()` returns fixed name/description/JSON-schema definitions.
- `await interface.call_tool(name, arguments)` validates and executes one tool.

Observation includes player identity, feet position, health/hunger, inventory,
held item/slot, look direction, aimed/supporting block, nearby entities and a
palette-encoded block cube. The cube is radius 15 (31x31x31), centered one block
above floored feet, **without line-of-sight filtering**. Unloaded/out-of-height
cells are unknown, not air. Block descriptors contain native state ID, collision,
fluid, replaceability and breakability information, not all former Mineflayer
properties. Entity radius is 15 blocks; available entity health may reflect only
what the client has received.

Inventory slots 1-9 are hotbar and 10-36 storage. Armor/offhand, crafting-grid,
container and cursor contents are not transcribed in that player-inventory
projection. Dropped items include item name/count. Recipe queries use recipes
synced to the native client. No admin commands, raw protocol access, server files
or unrestricted client object are exposed.

## Fixed tools

| Tool | Behavior |
| --- | --- |
| `GetObservationTool` | Same projection as `observe` |
| `MoveTool`, `JumpTool` | Native movement/jump keys held for a bounded interval, then released |
| `LookAtPositionTool`, `SelectTool`, `StopTool` | Set look direction, select hotbar, release controls |
| `GoToPositionTool` | Walk toward the target block center within 64 blocks; grid search bounded to 4096 expansions, single-block steps/jumps/drops, no digging/building/parkour |
| `DigTool` | Aim at and break a reachable visible block using native interaction; show hand swing and block damage |
| `PlaceTool` | Use the held item on a reachable, visible support face; check resulting block |
| `QueryCraftRecipeTool` | Query output recipes, indices, ingredient alternatives and material availability |
| `CraftItemTool` | Open player inventory or an aimed-at table; execute recipe count, not target inventory count |
| `SmeltItemTool` | Open an aimed-at empty furnace, insert carried input/fuel, wait and collect output |

The schemas are authoritative. Recipe indices are sorted by native recipe ID.
Without an explicit index, crafting/smelting selects the first recipe with
available ingredients. No automatic collection, station setup/recovery,
equipment selection or material-chain planning is provided.

Tools run on client ticks, without blocking the world on model reasoning.
Mutating calls are serialized; observations can run while a tool is active.
The final action budget is 60 seconds; digging also has a preceding aim request.
Long smelting requests can exceed the budget, leaving partially processed
materials in the furnace. The runner owns the overall Episode wall-clock budget.

## Termination and failures

`begin` unfreezes the shared server. `end` gates new calls, cancels an active tool,
waits for the native client to acknowledge control release, then freezes the
server. The client stays connected, allowing final native evidence and video.
Cancellation removes pending multi-tick work; it does not reconnect or respawn.
Unacknowledged cancellation terminates the client and raises an infrastructure
failure rather than claiming a successful stop.

Broken blocks, spent ingredients, in-flight network effects and furnace contents
are not rolled back. Normal action refusal returns `success=false`; bridge
failure/timeouts raise. Death never triggers automatic respawn.
Vanilla `tick freeze` does not freeze player packets, so snapshots remain
acknowledged save boundaries rather than atomic tick/deadline cutoffs.

The cooperative Python/stdio boundary is not a sandbox for hostile Agent code.
The mod is inactive for VM, which retains the pixel-only public interface.
Native Minecraft logic is used for breaking, placement, recipes and slot
transactions; this integration does not grant game/asset redistribution rights.
