# Native structure evaluation and endpoint-evaluator study

Date: 2026-10-22. Scope: implement Minecraft construction scoring, verify it
against actual native saves, and identify reusable endpoint predicates.
No model was invoked and no Agent capability result is claimed.

## 1. Source selection and implementation

Inspected local sources without changing their branches or worktrees:

| Source | Revision | Relevant evidence |
| --- | --- | --- |
| GameAgentVisual, `xianya/init_mincraft` | `696257de4ba7788f68026084b794d1265677f75b` | `benchmark/evaluator/world.py` reads native Anvil saves; `StructureEvaluator/evaluator.py` matches translated/rotated blueprints against before/after blocks |
| GameAgentResearch, `main` | `92b6d7f983dfe36929c851e8ae521a508cc60e82` | Structure evaluator consumes final nearby-block observations; `require_new_blocks` warns rather than enforcing a changed baseline at matched cells |

The native Visual design is the closer fit to LiveQuestBench's existing private
before/after world snapshots. Research contains an MIT license; no LICENSE or
COPYING file was found in the inspected Visual branch. The user's local-code
reuse request is recorded, but this is not evidence of an upstream MIT license
or a completed public-release licensing audit. Game assets/binaries remain
separate from benchmark source licensing.

Implemented:

- [Structure scorer](../../game/minecraft/evaluators/structure.py):
  `evaluate_structure(before, after, config)`.
- [Bounded Anvil reader](../../game/minecraft/evaluators/world.py):
  full requested-cell coverage, Java 1.20.4 palettes, negative coordinates,
  padded packed-long decoding and vanilla dimension paths.
- [Tests](../../tests/test_game/minecraft/test_structure.py):
  one consequential saved-evidence test and one actual native placement test.

Preserved: `[y][z][x]` blueprints, names/air/ignored cells, horizontal quarter-turn
invariance, translation, new-block checks, optional empty-space constraints,
recall/precision/IoU thresholds, extra target-material penalties and deterministic
best-match selection.

Intentional differences: the caller must declare an inclusive XYZ scoring region;
all requested cells must be readable in both saves. The upstream whole-save
intersection cannot establish coverage of unshared chunks. Local scoring avoids
unrelated world changes and never treats missing chunks as air. A 262,144-cell
region cap and a 5,000,000-comparison search cap raise explicit configuration/
resource errors rather than returning an incomplete best match.

