# Sixty focused task candidates and the seventy-task design worklist

**Date:** 2026-10-26. **Status:** design only; no new runnable configurations.
**Chinese companion:** [Focused catalog and combined counts](focused_task_catalog_60_zh_CN_20261026.md).
**Integrated catalog:** [Ten native-goal missions](integrated_task_catalog_10_20261026.md).

**Review status:** reference draft, not the accepted final task set. Several
items need a larger sustained-decision workflow. The next design focus is six
anchors, with former L2 as a minimum content reference, normally L3, and intended
5-30 minute completion times to be calibrated. Legacy runnable configurations
are now in the [archive](../back/legacy-config-20261026/README.md), not root `config/`.

## 1. Counting and interpretation

| Scope | Minecraft | Veloren | Total objectives | VM/ST target combinations |
| --- | ---: | ---: | ---: | ---: |
| Spatial understanding and interaction | 5 | 5 | 10 | 20 |
| Planning and resource management | 5 | 5 | 10 | 20 |
| Real-time decision and execution | 5 | 5 | 10 | 20 |
| Information use and adaptation | 5 | 5 | 10 | 20 |
| Multi-Agent cooperation | 5 | 5 | 10 | 20 |
| Within-Episode learning and improvement | 5 | 5 | 10 | 20 |
| Focused subtotal | 30 | 30 | 60 | 120 |
| Integrated missions | 5 | 5 | 10 | 20 |
| **Combined design worklist** | **35** | **35** | **70** | **140** |

This fulfills the requested **candidate design count**, not an implementation,
feasibility or measurement-validity claim. A goal-level task and its two track
implementations are different counting units. No 140 new YAMLs are created.
Seeds, matched controls, repetitions and extra team sizes are not additional
objectives in this count. The split is a useful proposed balance, not a reason
to retain a weak task after review.

The sixty focused candidates each have one primary dimension, a native goal
and a proposed discriminating comparison. They are not pure cognitive tests.
There are no easy/medium/hard labels. Former L2-L3 is only an intuition for
bounded workflows; longer learning sequences may depart from that intuition.

All F-C tasks propose two equal peer Agents; all other focused tasks propose
one. Together with the integrated catalog, the worklist contains 58 solo and
12 two-player objectives. Each peer is an independent instance of the same
chosen Agent/model with private history, one native character and the shared
goal/deadline. No pets or internal subagents count as peers.

## 2. Reading the candidate cards

Each card specifies **goal/start**, **decision**, **evidence**, **comparison** and
**reuse/admission**. Evidence is a proposal unless explicitly identified as an
existing scorer. Reuse references `MC:name` and `VE:name` refer to existing files
under `config/minecraft/tasks/structured_tools/` and
`config/veloren/tasks/structured_tools/`, respectively, with a `.yaml` suffix.
They identify source mechanisms, not an assertion that the candidate already
exists under that name or that its VM counterpart is qualified.

Every card targets VM and ST subject to admission. Shared gates:

| Gate | Applies to |
| --- | --- |
| VM uses screenshots and physical keys only; no hidden-state readback, typed chat injection or semantic completion macro | All candidates |
| Minecraft ST exposes a local block cube, not strict line-of-sight visibility; walls do not automatically hide nearby geometry | Spatial, information and cooperation candidates |
| Exclude `GoToPositionTool` where its internal navigation resolves the spatial or movement-calibration demand | F-S01/02/04, F-I02/04, F-L01 and relevant route variants |
| Use native furnace slot/state operations, not `SmeltItemTool`, where internal waiting removes the resource/timing/batching decision | F-P01, F-T01, F-I05, F-L03 |
| Veloren movement durations are native client updates, not guaranteed seconds | All movement and timing interpretations |
| Minecraft ST has chest take but no general qualified deposit/drop; Veloren peer transfer is not established by NPC trade | F-C01, F-C08 and any later handoff-dependent variant |
| Current team endpoint composition is not a general encounter, marker, motion, transfer or event scorer | All F-C cards requiring those events |
| Inputs/state cannot silently gain new fields or powers to make a task pass | All missing-interface candidates |

Do not pause the measured world or reset/heal between stages. Use ordinary
blocks, items, terrain, recipes, attacks, dialogue and native chat, not new
gameplay rules. Legal gathering, digging, building, retreat and other native
solutions remain allowed unless a restriction is explicit, justified and
versioned. Endpoint success does not prove the intended strategy; compare or
inspect processes before making the corresponding capability claim.

Primary success rules, partial credit, death/respawn, budgets and exact starting
stocks remain task-specific design decisions to review before implementation.
Do not silently propagate the integrated catalog's proposed recovery rule into
the existing focused no-death tasks. An opening that is invalid or missing
required benchmark evidence is not a valid Agent failure.

## 3. Spatial understanding and interaction

Primary metadata proposal: `spatial_interaction`.
Supply enough resources and time to keep scarcity secondary where feasible.

### F-S01: Find a traversable passage — Minecraft

**Goal/start:** retrieve a named cache item beyond two ordinary offset partitions
and return; supply basic tools, food and building material.
**Decision:** distinguish a short-looking blocked approach from a usable route,
including legal digging/building alternatives.
**Evidence:** correct item and return endpoint; route and obstruction encounters
are diagnostics, not a mandated path.
**Comparison:** matched open-access layout with similar travel extent and stock.
**Reuse/admission:** `MC:scout_outposts_return_0`, without its two required fights.
New geometry/control pairing; ST local geometry must not be described as
visually hidden, and the navigation macro must not solve the task.

### F-S02: Build an offset crossing — Minecraft

**Goal/start:** move cargo across a gap whose opposite landing is laterally
offset, using ample supplied ordinary building materials.
**Decision:** reason about supporting faces, reach, collision and a usable
landing rather than placing a straight line blindly.
**Evidence:** cargo arrival and newly present usable floor structure; native
alternative crossings remain legal under the published endpoint goal.
**Comparison:** aligned banks with comparable gap extent.
**Reuse/admission:** `MC:bridge_small_gap`, `MC:crossing_cargo_return`.
New geometry and structural predicates; not merely more bridge blocks.

