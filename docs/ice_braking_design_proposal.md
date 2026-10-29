# MC-L02: unchanged-rule stopping-policy transfer study

Status: **unadopted implementation/evidence proposal; learning remains blocked**.
The preserved no-practice five-second walk settles on the application pad in
9.799 seconds. That is a lawful counterpolicy, not an implementation failure.

## Historical minimal decision request

Ordinary same-scope design decisions are now delegated. The following original
options are retained as history, not a current permission blocker.

**L02-A:** authorize only the native trajectory observer and an unchanged-rule
paired practice/application prototype below. Keep the three 18-m practice lanes,
broad application turns, 4x4 pads, at most two application overshoots, native
friction, safe catches, and proposed 3/3 target. No model formal is authorized
until native parity and a preregistered matched contrast are ready.

**L02-B:** reject additional development of this mechanism and retain an unfilled
learning slot. Do not relabel motor competence as learning or replace the slot.

## Mechanism and concrete layout

Use three parallel packed-ice practice lanes at z=0, 10 and 20, each 18 blocks
long, with ordinary visible stopping bands and stone catch aprons. Application
uses two connected lanes with a broad right-angle approach and two 4x4 yellow
unloading pads. Preserve the approved broad geometry; do not shrink targets.
Select two held-out approach arrangements before running: long-then-short versus
short-then-long, with the turn mirrored. Record all block coordinates in the
fixture manifest and public route diagram before proof runs.

Concrete generator parameters for approval: floor y=71, four-block-wide
axis-aligned strips; practice strips x=0..17 with z starts 0,10,20.
Application A starts at (40,71,40), follows relative segments
`east 24, north 18, north 24, west 18`; application B swaps 24 and 18 and
mirrors north/south. A strip includes its starting cross-section and excludes
its final cross-section, which is the next segment's start. At bends, fill
the joining 4x4 square; do not make a one-cell precision corner. The last
four cross-sections of segments 2 and 4 are the two unloading pads. Surround
all strips by a three-block-wide nonlethal stone catch apron. Manifest both
variants before execution; these parameters are a proposal, not a change to
an existing scored fixture.

Two original cargo items originate in the practice-area chest. Deliver one to
each native pad chest and settle at each pad; no item is generated on success.
The reusable candidate procedure is **release/counter-steer as a function of
observed approach**, not remembering an absolute position or fixed duration.

## Public observation and action boundary

ST uses ordinary position, timestamps, blocks, inventory and bounded motor
actions. Speed can be inferred from consecutive observations; do not promise
a new privileged velocity field or exact-position pathfinding. VM uses ordinary
screenshots and motor inputs. All bands, application boundaries, catches and
chest targets are visible. Creeping, early release, stop-and-replan and walking
off the ice onto any reachable apron remain legal.

## Passive scorer and observer

- Fingerprint the original fixture/cargo manifest. Preserve original cargo
  lineage when checking the two destination chests.
- Record native game tick, player UUID, position, grounded state and motion at
  fixed native sampling intervals. The observer never moves/brakes the player.
- Proposed pad dwell is 20 consecutive native ticks grounded inside its 4x4
  footprint with native motion magnitude at most 0.1 blocks/tick (the existing
  settled-arrival speed convention). Publish this exact missing fixture detail
  before running; it is not an implemented score change or a tunable result.
- Define each overshoot by crossing that pad's visible downstream plane during
  its approach. Count once per actual outward crossing, re-arm only after a
  return to the approach side; remaining past the plane for many samples is
  one event, not many. Store crossing segments to expose sampling uncertainty.
- Score original deliveries, settled arrivals and at most **two** overshoots.
  Report application native ticks, reversals and overshoots separately; none
  creates an undisclosed speed threshold or changes the success budget.

## Native-feasibility proof and refutation

First prove legal cold walk, creeping, and release/counter-steer trajectories
on the *same* two application arrangements, in both action profiles. Preserve
public inputs and native before/after evidence. Test scorer boundaries offline:
one sustained excursion counts once; return/re-cross counts twice; wrong player
or original cargo does not score; practice crossings are excluded.

