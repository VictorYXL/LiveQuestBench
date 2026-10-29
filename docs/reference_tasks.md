# Initial twelve-task reference set

## Release scope

On October 28 the user selected a practical first-release target: **twelve
clear, reasonably challenging reference objectives for subsequent task design**,
not an exhaustive proof of six independent abilities or a frozen leaderboard.
The active catalog contains six objectives per game, with paired ST/VM
definitions: twelve objectives and twenty-four conditions.

This is a **development reference release**. Inclusion means the goal, native
mechanism, admitted interfaces and score are sufficiently specified to serve
as a reference, with the evidence limits below. It does not mean every condition
has a complete native success witness or statistically calibrated difficulty.
No existing failed result has been relabeled as success.

The four experiment examples under `config/{minecraft,veloren}/experiments/`
each select six objectives, one existing baseline and one repetition. They do
not launch automatically. Team objectives instantiate two peer Agents and must
be accounted for separately from single-player inference cost.

The [portable configuration and fixture manifest](reference_tasks_manifest.json)
records the frozen original definitions and file hashes. The
[compact learning evidence](evidence/learning.json) preserves
the reported native/model outcomes and their source-file hashes; large raw
journals are retained locally rather than embedded in this release.

### Veloren alive-contract revision 2

The separately versioned [migration record](evidence/veloren-alive-contract-v2.json)
pins the original and revised source hashes for all six Veloren objectives in
both tracks. Their public alive-only goals now explicitly use `min_health: 0`:
positive fractional native HP is allowed; zero HP, native dead and native downed
states are rejected. The shared implicit floor remains 1, and explicit health
reserves are unchanged. Team `all.min_health` also reaches the encounter owner's
health check and every participant's alive check; route scoring forwards its
explicit floor without changing route evidence requirements.

This is a new scoring source version, not a rewrite of the frozen manifest or
historical results. The native downed flag was previously not checked explicitly;
revision 2 rejects it even when HP is positive, including at the legacy floor.
Absent downed flags remain compatible with older snapshots; their absence does
not prove a native non-downed state. No original-six run has been demonstrated
to fail solely because of the old 1 HP floor. Offline tests and retained-endpoint
predicate replay do not requalify these changed conditions, relabel old verdicts,
or promote the 37 source-version qualifications to final readiness.

The [main-integration record](evidence/veloren-alive-contract-v2-integration.json)
separates the admitted revision from pre-existing, uncommitted contract-divider
experiments. Those local geometry/text changes are not frozen-reference changes.

## Goals and provisional difficulty

**2:** easier but substantive; **3:** standard; **4:** hard but useful as a
reference. These are engineering/design judgments informed by development
trajectories, not transformations of success rates. They are not the retired
L1/L2/L3 task hierarchy. Lower confidence is stated rather than hidden behind
a numeric label. The distribution is three category-2, seven category-3 and
fourteen category-4 conditions; VM remains the harder track.

| Game / objective | Primary dimension | Goal and substantive demand | ST | VM | Evidence boundary |
|---|---|---|---:|---:|---|
| Minecraft / `abandoned_mine_cargo` | Spatial | Recover three original cargo samples through elevated/lowered branches and return | 3 | 4 | ST completion; meaningful VM retrieval progress, weaker full-route VM support |
| Minecraft / `mining_workshop_restart` | Planning/resources | Prepare tools, obtain a diamond, deliver equipment/food and retain fuel/material reserves | 3 | 3 | ST completion; VM production/return with an omitted mining objective |
| Minecraft / `prepared_village_defense` | Real-time | Participate in and win a native raid, earn Hero of the Village and return | 4 | 4 | Complete native ST reference; VM primitives/partial combat, not a full VM victory witness |
| Minecraft / `expedition_record_reconstruction` | Information/adaptation | Use field information to recover three original records and return | 2 | 4 | ST clue/retrieval completion; VM partial retrieval; information attribution is not scored directly |
| Minecraft / `shared_crossing_camp` | Cooperation | Two peers build a crossing and shelter, retain food and reunite | 3 | 4 | ST team completion and actual division of work; VM crossing/food progress without shelter/reunion |
| Minecraft / `route_schema_transfer` | Within-episode learning | Discover cue-to-branch rules in practice and reuse them in reordered, rotated application wings | 3 | 4 | Public-ST history contrasts and a complete motor reference; narrow motor budget margin |
| Veloren / `mountain_workshop_circuit` | Spatial | Reach separated elevated workstations, craft/equip rawhide armor and return | 2 | 4 | Native full-route motor reference and concrete model crafting/equipment progress |
| Veloren / `self_funded_expedition` | Planning/resources | Prepare through crafting/trade, defeat two enemies, return with armor, potion and coin reserves | 3 | 4 | Preparation/trade/first-kill evidence; full-chain support is weaker, especially VM |
| Veloren / `hostile_route_supply_recovery` | Real-time | Secure leather while the supplied bundle is available, defeat two route enemies and deliver leather | 4 | 4 | Native pickup and combat progress; opportunity-loss pressure, not an identity-bound pickup deadline |
| Veloren / `native_contract_settlement` | Information/adaptation | Select the correct native Slay offer, defeat its target after acceptance, receive payment and return to giver | 4 | 4 | Lower-confidence design ratings: acceptance/contribution evidence, no inspected complete payment/return witness |
| Veloren / `coordinated_route_hunt` | Cooperation | Two peers coordinate two encounters and return alive; either player's damage counts | 2 | 4 | ST team completion; VM one kill and recovery failures; causal coordination advantage remains unmeasured |
| Veloren / `route_schema_transfer` | Within-episode learning | Acquire and reuse native architectural rules under an application travel allowance | 3 | 4 | Complete public-feedback ST witness; VM turn primitive verified, full-route VM witness not established |

