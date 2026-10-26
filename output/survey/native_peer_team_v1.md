# Native peer teams: implementation and protocol

This implements the approved **multi-Agent cooperation** substrate, not a new
cooperation benchmark suite or a validated capability score. The six selected
dimensions remain spatial understanding and interaction; planning and resource
management; real-time decision and execution; information use and adaptation;
multi-Agent cooperation; and within-Episode learning and improvement.

## Configuration and compatibility

Omitting `participants` preserves the existing single-player configuration,
serialized task settings, and execution path. Explicit participants use one
isolated native world/server and one independent native player/client per role.
Each role has its own initial `player_state`. Player IDs are unique,
case-insensitive, 1–16 ASCII characters, starting with a letter.

The selected experiment Agent/model configuration is instantiated independently
for every role. The experiment's `agents` list still means competing evaluated
systems, not team membership. Mixed-model teams and mixed-track teams are not
implemented. Team runs require `--headless`: each player receives an independent
virtual display, keyboard/mouse ownership, observation stream, model client,
history, video, and trace. Player count is explicit, without a hard-coded
two-player limit; resource use scales with native clients and model requests.

Example Minecraft ST task, saved beside the existing ST task files:

```yaml
id: team_rendezvous
game: minecraft
task_type: structured_tool
task: >-
  Exchange a broadcast greeting and privately report your carried supply.
  Both gather at [1.5,72,-2.5], keeping the apple and bread unconsumed.
  Stop within 3 horizontal blocks and 0.5 vertical blocks, alive.
time_limit_seconds: 240
fixture:
  world_path: ../../fixtures/island
  instance: 1.20.4
  difficulty: easy
participants:
  - id: Alpha
    player_state:
      position: [0.5,72,0.5]
      yaw: 180
      inventory: [{slot: 0, item: minecraft:apple, count: 1}]
  - id: Beta
    player_state:
      position: [2.5,72,0.5]
      yaw: 180
      inventory: [{slot: 0, item: minecraft:bread, count: 1}]
tools: [MoveTool, StopTool, BroadcastTool, ChatTool]
evaluator:
  name: team
  parameters:
    all:
      position:
        target: [1.5,72,-2.5]
        horizontal_tolerance: 3
        vertical_tolerance: 0.5
        max_speed: 0.1
    inventory_total:
      - {item: minecraft:apple, min_count: 1}
      - {item: minecraft:bread, min_count: 1}
    no_death: true
```

Veloren uses the same team fields, its existing shared fixture fields, and its
existing game-specific player-state schema. VM tasks select `visual_motor` and
omit `tools`. Existing experiment files and `run_benchmark.py` flags are reused.

## Communication and permissions

ST exposes `BroadcastTool(message)` and `ChatTool(recipient, message)` through
ordinary native chat. Explicit tool allowlists must include these names; when
omitted, the usual ST tools and both chat tools are available. Messages are at
most 200 UTF-8 bytes, with no leading command slash or control characters;
recipients must be team player IDs. A submission receipt is **not delivery
confirmation**. ST observations include only that native client's received chat,
retained for up to 100 messages, with bounded-history/truncation metadata.
Veloren's native event queue itself is bounded at 256 events; overflow before
polling is disclosed, not reconstructed from the server oracle.

VM uses only screenshots and normal keyboard/mouse events: native broadcast and
`/tell PLAYER MESSAGE`. The shared X11 key vocabulary now includes ordinary
punctuation, including `slash` and `minus`; previously `/tell` could not be typed
directly. Shift produces uppercase names and underscores. There is no semantic
VM chat tool, clipboard injection, server-transcript observation, or hidden
delivery to an Agent. Minecraft's existing client adapter exposes its own chat
HUD to ST; Veloren reuses its already-present native chat actions/events. No
server game rules or combat mechanics were modified.

P2P means **server-mediated private chat**, not network peer-to-peer. Broadcast
uses the dedicated local task server after setup administrators disconnect.
An Agent's private history is never mirrored to peers.

## Timing, termination, scoring, and evidence

All role loops receive the same monotonic start/deadline and common task.
World evolution and the budget continue during model calls, retries, messaging,
and native actions. Concurrent requests share the selected credential and may
encounter provider rate limits; no extra time is granted.

A member's final answer ends only its loop, revokes controls, and releases
held input. Its character stays in the world and remains subject to native
effects. Messages do not wake a finished Agent. All members finished, a shared
deadline, cancellation, or infrastructure failure ends the team attempt.
All participant gates close before cooperative Agent shutdown; the Minecraft
server freezes once at the team boundary, not when the first member finishes.
Followers close before the server-owning participant.

`evaluator: team` is mandatory for explicit participants, even an explicit
one-member team. All declared conditions are conjoined:

- `all`: every member satisfies the existing game's `state` predicates.
- `any`: at least one member satisfies those predicates.
- `roles`: named members satisfy their individual `state` predicates.
- `inventory_total`: sum final per-player inventory counts for each item.
- `no_death: true`: no member dies between the common snapshot boundaries.

Aggregate inventory is a final stock count, not transfer provenance. Chat
quality, delivery, or causal cooperation is **not** automatically scored by an
arrival task. Action-sequence, marker-arrival, motion, and glide-event predicates
are rejected until team-specific bindings exist. Old solo encounter/contract
evaluators are not silently reinterpreted as team objectives.

Private snapshots retain per-role native identities and capture timestamps.
They are explicitly **non-atomic**, particularly for continuously running
Veloren. Scores and death counts use those recorded boundaries; they are not
claimed to be an instantaneous global-world snapshot. Per-role evidence is
under `participants/<ID>/`; shared results aggregate accounting and deaths
while preserving each role's exit, traces, and native-source provenance.

Engineering evidence and preserved initial failures are indexed in
`native_peer_team_acceptance.json`. These are local Baseline/transport checks,
not formal rankings, cloud qualification, or evidence that every existing task
and external Agent wrapper has been independently multiplayer-qualified.

Both games' two-player ST arrival attempts succeeded. Both VM arrival attempts
failed, including the explicit follow-ups after adding punctuation keys; their
valid failures remain in the record. Native three-player diagnostics passed in
all four game/track combinations: broadcast reached all players, private chat
reached its recipient but not the third player, and remaining players continued
after one member finished. These transport results do not imply that a Baseline
Agent completed the communication/navigation task. Fourteen per-player videos
were decoded and all seven saved team evaluations replayed without rerunning
their scored actions.