If cold walking succeeds with no overshoots and comparable application time,
**stop before model formals**: there is no useful procedure effect to establish.
Do not lengthen the map solely to tax creeping or add a minimum speed.

If native evidence leaves a plausible useful transfer question, use the same
application snapshot, equipment, position, time budget and public information
for retained-practice and history-erased conditions. Reset only permitted model
history, not physical rules. Run each held-out arrangement under both conditions
in ST and VM; preregister ordering and report every result, including cold wins.
Keep practice time separate and report total episode time as well.

The parent must choose a useful-effect criterion **before** that comparison.
Proposed decision rule: practiced play must preserve completion/overshoot
performance on both arrangements and improve application efficiency on both;
do not infer a 3/3 learning rating or population effect from a single pair.
A cold fixed-duration controller matching the benefit, or an erased condition
with less public application information, refutes the intended interpretation.

## Current bounded hidden-mechanism review

No additional native run is justified by the current unchanged goal:

- Concealing or varying ordinary ice friction does not remove the legal cold
  solution. Original deliveries and settled arrival have no minimum approach
  speed; slow control reduces the very inertia the proposed lesson concerns.
- A smaller pad, longer map, hidden speed floor or punitive deadline would
  manufacture a penalty for that policy, not demonstrate useful discovery.
- A native pressure-plate/comparator cargo lock could make an unknown physical
  condition discoverable. It would, however, add a separate lock-learning goal;
  it does not repair the claimed braking-transfer mechanism. This pass does not
  silently append such a lock and call the old task validated.
- Automatically launched, inaccessible cargo with an unknown native brake
  delay could prevent player creeping. It changes self-paced player braking
  into timed cargo interception and needs its own native objective and
  counterpolicy review; it is not an implemented minimal repair.

Therefore the present gap is construct validity, not missing permission or
failed execution. Preserve the9.799-second legal cold result, leave the learning
slot unqualified and schedule no unchanged application probes. This conclusion
is bounded to these concrete revisions, not a claim that native learning tasks
are impossible.

## Covered friction plus a real timed gate: source feasibility check

The newly requested physical premise **is supported** by the pinned1.20.4
native bytecode. Carpet has a1/16-block collision height. Native player movement
samples slipperiness at `floor(feetY - 0.500001)`, also when a supporting block is
known. Feet at72.0625 therefore sample the floor at71 below carpet at72.
Packed ice0.98 and blue ice0.989 are genuine registered slipperiness values;
no custom friction hook is needed.

An idealized flat native movement recurrence estimates18m traversal at85–95
ticks walking versus66–75 ticks sprinting on ordinary/packed/blue floors.
An ordinary80-tick piston-gate interval could therefore create an actual
movement constraint, unlike a private minimum-speed score. These are source
calculations, **not** a built gate, complete route or native timing witness;
trigger geometry, collision and legal jumping remain unverified.

The decisive paired-track limitation is information, not unsupported physics:
the existing public ST31×31×31 block cube exposes the underlying floor through
carpet. The bridge deliberately does not apply line-of-sight filtering.
Visually covering the floor consequently does not hide its identity on ST.
Changing that interface is not an allowed silent repair. A timed gate also
does not rule out a robust cold sprint/release or wall-stop solution.

Retain this physically supported hypothesis without building a complex fixture
or claiming paired hidden learning. A separately hidden ordinary native gate
interval could be a discoverable parameter, but that is a different versioned
mechanism and still needs the cold-controller objection resolved. Exact jar
hash, movement bytecode references and calculation assumptions are retained in
`output/temp/task_development/checks/MC-L02-covered-friction-source-review.json`.
No new native or model episode was consumed for this decisive source check.

## Next bounded native locomotion investigation

The covered-floor design is rejected, not awaiting permission. Public fields
must not be removed to rescue it.

Source inspection identifies a different, **unadopted** candidate: native
camel dash-response calibration. This is a versioned locomotion-mechanism
proposal, not a claim that the old ice-braking task is now valid. A complete
revision must retain both deliveries, the two broad4x4 pads, public overshoot
rules and safe catches; the small diagnostic does not implement that full goal.

