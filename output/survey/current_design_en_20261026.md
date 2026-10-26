# LiveQuestBench: six capability dimensions and task redesign

**Updated:** 2026-10-26, UTC+08:00.

**Chinese companion:** [Current design in Chinese](current_design_zh_CN_20261026.md).

**Latest status:** all legacy runnable configurations have been moved from the
root `config/` to the [configuration archive](../back/legacy-config-20261026/README.md).
The seventy-candidate draft is not an accepted final task set: several focused
items are too close to mechanism checks. The next design focus is six substantive
focused anchors, using former L2 as a minimum content reference and normally L3,
with intended 5-30 minute completion times subject to empirical calibration.
This does not restore five difficulty tiers. No anchor implementation or
model/Agent discrimination result exists; design is paused for the archival step.

**Decision:** replace the five-level organizing framework with six capability
dimensions. L1–L5 remain historical labels, not current selection quotas,
capability axes, or difficulty bands. Preserve old configurations and results.
The dimensions and reuse-first direction are accepted; candidate families,
metadata names, scoring weights, and release size below remain proposals.
This documentation revision does not change tasks, budgets, scorers, or runs.

**Subsequent task-design decisions:** use two formal categories, focused and
integrated, without manual difficulty tiers. The requested design worklist is
ten focused candidates per dimension
([sixty-candidate catalog and combined counts](focused_task_catalog_60_20261026.md)) plus
[ten integrated candidates grounded in native goals](integrated_task_catalog_10_20261026.md).
The combined worklist contains 35 objectives per game, targeting 140 VM/ST
combinations, not 140 qualified configurations.
The earlier eight-family slice below remains a reference for incremental
development, not the current catalog size or a frozen release quota.

## 1. Research focus and unchanged boundaries

**When the world does not wait for a model to think, can an Agent coordinate
immediate action and long-horizon plans under persistent dependencies, finite
resources, and delayed consequences?**

Evaluate Agents through consequential native game situations, rather than
measuring encyclopedic game knowledge or claiming a context-free intelligence
test. Minecraft and Veloren remain the initial games. The six dimensions
describe overlapping demands, not six proven independent latent abilities.
Do not force every task to exercise every dimension.

VM supplies actual screenshots and bounded native keyboard/mouse control.
ST supplies allowlisted native observations and fixed game-specific tools.
Rank and interpret them separately: changing both observation and action
capabilities is not a pure vision ablation. Model comparisons fix scaffold,
history policy, tools and budgets; full-Agent comparisons disclose those
choices. Reasoning, network waits, retries and tool actions do not pause the
world. Controlled-delay or paused conditions are separate diagnostics.

Keep the six-step research process: scope -> framework/protocol -> games/tasks
-> Agents/experiments -> evidence-led iteration -> frozen release. Existing
related work overlaps substantially; do not claim “first” from an incomplete
search. Preserve game licensing, native mechanics, evidence isolation, failure
classification, and source/version recording.

## 2. The six dimensions

| Dimension / proposed metadata ID | Core question | Task patterns and discriminating evidence |
| --- | --- | --- |
| Spatial understanding and interaction / `spatial_interaction` | Can the Agent use position, terrain, viewpoint and physical relations effectively? | Occluded or elevated access, building a usable crossing, interaction distance and combat positioning. Contrast spatial alternatives with an otherwise similar direct-access condition. Not limited to timed navigation. |
| Planning and resource management / `planning_resources` | Do current choices preserve later goals and finite resources? | Shared fuel/material budgets, competing purchases, preparation and retained return supplies. Verify real dependency and resource competition, not just a long action list. |
| Real-time decision and execution / `realtime_execution` | Can the Agent act correctly in time while the world changes? | Expiring supplies, native attack opportunities and ongoing furnace consumption. Pair pressure conditions with equivalent low-pressure conditions and report sensitivity to added latency separately. |
| Information use and adaptation / `information_adaptation` | Can the Agent acquire, remember and verify information, then revise its plan? | Native clues/directions, uncertain passages, revisiting discovered routes, verifying failed actions. Compare discoverable information with an explicitly supplied-information control. |
| Multi-Agent cooperation / `peer_cooperation` | Can equal Agents divide work, communicate and coordinate toward a common goal? | Distributed observations, complementary initial resources, jointly timed collection/return. Compare with matched no-chat or shared-information team conditions; count outcomes, not message volume. |
| Within-Episode learning and improvement / `within_episode_learning` | Does earlier experience improve later behavior in related but different situations? | Several native traversal, interaction or encounter opportunities followed by a changed-layout application. Require transfer evidence, not character upgrades, one correction, or repeating an identical action. |

