# VE-L02 regeneration procedure transfer: implementation candidate

Status: **implemented for bounded readiness review, not admitted**. This is the
replacement for the pending VE-L02 slot, not a 61st task. Base is fresh main
`1e1a2aa37ffe0c9f03a52919c1b3e0169029d1e6`; existing glide/climb history and the
ledger remain untouched. No native game, model, install or build was run.

## Condition and learning claim

`regeneration_procedure_transfer` has paired ST/VM definitions. Three original
owned sheep start at 96%, 60%, 60% native health. Three original wolves have
55, 110, 110 HP. The player has the ordinary starter sceptre, rawhide chest,
100 HP, two minor potions and three apples. Within 2700 seconds, all wolves
must die with actual player contribution, each original sheep must survive,
remain owned/grouped, finish at least 90% healthy and receive actual
player-sourced Regeneration, and the living, never-dead player must stop at
the central arch. Untouched 96%-healthy practice sheep **fails**.

The southern small-deficit encounter offers experience of real primary damage
producing temporary combo and secondary spending that combo on a caster-centred
Group aura. Its retained procedure controls later action selection, preservation
of a charge source, and casting position for two differently elevated,
36m-separated beneficiaries. This is not a new enemy response-timing family or
simply harder triage. The changed beneficiary count, injury and geometry are the
application variation; no acquired information is a secret scorer variable.

Learning **2**, overall ST **2–3**, VM **3–4**, provisional/high uncertainty.
This adopts the accepted limited optional-reuse scope of VE-L03/L04/L05, not
their native evidence or an inflated primary score. No causal learning gain,
mandatory memory, forced practice order, required mistake, or population result
is claimed. Normal tooltips and cold competent execution remain legal.

In particular, herding the pets or a well-positioned late high-combo pulse may
reduce repeated casting. At some positions all three pets fit inside one aura.
These are real lawful alternatives, not forbidden shortcuts. Their prevalence
and effect on learning discrimination remain unmeasured. A fast scripted
component is not a baseline difficulty estimate.

## Implementation chain and compatibility

* `fixture.py`: optional role-keyed `companions` mapping, maximum three, mutually
  exclusive with the original singleton. Setup reuses `initialize_companion`,
  moves the owner to supported preparation positions, and applies ordinary
  native Stay before enemies/readiness. No post-begin grants, injury, regeneration
  or combo manipulation. Each reset builds new identities.
* Fractional initial injury is checked against native readback; the registry now
  records the **actual quantized native HP**, not the requested float. This is
  necessary for 96% injury to pass the unchanged exact opening-health checks.
* `runtime/worker.py`: each role has an original UID/entity-generation and
  client lifecycle binding; opening checks native ownership/Group/health.
  Terminal readback uses only the latest native bindings and exact original
  UID plus entity-generation. Missing/replaced identities never substitute.
  All measured native health/death events remain available to the scorer.
* `evaluators/encounter.py`: the existing singleton predicates are applied to
  every named pet, conjunctively. Each requires actual player/entity-sourced
  Group Regeneration, not RestingHeal, attempted input or another actor's heal.
  Any original pet death fails even if the terminal data looks healthy.
* `binding.py`: scored roles must exactly match prepared companion roles.
  The existing alive/minimum-zero/downed endpoint implementation and death
  metrics are unchanged. Existing singleton result structure is retained.

No native source, public projection, control tool, HUD, renderer or physics
changes. ST uses existing fixed tools and nearby-entity health/identity effects;
it does not receive a new combo oracle. VM uses actual frames and ordinary
bounded keys/mouse; native Stay/Follow remains available. No energy projection
was added. The original task definitions and source files were not overlaid.

## Exact supported-runtime/source bridge

Select the existing manifest explicitly with `LIVEQUEST_VELOREN_RUNTIME`:
`output/temp/task_development/veloren-route-v2-contact-fix/candidate-runtime.json`

Manifest SHA256:
`f90ca9a97e20a106e6d749368319cdd45243a2f902605e7797c6f8e3613c3793`.
Renderer SHA256:
`5141b9ac796d5e71f5ba999f910777d364480cfb2b0344731425e1a65d1c5878`.
Source inventory `source-manifest.json` SHA256:
`2b93892d262d632081f626dd683847359e41e45780d01c69f63088d2d7df2a7c`.
This is the supported artifact from
`docs/evidence/VE-C02-supported-main-admission-20261029.json`, not an implicit
qualification of the default runtime or an arbitrary rebuild.

The following actual source files matched that inventory exactly (paths are
relative to its `source/` directory):