- Current ST exposes nearby entity position, velocity and health, but not
  their movement-speed or jump-strength attributes. Observing motion can
  reveal a response; it does not directly disclose the hidden attribute.
  Player potion variants are not a substitute: current `InspectVitalsTool`
  exposes effect IDs and amplifiers.
- `MoveTool` and `JumpTool` are separate bounded key holds. Every completed
  action releases movement/jump/use keys. There is no ST simultaneous
  forward+jump or explicit dismount primitive. Horse mounting and vertical
  jumping are consequently plausible, but a running horse-jump course cannot
  assume a new key-chord permission.
- The pinned1.20.4 `CamelEntity.jump` supplies its own horizontal impulse
  along facing: `22.2222 * charge * native movement-speed attribute`.
  Its vertical impulse is
  `1.4285 * charge * (native jump-strength * block multiplier + jump boost)`.
  It does **not** condition this impulse on forward input. Ordinary existing
  use mounts an adult camel; the existing jump-key release protocol submits
  the charged native jump. No native hook or new tool is proposed.
- Vanilla camels normally have fixed default attributes. The two candidate
  values0.05/0.20 are **authored native movement-speed attributes**, not a
  claim about natural camel breeding variation. Jump strength remains0.42.
  Both values use the same public layout; the same individual retains its
  initial attributes throughout practice and application.
- `GoToPositionTool` is bounded standable-cell navigation with one-block
  steps, not gap-jump planning. It also targets the player's feet rather
  than a mounted vehicle's ground contact. It must not be assumed to provide
  a hidden calibrated dash controller.

`fixtures/camel_response.py` and `scripts/prove_camel_response.py` define one
small public ST diagnostic: one prior uniform instance selection, ordinary
mounting, a measured native dash on a safe practice floor, and at most two
marked-pad attempts across physical gaps using the measured response.
All initial commands occur while the game is ready/frozen; after `begin`,
control uses only public observation and ordinary existing tools.

The air gaps provide a physical reason walking cannot simply substitute for
a landing. This is still a hypothesis about the complete course, not an
exhaustive cold-policy exclusion. Full-charge launches, diagonal launches,
edge starts, mid-air correction, ordinary walking/sprinting, mounted settlement
and native dismount alternatives need honest review against actual evidence.
No hidden speed threshold, mandatory probe/failure, reduced pad or special
slow-walk penalty is introduced.

The diagnostic is not registered as a benchmark task. It does not claim
cargo delivery, an overshoot ledger, both-variant parity, VM feasibility or
learning qualification. Its retained result, including a failed mount,
alignment or landing, determines the next engineering decision; there is no
unchanged retry or model campaign.

## Bounded camel diagnostic closure

The corrected public ST diagnostic finished with a **valid first-pad landing
failure**, not full-task feasibility. The retained outputs are
`output/temp/task_development/MC-L02-camel-native-response-v1` and `-v2`;
the exact execution freeze is
`checks/MC-L02-camel-native-response-plan-v2.json` under that development root.

The first launch failed before public play: initial authoring removed the
player's supporting floor. Vanilla tick freeze does not freeze players; the
player fell into the catch, and initialization verification correctly rejected
the changed exhaustion. The corrected recipe preserves the initial support.
It reused the original private uniform draw, rather than selecting a condition
after an outcome. There were two native launches, one public-play episode,
zero model calls and no further retry.

In the corrected episode all55 public tool calls succeeded. Ordinary use
mounted the camel, and a0.50-second jump-key hold/release produced5.650819m
of settled displacement on the practice floor. The public controller selected
the same0.50-second charge and aligned to the application launch. After that
dash the public rider was at approximately(4.65,66.40,20.95), below and short
of the first pad, rather than on its surface. The episode ended after53.514
active seconds; no second-pad attempt or private recovery followed.