### F-S03: Build a usable shelter — Minecraft

**Goal/start:** complete a small specified shelter with a roof, open entrance and
usable interior from ample supplied mixed materials.
**Decision:** maintain access while building walls/roof and distinguish inside,
outside and required empty space.
**Evidence:** native block pattern, entrance/interior clearance and actual player
entry; no aesthetic judgment or reward for copying an internal blueprint.
**Comparison:** comparable wall/roof construction without interior-access demand.
**Reuse/admission:** `MC:mixed_material_shelter`.
Endpoint geometry is reusable; entry evidence and alternative accepted layouts
need explicit definitions. VM placement and ST reach stay native.

### F-S04: Reach the usable chest face — Minecraft

**Goal/start:** retrieve cargo from a chest inside an ordinary recessed alcove;
there is enough room and material to change approach.
**Decision:** find an interactable stance and aim, not merely minimize distance
to chest coordinates.
**Evidence:** real chest extraction and item possession; successful opening is
distinct from standing nearby.
**Comparison:** exposed chest with comparable travel and height.
**Reuse/admission:** `MC:open_chest`, `MC:take_supplies`.
Qualify native obstruction/reach behavior of the selected layout. ST can know
the chest position but still must reach and interact; exclude auto-navigation.

### F-S05: Retrieve supplies through cover — Minecraft

**Goal/start:** obtain a cache and return through a corridor exposed to a native
Skeleton, with cover and sufficient defensive supplies.
**Decision:** use occlusion and stance to limit exposure; killing is optional.
**Evidence:** cargo return, health/damage and exposed movement segments where
native evidence supports them.
**Comparison:** same threat and resources with changed cover geometry, plus a
no-threat diagnostic to separate combat execution.
**Reuse/admission:** `MC:ranged_cache_return`.
Keep normal enemy AI/loadout. Endpoint reuse is strong; causal cover analysis
needs more than final health. Neither track receives the scorer's sight rays.

### F-S06: Reach the correct elevation — Veloren

**Goal/start:** retrieve supplies from an elevated destination sharing horizontal
coordinates with a lower accessible position.
**Decision:** choose a climbable/stepped approach and finish at the actual height.
**Evidence:** three-dimensional position, grounded state and collected item,
not a two-dimensional proximity check.
**Comparison:** same-height access with a comparable horizontal route.
**Reuse/admission:** `VE:elevation_steps`, `VE:pickup_supplies`.
New placement/geometry variant; VM camera use and ST vertical coordinates differ
in assistance and are reported separately.

### F-S07: Carry cargo through alternating barriers — Veloren

**Goal/start:** collect a supply bundle and reach a destination beyond two
alternating ordinary walls.
**Decision:** plan successive turns and stopping positions without getting
trapped by the first apparent straight path.
**Evidence:** cargo and grounded arrival; collision/route inefficiency is secondary.
**Comparison:** comparable route with nonalternating openings.
**Reuse/admission:** `VE:staggered_detour`, `VE:pickup_supplies`.
No precise-seconds interpretation of `MoveTool`; no prescribed waypoint script.
This is related to F-S01, not an independent cognitive mechanism.

### F-S08: Land on a chosen terrace — Veloren

**Goal/start:** from a native elevated launch area, glide to a lower offset
terrace and finish on it.
**Decision:** choose launch direction and trajectory using height and clearance.
**Evidence:** actual airborne gliding followed by grounded landing in the zone;
walking there afterward is not a successful glide.
**Comparison:** generous aligned landing geometry, with the same native controls.
**Reuse/admission:** `VE:glide_and_land`.
Solo glide evidence exists; new launch/terrain feasibility is unqualified.
Separate this geometry contrast from the timing contrast in F-T09.

### F-S09: Work at an obstructed crafting station — Veloren

**Goal/start:** process supplied hide into leather at a native tanning rack
partially enclosed by ordinary terrain.
**Decision:** find a valid station-relative position rather than repeatedly
submitting a recipe from an inaccessible or wrong-height location.
**Evidence:** native crafted output and valid station interaction context.
**Comparison:** the same station and recipe in open space.
**Reuse/admission:** `VE:craft_equip`.
Qualify the actual native station distance/obstruction rules; do not invent
line-of-sight restrictions that crafting does not enforce.

### F-S10: Fight around a pillar — Veloren

**Goal/start:** defeat one ordinary melee opponent in an arena with a pillar,
with plentiful recovery resources and known equipment.
**Decision:** use reach, facing and collision to establish a valid attack position.
**Evidence:** identity-bound native defeat and damage events; attempted attacks
are not successful hits.
**Comparison:** the same opponent/loadout without the pillar.
**Reuse/admission:** `VE:defeat_legoom`, `VE:dual_legoom`.
New geometry, native encounter binding and paired-condition acceptance needed.
ST attacks must not auto-track or navigate; VM is not required to use absent keys.

## 4. Planning and resource management

Primary metadata proposal: `planning_resources`.
Prefer known goals/routes and generous wall-clock margins where possible.

### F-P01: Share fuel across workshop outputs — Minecraft

**Goal/start:** produce an iron pickaxe, shield and cooked food while retaining
declared expedition supplies from a shared small material/fuel stock.
**Decision:** allocate logs, planks and coal across crafting and furnace jobs.
**Evidence:** joint final outputs/reserves, with actual replenishment and fuel
loss reported rather than silently forbidden.
**Comparison:** identical production goals with plentiful fuel/materials.
**Reuse/admission:** `MC:shared_fuel_extraction`.
Use furnace slot primitives, not a supplied-smelt macro. Simplify its crossing
so spatial demands do not dominate the resource contrast.

### F-P02: Allocate wood between tools and a crossing — Minecraft