| File | SHA256 |
|---|---|
| `common/src/states/basic_beam.rs` | `e0f14909aa71ff63bbd0a2cd8351e2eeb2b91082b2dee0efcd88d255a86e7864` |
| `common/src/states/basic_aura.rs` | `06c26fa37e4b79c249e604a5ecc5d29dc750d0debd24f04f369604c1ee1e455f` |
| `common/src/comp/ability.rs` | `e4a9e6e236a56b1f7e64a9f3badfd8a9147196cc375e6a7901bb38c5be24d405` |
| `common/src/comp/combo.rs` | `5797789f09f8bddf48f4ffc202d0e271055dcc560d3f897a0593c9ba523a9738` |
| `common/systems/src/aura.rs` | `50fa9a7b4ce5f11d155a157d7d66317dd158f58fbec0787d34dfd67f39457167` |
| `common/systems/src/stats.rs` | `5503d5dc29796852b127fad0def56664975a3156f2293711854983cc08c5d0dd` |
| `common/src/comp/inventory/item/tool.rs` | `e26540101ee74d115ca62281ec79a83008e3ac91b93b629cb261e332fb7567b0` |
| `common/src/comp/buff.rs` | `41f404fc6fde88b9e6317e46f0ad18420626c627d9ce45db6f993809adfa7e1b` |
| `common/src/comp/body/mod.rs` | `c612dc78e83c23cfdf323100b02efb1e56c8c9ad6616d3c242b459b951624ac2` |
| `common/src/comp/body/quadruped_small.rs` | `474da446a6474dce2e086df0cebf27472b96ab869317cb9581d515591e85c836` |
| `client/src/agent_protocol/mod.rs` | `6c987a59830fc5a7bcd48f616e252733bef6af6cd9319d32f409162880d31bfc` |
| `server/src/pet.rs` | `16c6534c798c57bf86ad5535a2b25486b6c8ab317c0116a4482eae4e9460738f` |
| `common/src/comp/group.rs` | `933dcc3a597a437fd4524fd5e511517875a01b879015d7836c5ca754e00901b4` |
| `server/src/cmd.rs` | `92d1e1352fd6eeae8260a9cbede790fec03a081cbbda66c2f69afe130d31ffbe` |
| `server/src/events/interaction.rs` | `8befeb6d3267c200448c2ff01b891148f231f2fe8aede9280f2536bd0e9ce908` |

`server::pet::tame_pet_internal` adds each spawned pet to its owner's Group via
`GroupManager::new_pet`. `aura::Sys` iterates all in-range recipients independently
and matches `AuraTarget::GroupOf`, not just one selected companion. Thus three
native pets and two simultaneous recipients do not need a new native API.

The build receipt points to actual assets
`/home/msra/GameAgent/velorenbench-auto-525af64d/assets/assets`. These were read
without modification and matched the inspected source-tree assets:

| Asset under that directory | SHA256 |
|---|---|
| `common/abilities/ability_set_manifest.ron` | `7d8b9a1188791ac371e22fa993fb6a02bde9b7848da8ae0bf6b41ac546542948` |
| `common/abilities/sceptre/healingaura.ron` | `81a36a21571e0a0c500d03d6bdf4f6faaeacfd859e50b7fbed6ff02e31b985f5` |
| `common/abilities/sceptre/lifestealbeam.ron` | `e05d07369436e84c2766c3f5687d43750700ba7184045725c52059ae53ac4c66` |
| `common/items/weapons/sceptre/starter_sceptre.ron` | `9b466b7c574e635429eb9dd2d1b7e53d0e0f512189786e56c932a074e1ab778d` |
| `common/entity/benchmark/male_wolf.ron` | `9c40d12de1ad5cce59055760a366501779fe0763d82725c70152aa062ef841c3` |

## Reachable construction and resources

The original proposal's long linear layout was compacted because the actual
unchanged ST `nearby_entities` radius is **32 m**. The implemented 64×48 floor
and dividers contain 5,308 authored solid voxels. All three pets begin inside
that public envelope and are also visible from the common terminal arch.
No global pet locator or relaxed visibility predicate was introduced.

The geometry regression checks native-profile player envelope radius 0.45 m,
height 7/3 m, and sheep envelope radius 0.6 m, height 1 m, with all footprint
support cells and full headroom. It checks each pet and pre-readiness owner
approach, both casting locations, initial position and terminal arch. A
supported ground-cell flood joins all enemy courts, both casting positions and
the arch without climbing or flight. A cardinal construction totals **70 m**
for start→practice cast→application cast→arch (23+41+6). This is not a measured
trajectory or a shortest-path requirement.

Practice cast `(18732.5,10803.5,501)` reaches the practice sheep but not either
application sheep. Application cast `(18732.5,10830.5,501)` has distances 18 m
and sqrt(328) ≈18.11 m to the two application sheep; starter range is
25×0.95=23.75 m. The terrace is two metres higher, with broad support and an
ordinary stepped approach. The three-metre setup approach also fits on it.
Native Stay is not a freeze; small setup following/displacement remains possible.
The casting margin and broad surfaces accommodate the approach-side movement,
but no all-behaviour positional guarantee is claimed.