All conditions keep the 2700-second episode cap. A fast authored controller
is not a realistic model-latency estimate. Difficult VM conditions should be
reported with their existing named stage checks, not only binary success.
Do not turn a count of unrelated private checks into a universal progress score.

## Changes made for this release

### Learning tasks

Both old learning definitions are replaced by `route_schema_transfer`.
The old Minecraft workshop permits upfront production batching, and the old
Veloren glide task primarily measures ordered flight proficiency. Their YAMLs
remain in Git history and local research archives. Regression inputs live in
`tests/fixtures/learning/`; historical runs and the prior acceptance review remain unchanged.

The new task has three niche patterns, an instance-specific continuing-side
mapping, an exploration wing and two application wings with reordered modules
and rotated headings. Vanilla movement, collision and ordinary controls remain
unchanged. The combined application allowance is **344 metres**; practice and
connecting stairs consume time but not that distance allowance. Native death
fails this particular task. Private trajectory evidence is not Agent input.

| Native reference | Application metres | Outcome |
|---|---:|---|
| Minecraft mapping 5, retain practice mapping | 331.591 | Pass |
| Minecraft mapping 5, erase practice mapping | 476.928 | Budget failure |
| Minecraft mapping 2, retain practice mapping | 331.394 | Pass |
| Minecraft mapping 2, erase practice mapping | 404.444 | Budget failure |
| Minecraft mapping 0, retain / erase | 330.622 / 330.697 | Both pass: lucky fixed preference |
| Minecraft supplied-route VM | 340.491 | Pass; only 3.509m below the allowance |
| Veloren mapping 5, public-feedback retained experience | 325.015 | Pass, all wings, zero deaths |

The two Minecraft model probes are valid failures, not infrastructure errors.
ST completed all wings in 882.505s but used 470.027 application metres.
VM completed its episode in 2695.034s without task success. These single
diagnostic episodes do not estimate a population difficulty distribution.

The failed Veloren motor reference assumed 314 X11 pixels produced 90 degrees.
A separate small-platform native diagnostic measured **157 pixels producing
90 degrees**, twice the source-constant-only prediction. The correction is in
the reference controller, not the game's controls. It explains the observed
180-degree turns back along the opening corridor. No complete corrected
Veloren VM run is claimed. The public control manual also discloses native
**G** for the equipped lantern.

These results support the task's relevance to acquiring and reusing experience.
They do not prove that learning is universally necessary or that a particular
Agent updates weights, improves its own implementation, or outperforms another
Agent on a learning axis. Per-episode `learning_benefit` remains `not_estimated`.

### Instance policy

The bundled Minecraft example uses mapping 2; Veloren uses mapping 5.
They are **public development examples**, not secret evaluation instances.
The reusable author generates any of eight mappings:

```bash
MINECRAFT_EULA_ACCEPTED=true PYTHONPATH=. .venv/bin/python -m game.route_transfer_author \
  --game minecraft --variant 5 --source-world config/minecraft/fixtures/abandoned_mine \
  --output output/temp/new-minecraft-route
PYTHONPATH=. .venv/bin/python -m game.route_transfer_author \
  --game veloren --variant 2 --source-world config/veloren/fixtures/veloren_0_18_0_0.bin \
  --output output/temp/new-veloren-route
```