The retained native snapshots independently identify the same camel UUID
before and after, with movement speed0.05 and jump strength0.42 unchanged.
The terminal camel is grounded on the catch floor at(4.15,65,20.95), with
zero motion and full health; the player also retains full health. Mounted
client rider coordinates and saved entity coordinates differ, so neither
should be silently substituted for the other. The snapshot audit is retained
in `checks/MC-L02-camel-native-snapshot-audit.json`.

This closes the narrow uncertainty about whether existing public ST controls
can mount, produce and observe this native response without a new hook.
It does **not** close route feasibility or the learning construct. In
particular, settled flat-floor displacement is not an airborne landing-range
guarantee. The diagnostic's horizontal-footprint check is not a grounded/dwell
scorer and must not be used as one.

### Concrete next design decision, not an authorized rerun

If pursuing a versioned camel-calibration task, first derive feasible
charge/launch-position intervals for both native parameter values, including
the native minimum charge, camel collision box and mounted rider offset.
Consider shortening the physical gaps while retaining4x4 pads and safe
catches, or changing the authored parameter range if one instance cannot
land at any permitted charge. Those are prospective fixture revisions, not
retroactive reinterpretations of this failed course.

Reject any revised interval/layout combination admitting a common trivial
fixed charge/launch policy; review diagonal starts, mid-air correction,
ordinary movement and catches as lawful alternatives. No requirement to make
an initial mistake or mandatory probe is appropriate. A complete candidate
still needs the original three practice lanes, both cargo deliveries, native
grounded dwell/overshoot scoring, both-instance and VM witnesses, and honest
construct review. No causal-effect estimate or difficulty rating follows
from this diagnostic. MC-L02 remains unqualified; no further native or model
run is scheduled by this closure.

## New version: native courier response calibration

The subsequent engineering pass is explicitly a **new locomotion-calibration
proposal**, not retroactive qualification of the rejected ice task. Its target
remains within-episode identification and application of a native response.
There is no inherited3/3 rating or claimed causal learning benefit.

### Actual response difference

Two stratified native episodes applied the same public charge sequence on the
same flat floor. Their authored native movement speeds were0.05 and0.20; jump
strength remained0.42. A0.50-second input produced5.650819m and22.613622m
respectively, about a fourfold difference. A0.05-second input produced1.874970m
and7.511373m. The measured trajectories and other three charge settings are in
`checks/MC-L02-camel-actual-response-difference.json`.

Actual initial public entity records contained only ordinary identity, name,
type, display name, position, velocity and health. The attribute itself was not
exposed. Motion feedback remains lawful and useful; it is not suppressed.
These measurements establish a physical response difference, not that every
agent must learn or that a model has benefited from practice.

### Concrete native objective and course

`fixtures/camel_delivery.py` declares the common public goal: retrieve the two
original marked clay parcels from the depot furnace, deliver them to the
matching A/B furnace input slots, and finish alive with the original living
camel grounded and stopped on pad B. Dismounting is legal. Carrying parcels
alone does not complete the advertised courier-transport objective.

Three18m practice-lane markings precede the application corridor. Both
application pads are4x4, at x4..7 and x11..14, z20..23, with three-block
air gaps. Native water catches and a return stair permit recovery. The same
camel retains its native attributes through practice and application.
There is no mandatory probe, initial mistake, minimum speed, action ban or
private overshoot score. Unlike the old ice proposal, this version uses a
native cargo/original-courier endpoint goal, not an unimplemented temporal
overshoot ledger. It must be reviewed on those declared claims.

All interactions use existing native controls. Original parcel identity is
ordinary item NBT, preserved by native furnace UI transfers; the scorer reads
frozen saves. It compares the original camel UUID and checks native position,
grounded state, motion and health. There is no live task observer, custom
movement code, teleportation or after-begin authoring command.

### Retained engineering findings

- The first cargo-course attempt landed the lower-response camel on pad A,
  but its mounted rider moved when turning to aim, invalidating a single
  furnace aim. The fast camel also could not reliably satisfy an unnecessarily
  precise0.12m controller alignment. These were reference-controller problems,
  not unsupported native physics.