Source-derived unskilled full-condition buff multiplier is
`0.45 + log_5(1.45) = 0.680865418`. Regeneration rate is
`0.4 × multiplier × sqrt(combo)`. Conservatively counting seven one-second
ticks from the eight-second buff gives 1.906 HP for combo1, exceeding the
practice deficit of about 1.2 HP. Two **non-overlapping** combo8 pulses give
10.784 HP per application sheep, exceeding each 9-HP deficit to the 90% goal.
They affect both recipients without doubling the 20-energy cast cost. Allow
the first buff to finish, then acquire fresh charge for the second; do not
assume overlapping buffs sum or that charge survives a long wait.

This construction needs 17 successful combo-producing hit increments and three
casts (60 energy before native regeneration). The starter's nominal 1.8 beam
damage per tick leaves ample finite enemy HP within the 275-HP supply; the
application alone has 220 HP, and primary damage also earns energy. Remaining
wolves still require lawful defeat. Injury from combat can require additional
healing and reduce this margin. No damage avoidance, nominal RPC timing, or
particular AI trajectory is guaranteed. Combat/luring remains a real live-world
consequence, not a scripted target dispenser.

The 7.5-second combo decay requires a timely legal primary→secondary switch,
not transporting charge along the whole route. Existing ST and VM native
healing evidence already exercises that switch. The short joined walking
construction, finite combat demand and multiple existing roughly minute-scale
healing/combat components leave a substantial 2700-second engineering margin;
they are not an empirical whole-episode bound on model reasoning latency.
Nominal continuous beam damage for 275 HP is about 51 native seconds before
aim loss, recovery and pursuit. Even a tenfold combat allowance plus 140 seconds
for 70m walking at only 0.5m/s, 120 seconds for separated healing/positioning,
and 1200 seconds for observations totals 1970 seconds. This is an explicit
constructive allowance, not a measured cold-baseline time or guarantee.

Dividers block initial direct routes/sightlines but have wide lawful entrances.
Wolves can pursue through them and can reach pets; no “wolf-proof pen” claim
is made. Preparation/readiness rejects injured or missing original actors.
Neither hostile AI nor regeneration through ordinary intervening solids was
changed; native aura membership uses 3D distance, without a terrain ray test.

## Focused validation and actual retained parity

Command, from the isolated worktree using the existing project environment:

```text
python -m pytest -q --tb=short -p no:cacheprovider
  --basetemp=output/checks/regeneration-tests
  tests/test_game/veloren/test_encounter.py
  tests/test_game/veloren/test_initialization.py
  tests/test_game/veloren/test_peer_support.py
  tests/test_game/veloren/test_evaluators.py
```

Result: **108 passed, 6 skipped**, 1.29 seconds. Skipped tests are native-gated;
none were enabled. New tests cover actual three-pet healing conjunction, the
untouched-96% counterexample, foreign/wrong-Group/wrong-generation healing,
terminal missing/replaced/underhealthy pets, original death despite healthy
terminal data, duplicate originals, quantized injury, pre-begin native Stay,
strict opening binding, both task bindings and body-sized geometry.

The existing initialization mock had not accounted for the already-present
player binding-cursor warm-up on fresh main; its local test stub now acknowledges
that read. No production warm-up behavior was changed.

Actual retained ST episode:
`output/temp/task_development/veloren-interaction/VE-R04-guided-injured-wolf-st/guided_reference/native_companion_triage.structured_tool/episode_1`

Replay using the current singleton task and fresh-base versus candidate scorer
gave **exact dictionary parity**, success true, preserving one recorded player
death under that existing task's `no_death: false`.

* Before observation SHA256: `02048b69eab1b72de7bf11dba94e81a364a974055522db333a132f0e8213f677`
* After observation SHA256: `be0d1a0a7484754cf9aedafe02c1ddc87fb088d93d177fa948718dc0193babef`
* Canonical score SHA256: `465165b2f031bdee8c4caf53e48573f73a1acb4ec9d5e4762952a88d223edc75`
* Unchanged death-metric SHA256: `321fc9d85ae7a09002b64735d4e1f0ae69bd62a36065a89b29984da901fab1eb`

This preserves existing evidence; it does not turn it into a new-task success.
Retained VM triage components include actual 12-HP sheep restoration and living
close return, while the corresponding wolf-death failure remains a failure.
C02 supplies separately accepted native Group-heal/combat composition evidence.

## Remaining bounded questions and diagnostic boundary

The new Python multi-pet preparation/registry path has unit tests and native
source support but no actual execution receipt. A reviewer may find that
constructive composition sufficient; if not, the only proposed native component
is one exact-runtime readiness/readback of three original grouped Stay pets,
followed by one ordinary charged pulse affecting both application recipients.
It would diagnose the new harness integration, not chase a whole win. **No such
run is authorized or scheduled by this packet.**

Exact setup/AI timing, application damage avoidance and baseline learning
discrimination remain uncertain. A temporary co-located/level-pet diagnostic
could isolate Group attribution, but cannot certify the final separated/elevated
condition or replace it. A more generous health/resource condition would likewise
be diagnostic only. This candidate claims neither exhaustive zero bugs nor
admission; the coherent source/test/constructive packet is ready for the existing
bounded reviewer.