**Goal/start:** prepare a usable tool and bring cargo across a gap from a limited
wood stock, with legal but longer replenishment access.
**Decision:** spend planks on immediate access versus crafting and future repairs.
**Evidence:** joint tool/cargo/arrival result plus material expenditure and detours.
**Comparison:** plentiful wood in the same terrain.
**Reuse/admission:** `MC:craft_wooden_pickaxe`, `MC:crossing_cargo_return`.
Verify an actual feasible allocation and replenishment cost; never assume one
overused block makes the objective permanently impossible.

### F-P03: Reuse temporary building access — Minecraft

**Goal/start:** finish a small elevated permanent structure with limited spare
blocks available for temporary access.
**Decision:** recover and reposition scaffolding material rather than consume
all useful blocks as permanent access.
**Evidence:** valid final structure and material/access history where claimed;
successful alternative construction methods remain valid.
**Comparison:** ample spare access blocks with identical target geometry.
**Reuse/admission:** `MC:mixed_material_shelter`, `MC:place_single_block`.
New fixture must demonstrate a real access/material trade-off. Do not force a
specific pillar method or infer block reuse from final inventory alone.

### F-P04: Finance equipment and food — Minecraft

**Goal/start:** obtain an iron axe and a stated food supply from two ordinary
villager offers using limited initial coal/emeralds.
**Decision:** trade enough for both needs without spending all purchasing power
on the first attractive output.
**Evidence:** actual holdings and native trades if purchase provenance is required.
**Comparison:** sufficient initial emeralds, same offers and movement.
**Reuse/admission:** `MC:trade_outposts_return`, without its required combat.
Read actual prices/stock; preserve the selected native offers and disclosed
restocking conditions. Do not assign invented exchange rates.

### F-P05: Harvest, replant and divide the yield — Minecraft

**Goal/start:** manage a mature wheat plot, leaving it replanted while producing
bread and retaining the stated wheat delivery.
**Decision:** split outputs across food, delivery and continued cultivation.
**Evidence:** final planted crop cells and both item goals; no unsupported
per-plant provenance claim.
**Comparison:** extra wheat/seeds available without changing plot geometry.
**Reuse/admission:** `MC:farm_delivery`, `MC:harvest_and_replant`.
Account for native yield randomness and replenishment before fixing counts.
Do not score an impossible opening as an Agent's resource mistake.

### F-P06: Assemble a leather outfit — Veloren

**Goal/start:** make the required chest and boots from shared hides while
retaining replaced clothing.
**Decision:** distribute hides and intermediate leather across both recipes.
**Evidence:** complete outfit holdings/equipment under an explicit slot rule,
plus retained old items.
**Comparison:** surplus hides with identical stations and recipes.
**Reuse/admission:** `VE:leather_outfit`, `VE:craft_equip`.
Do not silently demand equipping unsupported slots; qualify native item-use
routes or keep the published goal to the supported holdings/equipment contract.

### F-P07: Cook while preserving raw supplies — Veloren

**Goal/start:** prepare a mushroom skewer while keeping raw mushroom, twig and
apple reserves from partial ingredients.
**Decision:** reserve ingredients instead of crafting every available recipe.
**Evidence:** native recipe state and joint final holdings.
**Comparison:** plentiful ingredients; keep supplies fresh enough that expiry
does not dominate this planning task.
**Reuse/admission:** `VE:food_reserve`.
Character recipe unlocking is not Agent learning. New balanced stock and
expiry conditions need verification in both tracks.

### F-P08: Buy knowledge without selling all recovery — Veloren

**Goal/start:** purchase and retain a Basic Equipment recipe collection, a coin
reserve and at least one potion from a limited potion inventory.
**Decision:** decide what to offer and retain through native trade phases.
**Evidence:** joint final book/coin/potion holdings; consuming the requested
retained book is not equivalent.
**Comparison:** extra purchasing resources, same merchant and offer.
**Reuse/admission:** `VE:merchant_exchange`.
Use actual native quotes and completion state; do not turn the tool into an
automatic fair-offer calculator or negotiation policy.

### F-P09: Budget a native skill loadout — Veloren

**Goal/start:** use a small disclosed Sword-point budget to unlock/configure a
specified eligible ability, then complete one short native encounter.
**Decision:** preserve points for prerequisites and choose a usable slot setup
instead of purchasing unrelated upgrades.
**Evidence:** native allocation/configuration and actual encounter outcome;
if ability use is required, its native activation needs separate evidence.
**Comparison:** prerequisites already purchased, with comparable remaining gear.
**Reuse/admission:** `VE:skill_hunt_return`.
Current two-point prerequisite/Defensive Riposte setup is prior art, not a
generic skill-tree optimizer. Skill progression is not Agent learning.

### F-P10: Provision two known encounters — Veloren

**Goal/start:** complete two short known encounters and return with finite
recovery stock and an optional resupply detour.
**Decision:** spend recovery early or preserve it, and decide whether the detour
is worthwhile before the second fight.
**Evidence:** both bound enemy outcomes, survival/return and supply use over time.
**Comparison:** generous recovery stock with the same enemies and terrain.
**Reuse/admission:** `VE:provisioned_hunt_return`, `VE:dual_legoom`.
Do not add stage healing/resets or assume the optional supplies are free.
Treat combat skill as a confound, not evidence that every failure is planning.

## 5. Real-time decision and execution

Primary metadata proposal: `realtime_execution`.
Use actual native pressure; do not manufacture difficulty by shortening a timeout.

### F-T01: Keep a hot furnace productive — Minecraft

**Goal/start:** finish a small mixed smelting order in a furnace already burning,
with inputs and fuel whose actual state is publicly inspectable.
**Decision:** change inputs and handle output before useful burning time is wasted.
**Evidence:** outputs, native fuel/progress history and additional fuel consumed.
**Comparison:** the same job with adequate spare fuel; added model delay is a
separate diagnostic, not a different main protocol.
**Reuse/admission:** `MC:shared_fuel_extraction`.
Qualify the opening burn state and use `InspectFurnaceTool`/`FurnaceClickTool`.
No complete-smelt macro or hidden exact timer supplied only to ST.