- The corrected controller uses broad safe launch bands and reacquires the
  furnace using existing public crosshair feedback. Both native ST instances
  then delivered both original parcels and finished with the same living,
  grounded camel on pad B. Frozen v2 source and exact replays are preserved.
- A fixed maximum-charge policy on the fast instance overshot into the catch;
  ordinary mounted walking on the slow instance fell into the catch. These
  refute those concrete universal policies, not every possible cold strategy.
- The full initial-block audit then found137 inherited grass blocks and621
  stone blocks in the preserved side strip. Grass was an unintended source
  of bridge material. Therefore v2 is **not** an eligible final fixture.
  Its native witnesses and counterchecks remain historical evidence.
- The v3 recipe clears only that unintended side terrain while preserving the
  live player's supporting floor and the intended recovery stair. An initial
  material audit now runs before public play and again in read-only scoring.
  This is initial-world admission, not a ban on legal mining or construction
  during play. The application pads, gaps, controls and parameter values are
  unchanged. Exact v3 native witnesses are required separately.

The first VM launch was owner-aborted after discovery of the material gap,
without a public motor action. Native begin completed during cancellation;
recording cleanup failed and no result JSON was emitted. Its retained log is
not represented as a valid VM witness or replayable final outcome.

Simple dismount-and-carry is insufficient under the public original-courier
goal, but dismounting, pushing/knockback, diagonal launches and mid-air control
remain legal strategies requiring honest counterpolicy review. Native witness
success alone cannot settle that review. The family has no model formals,
current-main admission or qualification claim in this engineering pass.

The exact v3 ST pair subsequently completed both deliveries and the original
courier endpoint:70.908s for the lower-response instance and35.631s for the
higher-response instance. Both immutable scores replay exactly; before/after
snapshots retain the original UUID and attributes. The full admitted initial
arena contains only air, water, bedrock, lane concrete, the two pad materials
and three furnaces. No inherited grass, dirt or stone remains. The receipt is
`checks/MC-L02-camel-delivery-native-audit-v3.json`. Eleven focused tests pass.
The corrected screenshot/motor-only VM pilot is a separate pending gate;
no VM success or family qualification is inferred from this ST pair.

### Same-episode policy acquisition correction (October 29 parallel worktree)

The recovered v2 and v3 delivery witnesses used a pre-calibrated lookup: a
half-second displacement threshold selected a known charge and two known
launch coordinates. That establishes legal execution, but does not establish
that these control parameters were acquired during the recorded episode.

The revised reference removes that table. It first measures a half-second
dash on the unchanged practice floor. If no safe launch predicts both public
landing bands, it measures a short reverse dash on the same floor. Only a
charge actually measured in this episode may be selected. Launch coordinates
are fitted continuously from those measurements and the public pad/support
geometry, with a half-block interior landing margin. No private instance
label, saved calibration file, mandatory failure or task-side probe requirement
is used. The second probe is conditional, not a task objective.

This is a reference-controller correction, not a new task condition. Native
attributes, blocks, cargo, endpoint scoring and legal actions remain unchanged.
Flat displacement remains an estimate of airborne range; native application
evidence must test that estimate rather than assume it. The bounded follow-up
targets the higher-response instance because it requires the newly measured
short charge. It is not a model comparison, difficulty calibration or proof
that every legal cold policy fails. Dismounting and pushing remain legal;
cargo-only delivery cannot satisfy the public original-courier endpoint.

The bounded check completed on source commit
`c418317d083eb1320775d7d25237a1e3c8e0eda4`, using the source-matched native
client and the unchanged v3 fixture. It is stored as
`MC-L02-camel-delivery-learned-i1-v4` under the development output root;
`v4` identifies the controller, not a fourth fixture condition. The measured
distances were22.613622m at0.50s and6.760236m at0.05s. The latter differs
from the earlier7.511373m diagnostic, so the resulting launch coordinates
(-0.760236 and6.239764) are not the old pre-calibrated answer. Both original
parcels and the living, grounded original camel reached their public goals
in39.066s, through54 successful public tool calls. Before/after manifests
(23 files each), unchanged UUID/attributes and the complete native score
were independently replayed offline. Thirteen focused tests pass.