Spatial demands exist in almost all 3D tasks; that alone does not make every
task a spatial diagnostic. A dimension is primary when the design deliberately
varies a relevant demand and provides evidence about it. Other demands remain
secondary confounds to control or report. Likewise, raw response latency is an
execution cost, not by itself a real-time decision competence score.

Adaptation means updating a current plan from new evidence. Within-Episode
learning requires evidence that prior experience improves subsequent related
behavior beyond that immediate correction. All learning opportunities and
applications stay inside one continuous Episode; no cross-task memory,
cross-Episode training, or model-parameter update is required.

## 3. Organization: dimensions guide design; tasks carry metadata

Keep `config/<game>/tasks/{structured_tools,visual_motor}/`. Do not create six
capability directories, duplicate a task across them, or infer scores from file
placement. Use two formal task categories:

- **Focused:** a primary capability demand, supported by matched conditions.
- **Integrated:** a coherent long objective with meaningful dependencies across
  several dimensions, evaluated separately from focused-axis scores.

Basic control, interface and transport diagnostics support engineering and
interpretation; they are not a third formal scored task category.

Proposed descriptive fields, **not accepted by the current strict loader yet**:

```yaml
task_family: spatial_access
evaluation_role: focused
condition_id: staggered_occlusion
capabilities:
  primary: [spatial_interaction]
  secondary: [planning_resources]
```

Focused tasks normally have one primary dimension; integrated tasks may have
several. Tags describe demands, not an expert-assigned Agent score or automatic
inclusion in several radar axes. A separate versioned evaluation selection
defines axis membership, family/variant grouping and weights. Metadata
implementation is a subsequent small schema change, not part of this revision.

Empirical difficulty is reported for a specified game, track, Agent, budget and
task distribution. Do not prescribe five tiers or tune tasks until preferred
success rates/rankings appear. Native game difficulty settings remain legitimate
fixture parameters; they are not the removed L1–L5 benchmark ladder.

## 4. Reuse-first migration of the existing catalog

Existing task YAMLs, historical L1–L3 groups, and the exploratory
`lost_expedition` remain intact. They are a source pool, not a required release
size. The historical snapshot has 60 paired objectives plus one exploratory
pair, or 122 VM/ST YAMLs; temporary multiplayer smoke tasks are not additional
published catalog families. These counts are not six-dimension coverage claims.

| Existing examples | Proposed disposition | Required change or interpretation limit |
| --- | --- | --- |
| `reach_nearby_point`, `select_pickaxe`, `move_2_metres`, `equip_supplied_armor`, `recover_health` | Retain as diagnostic prerequisites | No automatic primary-axis credit for a basic control check. |
| `staggered_detour`, `elevation_steps`, `glide_and_land`, `bridge_small_gap` | Reuse for spatial-access variants | Add meaningful layout/visibility alternatives and direct-access controls; respect allowed native shortcuts. |
| `shared_fuel_extraction`, `leather_outfit`, `food_reserve` | Reuse for planning/resource contrasts | Separate finite competition from mere possession. Additional gathering may be legal; measure whether it removes the claimed constraint. |
| `expiring_supply_return`, `block_and_counter` | Reuse for real-time contrasts | Record actual opening lifetimes/native effects. A deadline or a combat failure alone does not establish latency sensitivity. |
| `follow_quarry_note`, `workshop_directions` | Reuse for information acquisition/use | The former mainly scores arrival; the latter already requires native received directions. Add evidence only when the claim requires it. |
| `scout_outposts_return_0`, `two_outposts_return`, `market_hunt_return` | Reuse as integrated solo candidates | Preserve planning, resource and information dependencies; do not score the same success independently on all tagged axes. |
| Current two-player chat/arrival smokes | Retain as multiplayer engineering diagnostics | Working chat and joint arrival do not yet demonstrate necessary cooperation. |
| `companion_hunt_return` | Retain as native companion protection | The sheep is not another evaluated peer Agent; this is not evidence for the cooperation axis. |
| `learn_recipe`, `learn_food`, `known_food` | Retain as game-mechanism diagnostics | Unlocking a recipe is character state, not demonstrated Agent learning. A new within-Episode repeated-and-transfer family is needed. |
| `lost_expedition` | Keep as an exploratory integrated candidate | Its long budget and prior L4 label do not prove adaptation or learning; exclude from a compact mandatory set until its contribution is clearer. |