### F-T02: Defend and counter — Minecraft

**Goal/start:** survive and defeat a nearby ordinary attacker using supplied
shield, weapon and a known simple layout.
**Decision:** time native defense and return attacks without losing control.
**Evidence:** defeat, health loss and actual blocked damage/projectiles when
that mechanism is claimed, not just a use-item request.
**Comparison:** more initial separation with the same equipment and enemy,
plus separately reported latency interventions.
**Reuse/admission:** `MC:block_and_counter`.
Verify attack type and shield behavior of the selected opponent; new timing
analysis may need native events beyond endpoint health.

### F-T03: Pace attacks through the cooldown — Minecraft

**Goal/start:** defeat a normal opponent with a supplied weapon and adequate
health in an uncomplicated arena.
**Decision:** coordinate aim, approach and native attack cooldown instead of
issuing ineffective repeated attacks.
**Evidence:** actual damage/attack intervals, defeat and resource cost.
**Comparison:** controlled added inference delay on the same native fight;
do not modify cooldown rules to construct a contrast.
**Reuse/admission:** `MC:deal_damage`, `MC:two_outposts_return`.
Need native cooldown/damage timing evidence for the pacing claim. A kill alone
is gameplay success, not a validated timing score.

### F-T04: Finish a supply trip before night exposure — Minecraft

**Goal/start:** gather nearby supplies and reach an ordinary lit shelter while
the native daylight cycle approaches night.
**Decision:** choose collection order and when to abandon a risky extra detour.
**Evidence:** required supplies, shelter arrival and actual day/time/exposure;
late completion may still succeed but incur native risk.
**Comparison:** an otherwise matched earlier-day opening.
**Reuse/admission:** `MC:take_supplies`, `MC:restore_hunger` provide primitives.
New day-cycle fixture and light/spawn feasibility required; do not script instant
monsters at sunset or make an arbitrary timestamp the sole success condition.

### F-T05: Recover despawning cargo — Minecraft

**Goal/start:** recover two ordinary dropped supply batches with different
native ages and return with both.
**Decision:** prioritize the less accessible but shorter-lived batch.
**Evidence:** actual drop identities, opening lifetimes, pickups/expiry and cargo.
**Comparison:** fresh drops at the same locations.
**Reuse/admission:** `MC:take_supplies` supplies inventory/navigation components,
not a qualified aged-drop fixture. Native item age, chunk-loaded ticking and
pickup delay need new verification. Do not substitute wall-clock assumptions
for native despawn behavior or expose private exact ages only to one track.

### F-T06: Collect the expiring supply first — Veloren

**Goal/start:** retrieve aged cheese and newer apples from separated sites and
return with the required quantities.
**Decision:** trade route convenience against native remaining lifetime.
**Evidence:** actual opening ages/lifetimes, collection/expiry and final return.
**Comparison:** fresh cheese with otherwise equivalent geometry and stock.
**Reuse/admission:** `VE:expiring_supply_return`.
Its nominal aging period does not guarantee the opening remainder. Reject
invalid openings, preserve valid failures, and do not replenish expired drops.

### F-T07: Dodge and re-engage — Veloren

**Goal/start:** defeat an ordinary melee opponent with supplied equipment while
using native evasion opportunities.
**Decision:** avoid an attack and regain a useful fighting position without
wasting all energy.
**Evidence:** encounter outcome, health/energy and native attack/evasion timing.
**Comparison:** more initial warning distance, same opponent and abilities.
**Reuse/admission:** `VE:dodge_roll`, `VE:defeat_legoom`.
A roll command is not proof of a successful dodge. Native hit/roll-window
evidence is a measurement gap; do not invent an automatic dodge tool.

### F-T08: Recover during a safe window — Veloren

**Goal/start:** survive and finish one native encounter from reduced health with
plentiful ordinary recovery items and nearby usable cover.
**Decision:** choose when and where to recover while the opponent continues acting.
**Evidence:** actual item effect, health trajectory, opponent attacks and victory.
**Comparison:** more initial separation or safer initial cover, retaining native
healing rules and quantities.
**Reuse/admission:** `VE:recover_health`, `VE:combat_supply_return`.
Qualify the chosen food/potion effect; do not assume every healing item has a
cast-time or can be interrupted. No scripted healing penalty.

### F-T09: Correct a glide before overshooting — Veloren

**Goal/start:** land in a known zone after a native launch with a recoverable
initial heading that requires correction.
**Decision:** use timely feedback to turn or stow/control the glider before
overshoot; geometry is disclosed to reduce map discovery demands.
**Evidence:** actual glide, trajectory/corrections and valid landing.
**Comparison:** same flight with controlled additional inference delay, reported
separately, and a generous landing-zone diagnostic.
**Reuse/admission:** `VE:glide_and_land`.
Qualify correction feasibility and native timing; do not inject gusts or alter
flight physics. This shares a family with F-S08, not independent evidence.

### F-T10: Protect a companion from an approaching threat — Veloren

**Goal/start:** bring the original owned pet to safety while an ordinary wolf
can approach through a known native route.
**Decision:** intervene, fight, lead or use stay/follow before the pet is lost.
**Evidence:** original pet survival, native threat outcome and safe arrival.
**Comparison:** increased initial threat distance, not weakened AI or damage.
**Reuse/admission:** `VE:companion_hunt_return`.
Verify actual threat behavior and a viable opening; do not force aggro,
invulnerability or scripted death. Pet protection is not peer cooperation.

## 6. Information use and adaptation

Primary metadata proposal: `information_adaptation`.
Favor sufficient resources and ordinary pressure so missing information is salient.

### F-I01: Follow a native field note — Minecraft

**Goal/start:** use a readable native note to locate the correct cargo among
plausible cache destinations and return with it.
**Decision:** extract actionable information and distinguish the requested item
from nearby alternatives.
**Evidence:** correct cargo and destination; note exposure only if observable.
**Comparison:** the relevant location/item information supplied in the public goal.
**Reuse/admission:** `MC:follow_quarry_note`.
Its existing arrival score is not proof of reading. Keep clues genuinely
readable through admitted VM/ST channels and do not expose the answer privately.