This reference still has authored route/geometry knowledge; it is not an
unhinted agent measurement. Only the response calibration is acquired during
the episode. The result supports constructive ST feasibility and a concrete
same-episode acquisition/application procedure, not a causal model benefit,
universal shortcut exclusion or a numerical difficulty rating. The abandoned
VM v3 pilot has two motor batches but no final snapshot/result and a lease
return code of-15; it is neither a VM victory nor a scored task failure.
The handoff receipt is `checks/parallel-mc-learning-20261029.json` under the
development output root. No catalog, main branch or delivery ledger is changed.

### Substantive final-condition blocker: cold collision and delivery order

The follow-up did not stop at the acquired-policy success. Two sequential,
model-free checks on the **unchanged v3 fixture** establish a concrete lawful
alternative:

- `MC-L02-camel-bumper-i1-v1` used no response probe and one fixed0.50s dash
  along the furnace line. The high-response camel skipped A and stopped against
  B's furnace at(11.15,72,22.983), alive, grounded and stationary. The initial
  diagnostic expected A and stopped without delivering cargo, so this is a
  native courier-endpoint witness, **not** a full-task success.
- `MC-L02-camel-cold-courier-i0-v1` first delivered A from the supported
  pre-launch edge through ordinary native furnace interaction. The observed
  ray to the furnace's west face was3.900m, inside the existing4.5m limit.
  Without any response probe, two fixed0.50s dashes landed on A/B furnace tops.
  Walking off onto pad B and delivering B completed the unchanged full native
  goal in125.003s. All228 public calls succeeded. Furnace-top arrival is legal;
  the endpoint, not the reference's intermediate `on_pad` annotation, is scored.

Both scores replay exactly; all92 before/after manifest files verify, and the
original camel UUID and attributes persist. Native commands, goals, resources
and geometry match v3. The second check corrected the first diagnostic's
cargo-order omission in the other parameter stratum; no high-instance retry
or new condition was used.

The combined common policy is concrete: deliver A from the start edge, retreat
to the fixed launch, use maximum charge toward the existing furnace line,
repeat the same charge only if still at A, then deliver B. It branches on
current goal location, not a learned response model. For the high condition,
pre-launch A access has the same geometry/body dimensions/reach as the low
condition; an unfuelled clay transfer changes neither collision shape nor
camel physics. The native high endpoint then composes with the accessible B
transfer. This is a source-grounded constructive composition, not a claim that
the exact whole high cold controller was executed.

Therefore the final v3 condition remains **blocked for meaningful primary
learning fit**, despite genuine native response discovery being possible and
the learned controller genuinely succeeding. A slower cold reference is not
a causal learning-speed result: its navigation heuristics and bookkeeping
differ. No dismount, collision, ordinary walking or reachable UI interaction
is banned to rescue the claim.

VM is not merely labeled pending: the follow-up receipt records the preserved
native furnace screenshot, legal mouse/keyboard composition, observable block
grid/response contrast, native charge timing and launch margins, cargo/courier
joint resources, cooldown and1200s budget reasoning. There is no new VM
completion claim or universal particular-controller-victory gate. The same
physical cold-policy concern remains relevant to VM.

One exact **unadopted** repair option is a separately versioned flush-furnace
condition: move only destination furnaces from y72 to y71, replacing one
support block on each unchanged4x4 pad. This removes raised collision bumpers
without changing gaps, attributes, resources, action permissions or adding
probe requirements. Top-face UI access, pre-launch sightlines and airborne
feasibility change and need relevant checks; existing v3 wins would not
qualify it. This choice is presented for scoped approval, not silently
implemented. Alternatively retain v3 only as an unqualified control
diagnostic. Exact receipts and limits are in
`checks/parallel-mc-learning-substantive-gates-20261029.json` under the
development output root.

### Isolated flush-v4 source preparation, without a new native run

