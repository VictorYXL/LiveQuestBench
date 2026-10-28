# Native route-schema transfer: learning-task revision

## Status and scope

**Subsequent release decision (2026-10-28):** the user selected a practical
twelve-objective reference release without requiring exhaustive empirical
validation. The active learning pairs have now been replaced; see the
[release scope and current limits](reference_tasks_release_20261028.md).
The development gates and candidate statements below retain their earlier
meaning and are not a claim that every gate was subsequently demonstrated.

This is a development candidate, not an accepted replacement in the released
24-condition suite. The user authorized replacing workshop/glide while preserving
native game mechanics. No active task definitions have yet been replaced.

The narrow target is **within-episode acquisition and compositional reuse of an
instance-specific architectural rule**. It is not proof of general self-evolution,
online weight updates, or modification of an Agent's implementation.

Three module types have one, two, or three shallow entrance niches. Each instance
assigns a continuing branch to each type. A practice wing permits exploration.
Two subsequent wings change module order and orientation but preserve these
assignments. Application travel, including backtracking, has a fixed allowance.
Practice and connecting stairs consume episode time but not application distance.
Native movement, collision, equipment, and controls remain unchanged.

## Candidate revisions and rejected shortcuts

The first candidate used straight branches and eight-metre spacing. Its successful
Minecraft ST reference established mechanical feasibility only. A regression test
subsequently demonstrated that the radius-15 public block cube could reveal
adjacent future corridors through walls, disclosing a branch choice prematurely.
That candidate is not an acceptable learning design.

The revised geometry uses 32-metre branches, eighteen-metre entrance stems, and
two-turn offsets before branch endings. Module order is `(0,1,2)`, `(2,0,1)`,
and `(1,2,0)` across successively rotated wings. Floors are separated by 32 metres.
Application centreline distance is 328 metres; the current allowance is 344 metres.
Local-observation regression cases compare all eight mappings at each practice
fork. These checks do not constitute an exhaustive proof against every policy or
viewpoint.

Minecraft corridors have two-block headroom and three-block stair headroom.
Native invisible light blocks illuminate them; solid structure is bedrock, including
gate floors, rather than breakable wool. The terminal chamber is visibly enlarged.

Veloren requires different clearance: a recorded native humanoid terrain AABB was
2.333333 metres high. Its revision therefore uses three-metre corridors and
four-metre stair headroom. The route-only authoring ceiling is 10,240 voxels;
other fixtures retain the existing 8,192-voxel ceiling.

The first Veloren initialization failed before play: voxel
`[18627,10936,437]` was native **Leaves**, not the required Air. The revised fixture
raises the starting floor from 501 to 701 metres. It retains the ordinary starter
glider: native starting equipment includes it, and the existing initializer does
not support silently removing undeclared equipment. Enclosure, not changed flight
physics, must prevent any glider shortcut.

## Completed native evidence

Artifacts are under
`output/temp/anchor-development-20261026/native-transfer-candidate-02/`.

| Mapping | Minecraft ST controller | Active seconds | Actions | Completed wings | Application metres | Result |
|---|---|---:|---:|---:|---:|---|
| 5 | Retain practice mapping | 205.400 | 291 | 3 | 331.591 | Pass |
| 5 | Erase practice mapping before application | 243.454 | 347 | 3 | 476.928 | Fail: travel budget |
| 2 | Retain practice mapping | 185.299 | 263 | 3 | 331.394 | Pass |
| 2 | Erase practice mapping before application | 205.080 | 291 | 3 | 404.444 | Fail: travel budget |
| 0 | Retain practice mapping | 166.650 | 235 | 3 | 330.622 | Pass |
| 0 | Erase practice mapping before application | 166.107 | 235 | 3 | 330.697 | Pass |