### F-I02: Reuse a scouted return route — Minecraft

**Goal/start:** retrieve cargo beyond locally discoverable passage openings and
return through the same ordinary terrain.
**Decision:** retain useful outbound discoveries rather than repeat avoidable
search, while checking whether the chosen route remains usable.
**Evidence:** cargo return and revisits/route history.
**Comparison:** openings explicitly disclosed at the start.
**Reuse/admission:** `MC:scout_outposts_return_0`.
No guarantee that separate partitions share an opening. This is route memory,
not stable-rule learning; ST local geometry and navigation assistance must be
accounted for rather than pretending pixel-equivalent occlusion.

### F-I03: Find the missing loadout components — Minecraft

**Goal/start:** assemble a specified small expedition loadout from several
ordinary chests with initially undisclosed stock and ample total supplies.
**Decision:** inspect, compare with current inventory and redirect to the needed
source rather than repeatedly visiting a convenient empty source.
**Evidence:** complete loadout and inspection/collection history.
**Comparison:** public chest-stock list for the same world.
**Reuse/admission:** `MC:supply_loadout`, `MC:take_supplies`.
Chest contents remain subject to the admitted native inspection interface;
final holdings alone do not prove an efficient information strategy.

### F-I04: Diagnose a failed interaction — Minecraft

**Goal/start:** retrieve two supplies from ordinary interactions that require
correcting an initial bad stance or obstructed approach.
**Decision:** interpret native failure feedback, inspect context and change
position/aim instead of issuing an unchanged command.
**Evidence:** actual successful transfers and error-to-correction trajectory.
**Comparison:** valid initial stance and explicit access instructions.
**Reuse/admission:** `MC:open_chest`, `MC:take_supplies`.
No injected fake errors or hidden rule changes. This shares interaction
geometry with F-S04; the feedback/knowledge contrast is different, not the game rule.

### F-I05: Resume a partially completed furnace job — Minecraft

**Goal/start:** finish a known order whose furnace already contains some input,
output and residual progress, with sufficient spare fuel.
**Decision:** inspect what remains rather than restart or duplicate all work.
**Evidence:** correct outputs, native slot/progress state and duplicate expenditure.
**Comparison:** exact opening progress disclosed publicly.
**Reuse/admission:** `MC:shared_fuel_extraction`, `MC:cook_supplied_food`.
New opening-state/evidence fixture required; use slot-level operations, not
`SmeltItemTool`. Keep scarcity mild to distinguish this from F-P01/F-T01.

### F-I06: Ask a resident for workshop directions — Veloren

**Goal/start:** obtain actual native workshop directions from a moving resident
and reach the received marker.
**Decision:** identify relevant dialogue, preserve the directions and navigate
to the correct place rather than substitute an unrelated personal pin.
**Evidence:** native received workshop marker and arrival.
**Comparison:** target information supplied at opening, with the dialogue
requirement removed in that separate control.
**Reuse/admission:** `VE:workshop_directions`.
Existing solo marker scoring is strong prior art. A 2D marker does not establish
entering the workshop interior or interacting with a crafting station.

### F-I07: Verify a completed trade — Veloren

**Goal/start:** buy a recipe collection with ample purchasing resources, then
leave the merchant with the actual item.
**Decision:** distinguish proposed offers, Review and Complete, and verify what
was transferred before acting on an assumed purchase.
**Evidence:** actual completed native transaction and book possession.
**Comparison:** an explicit public explanation of the observed trade phase
sequence; do not auto-complete transactions for the Agent.
**Reuse/admission:** `VE:merchant_exchange`.
Current endpoint-only success does not prove transaction provenance. Add
evidence only if claimed; surplus funds distinguish this from F-P08.

### F-I08: Resolve a recipe's missing ingredients — Veloren

**Goal/start:** prepare a small food order from partial inventory and mixed
nearby ingredients, with plentiful total stock and known native recipe access.
**Decision:** compare actual requirements and holdings, collect missing items,
then verify that crafting succeeded.
**Evidence:** recipe/output state, inspected inventory and collection attempts.
**Comparison:** an explicit correct shopping list at opening.
**Reuse/admission:** `VE:food_reserve`, `VE:gather_food`.
Avoid a one-click pickup diagnostic: include multiple ingredient types and a
real revision opportunity. Recipe unlocking itself is not Agent learning.

### F-I09: Reacquire the designated opponent — Veloren

**Goal/start:** defeat a bound ordinary enemy that can move behind cover or
outside the current local observation range.
**Decision:** distinguish lost observation from death and use new observations
to resume the pursuit without attacking a lookalike.
**Evidence:** correct identity-bound death and search/reacquisition trajectory.
**Comparison:** open-layout engagement with the same opponent and initial stock.
**Reuse/admission:** `VE:combat_supply_return`, `VE:dual_legoom`.
Need robust lifecycle binding across observation gaps. The scorer's private
tracking cannot be exposed as an Agent locator or global enemy map.

### F-I10: Find and direct the original pet — Veloren

**Goal/start:** bring an owned pet to a destination among visually or spatially
plausible distractor animals, without an active predator.
**Decision:** verify ownership, actual stay/follow state and whether the correct
animal is moving as expected.
**Evidence:** original identity/ownership, native command state and arrival.
**Comparison:** no distractors plus disclosed initial command state.
**Reuse/admission:** `VE:companion_hunt_return`.
New benign layout/state verification needed. Do not score issuing `PetStayTool`
as completed following; keep threat out to distinguish F-T10.

## 7. Multi-Agent cooperation

Primary metadata proposal: `peer_cooperation`. Every card has two equal peers,
the same shared public goal, separate native characters and private histories.
Initial asymmetries are ordinary location, inventory or acquired information,
not artificial role permissions.