This is a name-level blueprint evaluator, not a general building-quality,
functionality, collateral-damage or actor-attribution evaluator. Changes to other
materials are not penalized; ignored cells belong to the footprint. Existing
same-name blocks do not count as new, even if removed and replaced during play.
Only the Overworld has actual runtime qualification in this change; the
Nether/End paths and gzip/raw/external Anvil variants have not been live-tested.
See the [game README](../../game/minecraft/README.md#structure-evaluator) for the
complete public configuration and result semantics.

## 2. Validation and a runtime-discovered defect

Initial command:

```bash
LIVEQUEST_MINECRAFT_TEST=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft/test_structure.py \
  tests/test_game/minecraft/test_game.py -q -s --headless --recording
```

Outcome: **1 failed, 4 passed in 52.59 seconds**. Both native placement actions
succeeded, but the new reader rejected an acknowledged saved region because its
file size was not divisible by 4096. This was an implementation defect, not an
Agent/gameplay failure. The three existing lifecycle/inventory checks passed.

Inspection of the failed run's before/after region showed:

| Boundary | Region bytes | Remainder modulo 4096 | Requested payload complete |
| --- | ---: | ---: | --- |
| Before | 545382 | 614 | Yes |
| After | 549477 | 613 | Yes |

The reader now validates sector locations, payload length/allocation and actual
bytes read without requiring trailing sector padding. The regression test
truncates actual payload bytes, not optional trailing padding. This is also a
useful warning against taking the generic community region-format page's
padding statement as proof about a live, acknowledged save boundary.

Final construction command:

```bash
LIVEQUEST_MINECRAFT_TEST=1 \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_game/minecraft/test_structure.py -q -s --headless --recording
```

Outcome: **2 passed in 26.37 seconds**, no skips.

The final lean offline Minecraft suite (`-m 'not game'`) also passed:
**3 passed, 4 deselected in 0.29 seconds**. Local links in the changed usage
documentation and this report resolved. The dedicated Pylance syntax endpoint
could not locate the new file; Python/pytest parsed and executed it successfully,
and the LSP diagnostic endpoint returned no diagnostics.

The real case used ordinary native ST `PlaceTool` calls, not server commands
that fabricated a successful after state. The server was running between
`begin()` and `end()`:

- Two oak planks placed at `(1, 72, 0)` and `(1, 73, 0)`.
- Both native snapshots covered all 27 declared cells; exactly two changed.
- Matched 2/2; extras 0; air violations 0; recall/precision/IoU all 1.
- Before/before and after/after do not pass with new-block requirements.
- First-person video decoded with FFmpeg error checking.
- Pylance reported no diagnostics for the two implementation files and test file.

Artifacts (local generated outputs, not checkout prerequisites):

- Successful run: `output/test/minecraft-structure-0786f0fd1ea649b4a897c8ae3ad3b535/`.
- Initial failed run retained:
  `output/test/minecraft-structure-f729832b6d9549b7abd046cb859291e3/`.
- Existing lifecycle validation:
  `output/test/minecraft-game-554a9fbb08ea4a098b1a8f79ef9cd696/`.

The focused non-game case uses actual NBT/Anvil binary files, not a mocked world
reader. It exercises negative chunk/region coordinates, five-bit palette padding,
90-degree matching, disabled rotation, preexisting structures, missing target
cells, exact relaxed thresholds, extra materials, blocked air, read-only baseline
handling, truncated payloads and missing evidence elsewhere in the scoring region.
These counterexamples are not replaced by a single successful construction run.

## 3. Verified precedents

### MineDojo: inventory and event-counter deltas

Official [success predicates](https://github.com/MineDojo/MineDojo/blob/2731bc27394269643b43828d9db8ab3a364601f0/minedojo/tasks/meta/utils/success_criteria.py)
at revision `2731bc27394269643b43828d9db8ab3a364601f0` explicitly implement:

- current-minus-initial item quantities;
- current-minus-initial per-type entity kill statistics;
- current-minus-initial item-use statistics, with any/all target conditions;
- a time-since-death threshold.

The official [Harvest implementation](https://github.com/MineDojo/MineDojo/blob/2731bc27394269643b43828d9db8ab3a364601f0/minedojo/tasks/meta/harvest.py)
warns that fast resets do not reset statistics/achievements and callers must
compare against the reset baseline. These are source-verified examples, not
runtime reproduction of MineDojo or a claim that its older observation schema
matches Java 1.20.4 save files.

### BEHAVIOR: explicit final goal predicates

The official [evaluation rules](https://behavior.stanford.edu/challenge/evaluation.html),
retrieved on the date above, define partial success as the fraction of goal BDDL
predicates satisfied at Episode end. Efficiency metrics such as traveled distance
are separate. This supports using a small vocabulary of interpretable state
predicates rather than forcing every task through one visual similarity score.
It is a methodological precedent, not code/runtime compatibility with Minecraft.

### MineRL BASALT: the limit of endpoint geometry

Official [BASALT task documentation](https://minerl.readthedocs.io/en/latest/environments/basalt.html)
explicitly uses human judgment. Its tasks include village-style houses, attractive
waterfalls, animal pens and a no-damage restriction. A block blueprint alone does
not measure beauty, village style, a camera tour, or absence of transient damage.
Do not label our construction scorer as a reproduced BASALT evaluator.

## 4. Recommended endpoint evaluator families

Priority is an implementation recommendation, not an approved expansion plan.
Except inventory and name-level structure matching, the following are candidates,
not implemented evaluators.

| Priority | Family | Before/after evidence and example | Important limitation |
| --- | --- | --- | --- |
| Existing | Inventory/resource reserve | Player item counts; acquire target material and retain required supplies | A net gain does not prove mining/crafting; net consumption is not total spending |
| Existing | Blueprint construction | Region block-name differences; wall, cube, enclosure template | Does not prove mechanism function, safety, style or attribution |
| Next | Player-state goal | Saved dimension/position, health, food, XP, equipped slots, durability/enchants; finish at a delivery point with usable gear | Final health is not minimum health over time; item variants and slots need exact predicates |
| Next | Container delivery | Fixed container block entity ID/position and item quantities; deposit ingots into the designated chest | Validate both endpoint identities/coverage, double chests and container replacement; no proof of the item's origin |
| Next | Native statistics delta | UUID-specific saved counters for crafted/mined/used/killed/deaths; perform actions even if their products are later consumed | Need versioned counter semantics and reset/overflow checks; missing file is not zero; counters generally omit order |
| Next | Advancement transitions | Newly completed saved advancement/criterion; technology or exploration milestone | Start-state recipe unlocks already occur; player progress files differ from advancement definition JSON |
| Later | Region repair/clearing/preservation | Selected block predicates/deltas; clear debris, restore a bridge, leave protected blocks unchanged | Final equality cannot detect break-and-repair during the Episode |
| Later | Farming/block-state condition | Farmland, crop age, moisture, powered/open state at selected coordinates | Requires state properties beyond this name-only reader; a mature final crop does not prove harvest/replant |
| Later | Entity/relational goal | Stable entity UUID/type/owner/age/position; designated animals inside a pen | Must read saved entity regions and distinguish missing/unloaded/dead/despawned entities; mere bounding-box inclusion is not secure containment |

Do not immediately create an evaluator class for every item or task. Prefer small
reusable predicates, game-owned native readers, and explicit task parameters.
Avoid adding a generic query language or universal game ontology before concrete
tasks require it.

### Local persistence evidence for statistics

The failed initial construction run still produced complete before/after native
saves before scorer invocation. Both included `stats/<uuid>.json` and
`advancements/<uuid>.json`, with DataVersion 3700:

- Before statistics contained time counters and no `minecraft:used` entry.
- After statistics contained `minecraft:used: {"minecraft:oak_planks": 2}`.
- Both contained already-completed recipe advancements due to initial planks.

Thus this concrete save boundary persisted two actual placement-use events and
initial recipe progress. This does **not** qualify every statistic, death,
advancement, combat or reset scenario. A future statistics evaluator should
interpret an absent known key as zero only inside an otherwise valid, correctly
identified native statistics file; missing/corrupt files remain measurement errors.

The [Minecraft statistics reference](https://minecraft.wiki/w/Statistics)
documents the UUID JSON location and sparse counters. This is a community
technical reference; the exact 3700 persistence above was checked locally.
The [region format reference](https://minecraft.wiki/w/Region_file_format)
describes Anvil payload/compression layout; its general padding description was
insufficient for the current snapshot boundary, as the real test established.

## 5. Three evidence levels, not one "before/after" category

1. **Final-state predicates:** what is true at the end, optionally relative to
   the initial state: inventory, delivery, location, surviving structures.
2. **Persisted event summaries:** what happened during the interval according to
   authoritative cumulative statistics or advancement progress. Two snapshots
   can contain historical evidence without storing every frame.
3. **Trajectory/temporal constraints:** order, deadlines within phases, minimum
   health, exact time spent exposed, transient damage, and visit-then-return
   usually require events or periodic evidence. An explicit persisted custom
   milestone/state machine can sometimes summarize these, but that is additional
   instrumentation, not a property of ordinary final snapshots.

For example, a no-death condition can use a validated death-counter delta of zero
with identity/reset guarantees; it cannot be inferred from final health alone.
Likewise, a return coordinate cannot establish a prior visit without additional
milestone evidence. Kill counters are stronger attribution evidence than a
missing mob, but their native credit rules still need disclosure.

Recommended next sequence: **player-state predicates -> container delivery ->
native statistics deltas -> advancement transitions**. This would support
preparation/delivery/return tasks with resource constraints while keeping temporal
claims honest. Do not claim these predicates alone establish the benchmark's
cross-stage planning or continuous-real-time research hypothesis.