Actual source examples constrain the redesign. `shared_fuel_extraction` permits
legal resource replacement and alternative crossings. `expiring_supply_return`
uses native aged drops, not an invented timer. `workshop_directions` binds native
received markers. `scout_outposts_return_0` explicitly warns that successive
passages need not share the same opening: it is not evidence of a hidden stable
rule learned between walls.

## 5. Earlier compact development slice: six focused families plus two integrated

The following **eight-family proposal** is a starting worklist, not eight frozen
YAMLs, a mandatory rectangular game-by-dimension matrix, or a final release size.
Each family needs a small set of meaningful variants/controls; seeds and VM/ST
copies are not independent capability families.

| Candidate family | Initial design | Evidence / matched condition | Reuse and remaining work |
| --- | --- | --- | --- |
| F1 Spatial access | Reach or interact with a target using alternative elevations, occlusion or a constructed crossing | Endpoint/structure plus relevant movement evidence; direct access vs obstructed access | Existing detour, steps and bridge fixtures; candidate geometry and budget calibration |
| F2 Resource allocation | Produce or purchase several needed outputs while retaining supplies for a subsequent leg | Joint endpoint conditions; constrained vs plentiful resources with comparable routes | Shared-fuel and leather-outfit mechanisms; audit replenishment and actual trade-offs |
| F3 Timely prioritization | Recover native expiring resources and return; optionally contrast a native combat-response family | Real opening lifetimes, resource loss, action timing, outcome under matched pressure/added-delay conditions | Expiring-supply and block/counter mechanisms; delay condition and analysis not implemented |
| F4 Information-guided revision | Obtain clues/directions, choose an initially uncertain route, and use discoveries on return | Native information receipt where available, avoidable revisits and successful completion; known-information control | Notes, directions and scouting; new variants and additional history evidence as needed |
| F5 Distributed recovery | Two equal Agents start apart with different local information/resources; decide who retrieves what and where to reunite | Joint delivery and survival; chat-enabled vs no-chat/shared-information teams with the same player count and budgets | Native peer substrate exists; consequential information layout and scoring remain to design |
| F6 Experience and transfer | Earlier opportunities expose a native movement/interaction/encounter pattern; later application changes location, orientation or relevant context | Later errors/resource cost under matched opportunity controls; account for health, gear, familiarity and elapsed time | New Episode-level task and phase evidence; no validated learning evaluator yet |
| I1 Solo expedition | Prepare, discover access, fight or recover cargo, and return with required reserves | Whole-task success plus explicitly supported phase/condition outcomes; independent-skill controls | Reuse outposts, market expedition, or shared-fuel crossing; do not concatenate unrelated successes |
| I2 Team expedition | Distributed reconnaissance/preparation and timed recovery followed by a shared return goal | Explicit team conditions and communication controls; integrated score separate from radar axes | Reuse native teams and supplies; team encounter/contract event scoring is not automatically available |

F1 must not collapse into “walk to coordinates”: useful alternatives include
placing a usable crossing, finding an interaction viewpoint, or achieving a
position with required line of sight. F3 must not collapse into “make the time
limit shorter.” F5 should let Agents choose a division of labor, not receive a
complete prescribed dialogue/role script or points for saying enough words.
Use ordinary terrain, signs/items, drops, inventory and native chat, not
artificial role locks or modified NPC mechanics.

For F6, candidate learning opportunities include calibrating movement bursts
across several native gaps, improving interaction positioning across changed
orientations, or using earlier native encounter feedback in a later encounter.
Hold rules stable while varying application context. Pure recall of one
coordinate is an information-use task, not sufficient transfer evidence.
Equipment improvements, easier later stages and survivor selection can create
apparent learning; control or report them and include failed early trajectories.
If the evidence cannot separate these explanations, label the score exploratory
or unavailable rather than claiming verified self-improvement. Diagnostic
control runs may be independent Episodes; no Agent carries learning between
them, and the scored learning trajectory itself remains within one Episode.