**Common comparison:** same two-player fixture and per-role budget with versus
without native text chat; also consider a separately declared shared-information
control. No-chat does not suppress visual coordination or ordinary item use.
Solo-versus-team is not a communication ablation. Outcomes matter, not message
counts, prescribed dialogue or equal work shares. Both broadcast and private
tells are available; neither must be used merely to earn a score.

### F-C01: Make tools from distributed materials — Minecraft

**Goal/start:** both players finish with the requested basic tool loadout;
ingredients are split between their ordinary starting inventories.
**Decision:** agree who crafts what and how to exchange materials/results.
**Evidence:** joint final holdings and native handoff/crafting provenance only
where the interpretation requires it.
**Comparison:** common team controls plus co-located accessible material stock.
**Reuse/admission:** `MC:craft_wooden_pickaxe`, native team endpoint composition.
**ST handoff hold:** general player drop/chest deposit is not qualified.
VM ordinary dropping also needs task acceptance and recipient evidence.

### F-C02: Build one shared shelter — Minecraft

**Goal/start:** complete one usable shelter from material stocks split across
two starting positions; each player can move/build freely.
**Decision:** divide construction, avoid overlapping work and keep shared access.
**Evidence:** one native structure with usable entrance/interior and team arrival.
**Comparison:** common team controls, keeping total material and distance fixed.
**Reuse/admission:** `MC:mixed_material_shelter`, team state composition.
No mandatory handoff: each can place its own materials. New shared-structure
binding/occupancy checks; no minimum blocks per person or hidden role lock.

### F-C03: Scout a crossing for the builder — Minecraft

**Goal/start:** move shared cargo across a gap when one starting location reveals
a useful approach and another is near the building stock.
**Decision:** communicate observed geometry and choose a workable plan before
wasting material, or legally reunite and inspect directly.
**Evidence:** cargo/team arrival and actual constructed access if claimed.
**Comparison:** common controls plus initially shared approach information.
**Reuse/admission:** `MC:bridge_small_gap`, team chat.
Place information beyond the other player's actual ST radius, not merely behind
a wall. No enforced scout/builder permissions; qualify geometry and team evidence.

### F-C04: Combine two field reports — Minecraft

**Goal/start:** recover the correct expedition cargo using two native readable
notes at separated locations, one naming the site and another its usable approach.
**Decision:** share complementary useful information and avoid redundant travel.
**Evidence:** correct cargo and team delivery; note access/communication is diagnostic.
**Comparison:** common controls plus both reports available at each starting site.
**Reuse/admission:** `MC:follow_quarry_note`, `MC:take_supplies`.
New grounded notes/readability/evidence; not an invented cipher, answer token
or communication-only artificial lock. Independent scouting remains legal.

### F-C05: Cover a cargo retrieval — Minecraft

**Goal/start:** retrieve supplies and return together through an ordinary
Skeleton-exposed approach, starting with useful separate cover/building equipment.
**Decision:** coordinate cover construction, threat handling and movement.
**Evidence:** cargo, both arrivals, native damage and any claimed cover effects.
**Comparison:** common team controls with the same enemy and total equipment.
**Reuse/admission:** `MC:ranged_cache_return`, peer lifecycle.
Do not assume a shield protects a teammate behind it or that aggro can be forced.
Native shared encounter and process evidence remain task-specific gaps.

### F-C06: Divide expiring supply recovery — Veloren

**Goal/start:** collect separated cheese/apple supplies with unequal native
lifetimes and reunite with the required team inventory.
**Decision:** allocate destinations and communicate completion or a needed handover
of responsibility before a supply expires.
**Evidence:** aggregate holdings, both arrivals and actual opening/pickup timing.
**Comparison:** common controls; a fresh-supply condition checks timing dependence.
**Reuse/admission:** `VE:expiring_supply_return`, team aggregate inventory.
No item handoff is required. New two-player openings and expiry feasibility
need qualification; native team snapshots are not atomic.

### F-C07: Relay resident directions — Veloren

**Goal/start:** deliver the team's supplied crafting materials to the workshop
identified by real native resident dialogue; players start nearer different
parts of the route.
**Decision:** share the received location and decide who should travel/deliver,
instead of both repeating the same conversation and journey.
**Evidence:** a team member's actual received marker and delivery/arrival by a
team member at that marker, with all actors alive at completion.
**Comparison:** common controls plus the received location supplied publicly.
**Reuse/admission:** `VE:workshop_directions`.
**Team marker hold:** current team scorer rejects marker predicates. No private
oracle location may replace native dialogue; no mandatory peer item handoff.

### F-C08: Share recovery with an injured peer — Veloren

**Goal/start:** bring both players to a safe rendezvous with specified recovered
health; one starts injured without recovery items and the other has supplies.
**Decision:** communicate need, arrange a native handoff and confirm actual use.
**Evidence:** donor-to-recipient transfer, recipient recovery and joint arrival.
**Comparison:** common controls plus equivalent recovery stock on both players.
**Reuse/admission:** `VE:recover_health`, native peers.
**Transfer hold in both profiles:** NPC trading does not qualify player trade,
invitation acceptance or dropping. If campfire recovery is a legal successful
alternative, accept it but do not label that trajectory item-sharing evidence.

### F-C09: Coordinate a native hunt — Veloren

**Goal/start:** defeat one ordinary bound opponent and return both players alive,
with usable nonexclusive equipment at separate starting positions.
**Decision:** coordinate approach, space, recovery and pressure without colliding
or assuming a scripted tank/healer role.
**Evidence:** native target death with team attribution and joint return.
**Comparison:** common team controls, not a different solo enemy/loadout.
**Reuse/admission:** `VE:dual_legoom`, peer lifecycle.
**Team encounter hold:** extend attribution beyond current state composition;
do not require equal damage fractions, fake aggro or unqualified teammate healing.

### F-C10: Reassign collection after discovering a blocked route — Veloren