Mappings 5 and 2 are complements: each cue continues on each side once across
them. Mapping 0 is an intentional chance control: the controller's default branch
preference happens to be correct for every cue, so erasure does not prevent success.
All six runs finished alive at the terminal chamber with zero deaths.
The variant-2/0 artifacts are under `native-transfer-candidate-03/`.
The controller reads niche geometry and branch continuation from admitted
public observations; it receives no instance answer key during play. The ablation
clears only its learned mapping at the practice/application boundary. It can still
learn again during application, and did so.

The two informative pairs demonstrate a useful experience-retention effect **for
this controller and mappings 5/2**, while mapping 0 demonstrates chance success.
They are neither representative-model difficulty calibration nor a
population-level estimate of Agent learning differences. The per-episode scorer
therefore continues to report `learning_benefit.status: not_estimated`.

The initial Minecraft VM motor reference failed without completing a wing.
Post-episode diagnosis found that wall-following overshot a negative-side exit into
the next module's entrance niche. A second attempt completed practice but allotted
flat-ground movement time to descending stairs, desynchronizing its later turns.
Both failures are preserved.

The third Minecraft VM reference completed all three wings in **202.949 active
seconds**, with **340.491 application metres against 344**, zero deaths, and a
valid terminal state. It used admitted keyboard/mouse actions and actual screenshots,
with supplied route knowledge and no ST/native-state feedback during play.
This establishes VM mechanical feasibility, not visual learning or representative
Agent difficulty. Its small remaining travel margin is an explicit calibration
concern, not evidence that the final budget is already well tuned.

The corrected Veloren fixture initialized successfully. Its first complete ST
reference traversed all wings in **157.657 active seconds**, without deaths, but
failed with **399.094 application metres** and residual terminal speed **1.370m/s**.
Public feedback shows roughly 11.31m travel in long 30-tick actions, versus the
controller's assumed 7m, and repeated waypoint overshoots. It is a full traversal,
not a passing budget witness. A separate controller revision uses conservative
12m/s pacing and passive settling after released movement; it does not change
native physics, task geometry, or the allowance.

Veloren qualification uses a separate renderer build with opt-in passive route
evidence. The installed prior renderer was not replaced. The first focused Rust
command mistakenly targeted the binary and ran zero tests; the corrected library
target subsequently executed the named regression: **one test passed**.
A zero-test result is not recorded as regression coverage.

The corrected public-feedback Veloren ST retained-experience reference subsequently
passed in **144.800 active seconds**, with **325.015 application metres**, all three
wings, zero deaths, and a stationary terminal state. Its mapping came from admitted
local niche/continuation observations. This establishes one-instance feasibility
with experience use, not a matched-history learning effect for Veloren.

The Veloren VM supplied-route reference completed its action program in
**184.041 active seconds** but remained near the opening and completed **zero wings**.
It is a failed controller witness, not evidence that the route is impossible.
Artifacts for both are under `native-transfer-candidate-04/`.

The static Veloren VM manual now discloses native **G** for the equipped lantern,
verified in the pinned `voxygen/src/settings/control.rs` binding. The key was already
admitted; this is control disclosure, not a new skill or altered lighting mechanic.
It changes the shared VM prompt, so older Veloren prompt evidence is not silently
represented as an exact-current-prompt run.

## Reproducible authoring

The reusable author is `game.route_transfer_author`; it no longer depends on the
workshop or glide task definitions. Variant selection and source world are explicit.
It writes both track definitions, layout metadata, and author/layout source hashes.
Minecraft additionally preserves the submitted native construction commands and
receipts. Output directories must be new; existing evidence is not overwritten.

```bash
MINECRAFT_EULA_ACCEPTED=true PYTHONPATH=. .venv/bin/python -m game.route_transfer_author \
  --game minecraft --variant 5 --source-world config/minecraft/fixtures/abandoned_mine \
  --output output/temp/route-transfer-minecraft
PYTHONPATH=. .venv/bin/python -m game.route_transfer_author \
  --game veloren --variant 5 --source-world config/veloren/fixtures/veloren_0_18_0_0.bin \
  --output output/temp/route-transfer-veloren
```

These are development authoring examples, not a held-out evaluation distribution.
Fixed public mapping 5 alone must not be used to claim general within-episode
learning discrimination.