## 6. Radar plots and dimension scores

Primary reporting remains native task outcomes with execution/measurement
status. Do not infer six ability scores from one integrated success/failure.
Proposed focused-axis aggregation:

1. Freeze tasks, variants, repetitions, budget, membership and weights before
   confirmatory evaluation. Do not select favorable tasks after seeing rankings.
2. Aggregate repeated outcomes within each task variant, variants within a
   family, then families within a dimension. Equal family weights are a proposal,
   not a currently implemented leaderboard rule.
3. Show VM/ST separately; report per-game scores before any explicitly weighted
   cross-game view. Do not let additional near-duplicate tasks give one game or
   mechanism disproportionate weight.
4. Show family/episode counts, uncertainty and missing coverage. Account for
   shared fixtures and correlated variants rather than treating every repetition
   as independent evidence. A one-family axis is preliminary, not a broad
   validated capability scale.
5. Report integrated tasks separately. Secondary tags do not duplicate credit.
   Task-specific partial progress needs a published grounded rubric; no generic
   partial-credit scale is introduced here.

A valid gameplay failure can contribute zero. Infrastructure errors, missing
evidence, or a benchmark dimension that is not implemented are not Agent zeros.
An Agent that genuinely cannot participate in an otherwise supported and
published protocol can receive zero only under a predeclared eligibility rule;
retain that distinction from infrastructure failure. Do not silently renormalize
missing coverage into an apparently comparable full radar polygon.

Report latency/cost, survival, resource expenditure and team communication
diagnostics beside capability-oriented task scores. Team Episodes have multiple
concurrent model clients: disclose team size, per-role and aggregate usage,
wall-clock and comparison budgets. A two-player/no-chat control helps separate
communication from merely adding a second actor; solo-versus-team scores alone
do not isolate cooperation.

## 7. Current multiplayer implementation and its limits

Omitted `participants` preserves the solo path. Explicit participants instantiate
the same selected Agent/model independently in one world, with individual initial
states and private histories. Current teams are homogeneous and same-track.
ST has native `BroadcastTool`/`ChatTool` and own-client received chat; VM uses
screenshots and physical keys, now including punctuation for `/tell`.
Member completion stops only that member; its character stays in the world.
The shared deadline or all members finished ends the team.

The existing team evaluator supports explicit `all`, `any`, named `roles`,
aggregate final inventory, and `no_death`. It does not silently convert old
solo encounter/contract scorers or establish causal communication credit.
Snapshots preserve per-role capture timing and are non-atomic.

Both games/tracks have local two-player Baseline runs and three-player native
broadcast/private-isolation checks. ST examples succeeded; VM examples retain
valid task failures. These establish a usable substrate, not a validated
cooperation family or qualification of all external Agent wrappers.
See [protocol](native_peer_team_v1.md) and
[source-bound local evidence](native_peer_team_acceptance.json).

## 8. Implementation sequence after this design update

1. Inventory existing tasks against the six demands, actual scoring evidence,
   native mechanisms, tool assistance and per-track gaps; choose reuse, adjust,
   diagnostic-only or hold. Preserve historical IDs/results.
2. Review the sixty-focused/ten-integrated candidate worklist and the claims each
   family can support. Use the earlier compact slice to prioritize implementation,
   including F5/F6 gaps, rather than committing to implement every candidate.
3. Add the minimal metadata/selection schema once reviewed; do not change game
   lifecycles or move tasks into capability directories.
4. Implement missing variants and evidence only where needed. Review proposed
   transfer, native trade, phase or team event requirements before building them.
5. Use bounded Baseline acceptance in the admitted game/track conditions;
   separately check native feasibility/transport. Preserve valid failures and
   inspect whether matched contrasts isolate the intended demand.
6. Calibrate budgets/difficulty, revise unsupported claims, then freeze a small
   task distribution and analysis plan before broader model/Agent evaluation.
   Expand coverage because of a demonstrated gap, not to fill a task-count quota.

No new task YAML, schema field, six-axis scorer, game run, model run or cloud job
is created by this documentation revision. Existing gameplay, permission,
licensing and native-source constraints continue to apply.