Use a new output directory. The author records source hashes and does not
automatically qualify the output. Veloren needs the updated passive-route
renderer patch; follow `game/veloren/README.md` and use a separate build directory.
Native Veloren voxel initialization can take tens of minutes outside episode
time and produce large journals; do not confuse setup time with Agent difficulty.

A fixed mapping can be memorized. Absolute positions also correlate with
aggregate branch choices. Although local fork geometry is checked across all
eight mappings and all three wings, this is not an exhaustive shortcut proof.
No hidden-instance/random-origin evaluation policy was confirmed during this
release. Formal learning comparisons must predeclare a fresh instance
distribution and matched experience conditions instead of using these examples
as a secret test set.

### Recovery and goal/score alignment

The ST contract now matches the existing VM configuration: visible stone arch,
3000 giver funding for native offers, unchanged 1000-coin Slay reward, and an
initial native camp waypoint. Neither the contract nor a target kill is supplied.
NPC movement, retaliation, death and ordinary offer variation remain active.

Expedition, supply and peer-hunt fixtures now request an initial native waypoint
at each player's own start. This removes the unintended below-platform respawn
trap while preserving elapsed time, spent items, NPC outcomes and native
equipment consequences. It does not promise recovery after every possible
decision. Historical results used their original definitions and are not
exact-current-configuration runs.

Supply scoring already checks delivery of a new leather item, not pickup UID.
The public goal now says this explicitly and accepts another lawful leather
source. The pinned authored Green Legoom loot table contains plant/food/quest
items, not leather, so the required kills do not themselves supply the cargo.
Leaving to find an alternative source is not declared impossible or cheating.
This is an expiring convenient opportunity plus combat task, not a demonstrated
identity-bound hard-deadline diagnostic. No source attribution is inferred
from the inventory delta.

## Engineering checks and preservation

All twenty-four definitions pass binding admission; paired tasks share goals,
fixtures, participants, budgets and scoring. Offline regression checks cover
route geometry, observer boundaries/identity, native deaths, recovery setup,
existing scorers, team composition and runner behavior. The focused native
Rust library route-recording regression executes one test and passes.

Legacy regression inputs now live in `tests/fixtures/legacy/config` instead
of missing active L1/L2/L3 files. The obsolete Minecraft expedition test module
is archived because its implementation was retired in `31cf02c`; it is not
reported as passing. Passive block/damage helpers needed by the retained state
scorer are preserved independently of the retired world authors.

Only active authored Minecraft saves, the existing attributed Veloren map,
source code, task definitions and compact documentation/evidence are published.
Do not distribute native game executables, model credentials, runtime installs
or multi-gigabyte journals. Minecraft and Veloren retain distinct licensing
and setup requirements.

All `output/` contents are local and ignored, including research drafts,
temporary scripts, Azure credentials/configuration and experiment results.
Previously tracked historical material remains available in Git history and
in the local output directory. The current manifest reflects renamed fixture
paths; preserved learning outcomes describe their original recorded runs,
not new evaluations under the current checkout.

## Follow-up, not a claim of completed validation

### Separately admitted spatial additions (October 29)

The frozen twelve-reference experiments and their manifest remain unchanged.
Three further paired objectives are available as standalone task definitions:
`irrigation_reconnection`, `occluded_target_gallery`, and `ridge_glide_delivery`.
Their [integration manifest](evidence/spatial-task-integration.json) records exact
qualified source hashes and the distinction between native feasibility and formal
measurements. Irrigation's two final measurements succeeded; the gallery's ST
measurement failed despite completing its hits, while VM succeeded. Both glide
measurements are valid failures; separate guided native successes establish
feasibility, not model success. Glide retains the explicitly accepted ST2/VM2
engineering ratings.

All six definitions retain their qualified goals, fixtures, budgets and scoring.
Retained endpoints were replayed offline; no new native or model episode was
started. Glide uses independent `native-client-glide/1` evidence without enabling
route evidence. Main retains `native-client-route/2`; historical runtime provenance
is not rewritten or presented as a fresh qualification of a rebuilt binary.

The reference set is ready for further task development. The highest-value
next research checks are complete Veloren VM transfer and contract-chain
witnesses, representative difficulty repeats, and matched learning/cooperation
comparisons. Those limitations stay visible; this release does not manufacture
six statistically validated scores to close them.