`game.minecraft.fixtures.camel_delivery_flush_v4` now provides a separate
versioned authoring/evaluation entry point. It changes exactly the two
destination `setblock` commands from y72 to y71; v3 remains unchanged and is
still the existing runner's default. The native evaluator accepts an explicit
destination tuple, with its v3 default preserved. Seventeen focused tests pass,
including unchanged full pads/gaps/catches and the isolated destination binding.
Five retained v3 native scores replay exactly after this parameterization.
No new native world, model call, canonical definition or admission is produced.

The causal claim is bounded. Low cold maximum-charge inputs landed on the
raised furnace tops; high cold input stopped at the B west face minus the
camel half-width. Native stepping/contact at A can also alter the trajectory.
The cold trace does not contain per-tick collision telemetry, so B is not
asserted to be the only causal contact. Flush receptacles form an ordinary
unobstructed loading deck and remove these raised supports/bumpers for all
controllers, while preserving normal collision and all legal strategies.

The old open-line response evidence explains a useful choice: broad interior
launches work with the longer measured pulse for the low response and the short
measured pulse for the high response. The existing successful open-line flights
do not intersect the changed z23 cells, so their airborne geometry transfers
without requiring another whole-controller victory. Top-face UI access is the
changed interaction. Geometry provides ordinary reach slack on the pad, but
native interaction has not yet been measured for this version.

Importantly, flush placement does **not** make pre-launch A delivery illegal:
aiming at the near top edge remains within the native4.5m reach. Also, a lawful
short diagonal hop from a supported camel overhang could bypass calibration.
One concrete fixed policy starts at(1.7,72,20.5), points along XZ unit vector
(0.94,0.341174), and uses0.05s. Flat traces project both responses into the
pad's body-support range, but low response must cross1.542553m before its feet
drop through deck height. The retained samples bracket, rather than resolve,
that contact. Its narrow support margins are not yet a robust cold witness,
and must not be dismissed by treating reference launch bands as action rules.

The requested next check is therefore **one low-response cold edge-hop/contact
diagnostic**, followed by ordinary flush-top UI access only if it lands, not
another adaptive success run. It is not queued. The exact evidence, response
table, causal limits, remaining alternatives and source-only handoff are in
`checks/parallel-mc-learning-flush-v4-proposal-20261029.json` under the development
output root. If a robust common cold route survives, stop this repair rather
than iteratively narrowing pads or outlawing legal control to force learning.

### Authorized flush-v4 contact diagnostic and version-bound runner

The single authorized `MC-L02-flush-v4-low-cold-support-v1` episode executed
clean source `33b9e78c0164b7d5899c4e59c3b90d0404d800cf` with the explicit
source-matched native runtime. It used the unchanged initial state, ordinary
mount/navigation, zero calibration probes and exactly one0.05s diagonal pulse.
Actual launch was(1.690859,72,20.494436), inside the predeclared band. All65
public calls succeeded; active play lasted58.854s.

This fixed hop **did not settle on A**. Public samples show(2.867854,72.015566)
in XY, followed by(3.009246,71.794077), then horizontal stopping at
x3.149999976 while descending. The endpoint was(3.149999976,65,21.299488).
The frozen native snapshot confirms the original living camel was grounded,
motionless on the catch floor, with unchanged attributes. This is actual
endpoint evidence, not rejection because the center was outside the displayed
pad. Public observations do not expose per-tick ground flags; no stronger
claim about every intermediate contact or possible legal recovery is made.
The conditional furnace-top UI branch was **not attempted**, not a UI failure.

All46 snapshot files verify. Native blocks compared with the retained low-v3
initial world differ at exactly the four declared furnace/floor cells.
Authoring commands equal the isolated v4 recipe; the unchanged full-goal score
replays exactly as false, as expected for this partial diagnostic. The lease
finished successfully, with no second episode, model call or queued retry.

The negative result rules out treating the proposed fixed launch/pulse as an
established robust cold route. It does not exclude other charge timing, nearer
overhangs, initial motion, in-flight controls, pushing or recovery. Nominal
short key holds remain tick-sensitive; historical flat settled distances
cannot replace native support evidence. No gap, pad, attribute, legal action
or scorer predicate was changed after this result.