## Measurement and remaining acceptance gates

Minecraft uses a passive vanilla tick datapack with player UUID, position, game
time, observer hashes, continuous tick history, and snapshot-boundary checks.
Admission verifies actual native solids and walkable clearance against the scored
layout. Veloren records an opt-in private native-client position polyline and
checks actor/session identity, monotonic counters, preserved history, and opening
boundaries. Public observation projection does not include these private records.

The current candidate requires completion without death. Verified native death is
a game failure, not an infrastructure error caused by the subsequent respawn
displacement. Unexplained large sampling gaps remain measurement errors.

Before promotion:

- Establish complete native feasibility for Veloren ST/VM and qualify actual
  visual cue legibility separately from supplied-route execution.
- Expand the matched-history evidence beyond the current two informative mappings
  and one chance control before estimating distribution-level learning benefits.
- Inspect positional/layout correlations and practical probing shortcuts. Eight
  mappings alone do **not** justify claiming a universal 1/8 no-history success bound.
- Calibrate difficulty with bounded representative play. Script success alone
  does not establish a category-2/3/4 Agent difficulty judgment.
- Publish reproducible authoring/provenance, archive the superseded learning tasks,
  and only then update active mappings and commit/push the qualified replacement.

One existing Baseline/Astra episode per Minecraft track was scheduled on variant 2
under the unchanged 2700-second cap, credential leases, and development ledger.
There are no automatic retries or new Agent-learning components.

The ST probe completed in **882.505 active seconds**, with 85 successful model
requests and 84 tool calls. It reached all three wing endpoints and the terminal
chamber with zero deaths, but failed the application allowance:
**161.503 + 308.524 = 470.027 metres**, versus 344. Thus this failure is not a
navigation impossibility or a near-threshold movement correction: its first
application was efficient and its final application included substantial
backtracking. The transcript contains no intermediate explicit rule summaries,
so the failure is not attributed exclusively to memory rather than orientation,
cue identification, or decision errors. The visual probe also completed: valid
task failure after **2695.034 active seconds**. Its detailed failure attribution
has not yet been established.

## Bounded release closeout

The remaining work must not become an indefinite sequence of controller tuning
or a requirement to establish population-level statistical validity before a
first release. Keep engineering readiness, provisional difficulty, and empirical
capability discrimination separate.

1. Diagnose the completed Veloren VM opening failure from its recorded public
   frames/actions before launching another reference. Validate the specific
   control correction on recorded evidence or a bounded native primitive first.
   Complete the Veloren matched-history check and settle instance-distribution
   policy; fixed public mapping success is not general learning evidence.
2. Resolve the contract end-to-end bottleneck and the supply-source scoring gap
   using existing native evidence/code first. Inspect conditional feasibility
   claims for expedition, recovery and team tasks rather than assuming only
   the last three old difficulty labels matter.
3. Retain meaningful task-specific stage results alongside binary outcomes.
   Do not invent a unified partial-credit total or a six-axis ranking from
   unvalidated attribution.
4. Freeze an explicit per-condition acceptance table and publish only the
   supported scope. Any condition still blocked remains openly blocked;
   changing the promised 24-condition scope requires user approval.

No full model batch or repeated automatic retry is authorized by this closeout.
A failed targeted verification should trigger a documented defect/design decision,
not an unbounded search for a passing run. Statistical multi-Agent learning and
cooperation contrasts can follow an engineering release, but must remain labeled
unvalidated until actually measured. Commit/push remains conditional on the
user-requested validation and a review of the scoped dependency closure.

Focused checks passed, including geometry, native-evidence boundaries, and public
projection. Extending the checks to the existing Veloren lifecycle test exposed
an unrelated pre-existing fixture path: `tests/conftest.py` still loads
`config/veloren/tasks/structured_tools/move_2_metres.yaml`, which is absent from
both the current tree and HEAD following the prior task archival. That case has
not been silently treated as a passing check or repaired as part of this revision.