**Goal/start:** recover two supply batches and reunite; an ordinary static
barrier makes one player's apparently convenient route a detour.
**Decision:** report the discovered access and reassign collection when another
player is better placed.
**Evidence:** joint cargo/arrival and route/assignment history if claimed.
**Comparison:** common controls plus full route information at opening.
**Reuse/admission:** `VE:staggered_detour`, `VE:pickup_supplies`.
The obstacle exists from the start; no surprise runtime map edit. Do not script
a mandatory reassignment if the original plan remains a good native solution.

## 8. Within-Episode learning and improvement

Primary metadata proposal: `within_episode_learning`.
**All ten are measurement candidates, not ten validated learning tests.**
They introduce related practice and changed-context application into one
continuous Episode. They require more than new endpoint YAMLs.

Shared rules for every F-L card:

1. Give an ordinary game objective with useful earlier opportunities and a
   later related but nonidentical application. Keep game rules stable. Do not
   invent a secret recipe, random control mapping or a changing damage law.
2. Preserve the Agent's normal within-Episode history and memory policy.
   No stage reset, forced healing, inventory restoration or benchmark-supplied
   strategy summary. Record when information becomes available and whether
   the Agent actually encounters the earlier opportunities.
3. Measure later proficiency separately from **experience benefit**. Already
   proficient Agents are not assigned zero merely for having no room to improve.
   Later success alone is not evidence that earlier experience caused it.
4. Proposed diagnostic controls vary relevant earlier opportunity versus an
   unrelated/equivalent-time opportunity, with comparable later resources,
   gear, health, layout distribution and world time. Controls are separate
   conditions/Episodes without memory transfer, not resets inside the scored
   trajectory. If matching is not credible, report an observational result
   or unavailable learning effect, not a causal score.
5. Include early failures and deaths in outcome reporting. Do not estimate
   improvement only among survivors or successful practices. Gear gains,
   easier later enemies, repeated coordinates, accumulating materials and
   extra deliberation time are explicit competing explanations.
6. Validate phase events and error/cost measures before admitting a learning
   claim. Endpoint-only completion can remain a proficiency result; it must
   not silently fill an unmeasured radar axis.

### F-L01: Calibrate stopping across delivery bays — Minecraft

**Goal/start:** move ordinary cargo between successive staging bays, with a later
bay rotated and approached from a new direction.
**Decision:** use earlier overshoot/collision feedback to choose better movement
bursts and stops, rather than replay identical coordinates.
**Evidence:** phase-bound stopping error, corrective moves and later delivery.
**Comparison:** shared learning controls with matched later approach geometry.
**Reuse/admission:** `MC:reach_nearby_point`, `MC:crossing_cargo_return`.
New multi-bay fixture and phase evidence; exclude navigation macros. Keep later
surface/gear comparable. Each track needs its own movement calibration analysis.

### F-L02: Transfer a placement approach to a rotated structure — Minecraft

**Goal/start:** complete a small earlier work section and a later rotated shelter
section using ordinary supplied materials.
**Decision:** reuse an effective stance/placement-order strategy in a changed
orientation rather than memorize one absolute block sequence.
**Evidence:** valid structures, unreachable attempts, obstruction corrections
and material waste by phase.
**Comparison:** shared controls with equal useful material at the application.
**Reuse/admission:** `MC:mixed_material_shelter`, `MC:place_single_block`.
New phase-aware construction evidence. Rotation alone does not prove transfer;
later geometry must not simply be easier.

### F-L03: Improve furnace batching on a new order — Minecraft

**Goal/start:** fulfill successive small workshop orders, with a later different
mix of known smeltable inputs and output quantities.
**Decision:** use earlier idle-burning or slot-management experience to improve
batch scheduling without receiving a recipe strategy from the benchmark.
**Evidence:** native fuel wasted, slot errors, outputs and order completion times.
**Comparison:** shared controls with comparable available fuel/progress at the
later order; inability to match these limits causal interpretation.
**Reuse/admission:** `MC:shared_fuel_extraction`.
Slot-level tools only; new order/phase events. Do not call simply accumulating
coal or learning a game recipe Agent improvement.

### F-L04: Transfer attack pacing between encounters — Minecraft

**Goal/start:** complete earlier and later native encounters with the same weapon
type, but a changed location and approach orientation.
**Decision:** use actual hit/cooldown feedback to improve later pacing and aim.
**Evidence:** attack/damage timing, ineffective attempts, health cost and later
encounter proficiency.
**Comparison:** shared controls; report earlier damage/weapon wear and target
differences rather than pretending phases have identical state.
**Reuse/admission:** `MC:two_outposts_return`, `MC:deal_damage`.
New native timing/phase evidence. Do not infer learning from defeating two
different enemies or from upgraded equipment.

### F-L05: Apply a better allocation strategy to a new commission — Minecraft

**Goal/start:** finish earlier and later workshop commissions that use overlapping
native materials for different known output mixes.
**Decision:** carry forward a planning method for reserving common inputs while
recomputing quantities for the new commission.
**Evidence:** phase-bound allocations, avoidable shortfalls/replenishment and
later joint output completion.
**Comparison:** shared controls with matched later starting resources and goal
information; scoring must distinguish stock accumulation from better choices.
**Reuse/admission:** `MC:shared_fuel_extraction`, `MC:supply_loadout`.
New feasible commissions and allocation evidence; no hidden recipe changes or
forced resource mistake. This is related to F-P01, not a new native mechanic.

### F-L06: Calibrate native movement bursts — Veloren

**Goal/start:** deliver supplies through successive stopping areas and a later
changed-orientation approach.
**Decision:** improve bounded movement commands using earlier actual displacement
and collision feedback.
**Evidence:** stopping errors, corrections and arrival by phase, including native
timestamps rather than assuming each client update is one fixed time unit.
**Comparison:** shared controls with comparable later terrain and equipment.
**Reuse/admission:** `VE:move_2_metres`, `VE:staggered_detour`.
New sequence and phase evidence. Cross-game analog of F-L01; do not count it as
an independent learning mechanism simply because units differ.