The reference runner now accepts explicit
`--condition courier-v4-flush-destination-furnaces`, binding that version's
public goal, authoring commands, destination coordinates, top-face aiming and
native evaluator together. The default remains `courier-v3`. This follow-up
is runner plumbing, not another native execution or condition delta. Twenty
focused tests pass, including mocked end-to-end default/v4 binding and
top-surface targeting; a mocked UI is not native UI evidence.

Keep v3 unqualified for its preserved lawful cold composition. Keep v4
unadmitted, with fixed geometry, pending bounded construct review and the
unexercised native flush-top interaction. If additional execution is approved,
the smallest remaining interaction check is a separately labeled, simplified
initial-on-pad mounted top-face UI check, not another adaptive full victory.
It would establish UI plumbing only, not original-task learning or difficulty.
No such episode is currently authorized or queued. Existing VM composition
remains separate; lack of a full VM-controller victory is not the blocker.

The verified outcome, analytical limits, exact remaining decision and proposed
factual status reconciliation are in
`checks/parallel-mc-learning-flush-v4-native-closure-20261029.json`.
No canonical task, assessment ledger or admission count was changed.

### Corrected mounted flush-top UI and original-cargo transfer

The separately authorized simplified component check is now complete. The
first attempt stopped **before public play** because integer `tp` coordinates
were centered by native Minecraft and the driver assumed a fixed rider height.
Its46 snapshots and initialization-error result are preserved. It supplies
neither a native UI failure nor a success.

For the one approved corrected attempt, the exact external script and its diff
were archived before launch, independently of clean task source `7abd21d`.
The script hash is
`0a9c72ab9adefed70500eaa398516996f8b4fa772de7ef350367737a2895588d`.
Decimal coordinates produced the intended camel center(6,72,22). Native
`RootVehicle` attachment, original UUID/attributes, grounded zero motion and
all four body-support blocks were verified. The native animated rider position
was read only at the frozen initialization boundary; ordinary `PlayerState`
and canonical begin verification remained active. No readiness, collision,
reach, GUI or task geometry was changed.

`MC-L02-flush-v4-mounted-A-ui-transfer-v2` then completed eight successful
ordinary public actions in1.910s: aim at(5.5,71.99,23.5), open the native furnace,
pick the original A parcel from inventory slot3, place it in input0, close,
re-aim, reopen and stop. Native windows preserve the empty-input/held-item,
cursor, inserted-item and reopened states. The three frozen snapshots verify
the exact same original item payload, except its slot, moving
depot→player→A input; B remains at the depot. The original living camel remains
mounted and grounded on A. All69 manifest files verify, all compared native
blocks equal frozen v4, and the exact evaluator records A delivered while the
whole goal remains false.

This closes the **changed mounted A interaction and actual transfer** question,
not the original route: initial placement onto A was explicitly simplified.
B is a constructive composition, not an executed second delivery. Its furnace
is translated seven blocks east with identical native screen/slot behavior;
`NativeInventory` uses ordinary block interaction and `clickSlot`, without
destination or cargo-name special cases. From the retained actual standing
rider poses, the flush-top target distances are3.449/3.458m for low A/B and
3.522/3.496m for high A/B, within4.5m reach. The rays enter the exposed top near
its center. Retained low/high open-line flights remain physically clear of
the changed z23 cells. These source-backed unchanged segments plus the actual
changed interaction establish a reviewable lawful composition, not an
executed whole-v4 victory or a new VM result.

The handoff now combines this component evidence, preserved acquisition and
route evidence, independent provisional construct judgment and the bounded
cold-hop result. Legal alternatives remain legal; no universal cold exclusion,
mandatory probing or numerical learning/difficulty effect is asserted.
Independent admission review can judge the remaining gates without demanding
another particular-controller victory. Main integration, ledger reconciliation
and promotion remain separately scoped decisions.

Exact script/diff hashes, public/private receipts, composition boundaries,
prior failures and cleanup are in
`checks/parallel-mc-learning-flush-v4-ui-transfer-v2-closure-20261029.json`.