### F-L07: Transfer a landing strategy to new terrain — Veloren

**Goal/start:** traverse a route with earlier glide opportunities and a later
new launch/landing geometry reachable by ordinary continued travel.
**Decision:** reuse launch, steering and landing experience under changed spatial
conditions rather than fly to the same saved coordinate.
**Evidence:** native airborne/landing events, correction cost and later success.
**Comparison:** shared controls; account for travel time, health and starting
height rather than resetting the player between flights.
**Reuse/admission:** `VE:glide_and_land`.
New feasible connected route and phase evidence. Dangerous practice must not
produce a survivor-only apparent learning gain.

### F-L08: Transfer crafting-station approach — Veloren

**Goal/start:** process supplied materials at earlier stations and complete a
later job at a differently oriented or recessed station.
**Decision:** generalize successful interaction stance and validation behavior
from earlier native range errors.
**Evidence:** failed interaction attempts, corrections, crafted output and phase.
**Comparison:** shared controls with comparable recipe/material complexity.
**Reuse/admission:** `VE:craft_equip`, `VE:leather_outfit`.
Qualify actual station rules and new layout; no invented facing requirement.
Being near the second station or unlocking its recipe is not learning evidence.

### F-L09: Transfer trade verification to a new merchant — Veloren

**Goal/start:** make an earlier native purchase and a later different purchase
from another merchant, with adequate overall purchasing power.
**Decision:** reuse understanding of offer/review/completion while checking new
stock, prices and transaction identity.
**Evidence:** phase/transaction-bound premature completion errors, corrected
offers and actual later receipt.
**Comparison:** shared controls with equivalent later quote/resources.
**Reuse/admission:** `VE:merchant_exchange`.
Multiple-merchant fixture and native transaction evidence are not qualified
by the current single-merchant example. Memorizing one trade ID is not transfer.

### F-L10: Transfer combat spacing and energy management — Veloren

**Goal/start:** face related native melee encounters in changed terrain within
one continuous journey using unchanged equipment.
**Decision:** carry forward a better spacing/roll/attack policy while adapting
to the next position, without assuming identical attack timing.
**Evidence:** effective hits, wasted abilities, health/energy costs and later
encounter outcome by phase.
**Comparison:** shared controls; explicitly account for persistent damage,
experience/skill changes and opponent differences.
**Reuse/admission:** `VE:dual_legoom`, `VE:provisioned_hunt_return`.
New process evidence; do not count character skill gains or mere survival as
Agent learning. If confounds cannot be separated, learning gain stays unavailable.

## 9. Family overlap and a better-than-counting development plan

The requested sixty slots are useful for generating options. They are **not
sixty independent mechanisms**. Freeze task-family membership before scoring,
and do not reward a family more heavily because it appears under several labels.

| Related candidates | Shared mechanism | How their questions differ |
| --- | --- | --- |
| F-S04, F-I04, F-L02 | Native access/placement feedback | Geometry, current error correction, later changed-context application |
| F-P01, F-T01, F-I05, F-L03 | Furnace workflow | Resource allocation, action timing, unknown progress, experience benefit |
| F-P08, F-I07, F-L09 | Native trade | Budget, completion verification, transfer to a new transaction |
| F-S08, F-T09, F-L07 | Gliding | Geometry, correction timing, benefit from earlier practice |
| F-T10, F-I10, INT-VE-02 | Native pet behavior | Threat response, state/identity verification, complete acquisition journey |
| F-C05, F-C09, INT-MC-04, INT-VE-05 | Team encounter coordination | Bounded collaboration versus whole native defense/dungeon missions |

**Recommendation:** retain all seventy as a reviewed design pool, but implement
mechanism families together and qualify a smaller representative slice first.
Do not build 140 independent near-duplicate scenes. Shared code/fixtures can
serve related cards while preserving separate goals, conditions and evidence.
This is a development recommendation, not deletion of requested candidates.

Learning is the weakest **measurement** area, not proof of a missing memory
framework. F-C01/F-C08 expose real native transfer admission gaps; team markers
and encounter attribution require task-specific scoring. These should be visible
in planning rather than described as forty or sixty already-ready tasks.

Before selecting formal results, check:

- A natural goal and feasible opening for the pinned game/track.
- An actual mechanism-specific contrast, not only a new distance/count/name.
- No ST macro or privileged observation solving the primary challenge.
- Native evidence for every process claim, including phase and actor identity.
- Continuous-world lifecycle, legal recovery and actual pressure semantics.
- Human-readable public success conditions and versioned private evaluation.
- Bounded Baseline acceptance, with valid failures preserved and infrastructure
  failures separated; no run is authorized by this design document itself.

Difficulty and budget calibration follow task review. Do not trim or expand
tasks to achieve a preferred model ranking. Unqualified candidates remain
unqualified rather than contributing Agent zeros.

## 10. Source scope

This design reuses actual repository task definitions and interfaces at the
published base `3917b89`, with existing results retaining their original scope.
Relevant entry points:

- [Archived Minecraft task pool](../back/legacy-config-20261026/config/minecraft/tasks/structured_tools/)
  and [ST interface](../../game/minecraft/structured_tools/interface.py).
- [Archived Veloren task pool](../back/legacy-config-20261026/config/veloren/tasks/structured_tools/)
  and [ST interface](../../game/veloren/structured_tools/interface.py).
- [Minecraft state evaluator](../../game/minecraft/evaluators/state.py)
  and [Veloren endpoint evaluator](../../game/veloren/evaluators/endpoints.py).
- [Team lifecycle/evaluation](../../game/team.py),
  [native peer protocol](native_peer_team_v1.md) and
  [prior acceptance evidence](native_peer_team_acceptance.json).
- [Current six-dimensional design](current_design_en_20261026.md) and
  [integrated catalog/source ledger](integrated_task_catalog_10_20261026.md).

No source reference above proves the new contrast or learning claim. No game
mechanics, interface, task configuration, evaluator or prior run was changed
while producing this catalog.
