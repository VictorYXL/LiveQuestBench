# Ten integrated task candidates grounded in native game goals

**Date:** 2026-10-26. **Status:** design proposal, not executable task specifications.
**Chinese companion:** [Ten integrated tasks](integrated_task_catalog_10_zh_CN_20261026.md).
**Parent design:** [Six capability dimensions](current_design_en_20261026.md).

**Review status:** retained as a proposal, not an admitted replacement catalog.
Legacy runnable configurations have moved to the
[configuration archive](../back/legacy-config-20261026/README.md).

## 1. Scope and selection principles

The requested design worklist is sixty focused candidates, ten per capability
dimension, plus **ten integrated candidates**. This document supplies the latter;
it does not claim that either catalog has been implemented or qualified.
[The focused catalog](focused_task_catalog_60_20261026.md) completes the combined
70-objective worklist: 35 per game, targeting 140 VM/ST combinations.
Minecraft and Veloren contribute five candidates each as a proposed balance,
not a mandatory release quota. Eight candidates are solo; two explicitly use
two equal, independently running copies of the selected Agent/model.

Focused and integrated tasks are the two formal task categories. Basic controls
and transport checks remain supporting engineering diagnostics. There are no
manually assigned benchmark difficulty tiers. Former L4 is a useful intuition
for a coherent expedition, not a duration requirement or equivalence.

An integrated task should have a goal a player might pursue without our rubric.
Preparation must affect execution, and expenditure or route choices must affect
later options. A naturally required sequence is not a prescribed action script.
Do not add an unrelated delivery, enemy kill, minimum message count, or learning
phase merely to fill a capability checklist.

Recognition has three distinct meanings:

| Evidence | What it supports | What it does not support |
| --- | --- | --- |
| Minecraft native advancement | The game has a named, machine-recognized completion event | The advancement necessarily requires a long plan, or proves all advertised prerequisite actions |
| Veloren native quest settlement, ownership, equipment or boss outcome | A concrete native result exists for the proposed goal | Every such result has a named achievement badge or persistent dungeon-clear flag |
| Official feature descriptions and community guides | The activity is an established, recognizable part of play | A measured community consensus that this particular benchmark scenario is enjoyable or representative |

The cited sources establish native goals and documented play patterns, not a
player survey. We have not established a general Veloren achievement system.
None is required or assumed here.

## 2. Shared proposed Episode contract

These are reviewable task-design proposals, not changes to the current protocol.

- **Bound the starting chapter, not the available solutions.** Start at a
  meaningful progression point with ordinary equipment and reachable native
  prerequisites. Do not require every mission to begin with an empty inventory.
  Publish what earlier progression the fixture supplies.
- **Use native worlds and mechanics.** Select and snapshot suitable generated
  sites; preserve ordinary AI, damage, recipes, collision and spawn rules.
  Do not substitute a summoned arena boss for a claimed full dungeon expedition.
  Initial fixtures may select conditions, but must not manufacture scripted
  combat outcomes or assist after the measured opening.
- **Keep resources consequential without creating arbitrary reserves.** Supplies
  compete with preparation, travel and recovery. Allow ordinary gathering,
  trading, building, retreat and resupply. If these remove an assumed trade-off,
  revise that research claim rather than silently forbidding the solution.
- **Treat world time honestly.** Native enemies, projectiles, daylight, recovery
  and relevant processing continue during inference. Safe preparation is legal;
  do not force every moment to be dangerous. A global timeout alone does not
  establish real-time sensitivity.
- **Prefer native recovery over artificial permadeath.** Proposed main conditions
  allow ordinary death/respawn and its native costs within the same deadline,
  unless the public mission's protected target or objective is irreversibly
  lost. Report deaths separately. This choice requires review before YAMLs are
  written; existing no-death tasks and results remain unchanged.
- **Separate native victory from added expedition conditions.** A return,
  equipped set, surviving beneficiary or team rendezvous is explicit benchmark
  wording when the native achievement does not require it. Record both the
  native milestone and whole-mission success. Do not append a return to every
  task by habit.
- **Use episode-bound evidence.** Relevant advancements are initially incomplete.
  Bind actors, sites and targets privately; record the native trigger or state
  transition after the opening. A preexisting item, missing enemy, inventory
  delta or action receipt is not sufficient evidence of its claimed origin.
- **Do not fix a budget by intuition.** Each starting chapter needs later
  feasibility checks and bounded Baseline acceptance. Publish wall-clock and
  inference resources, including team totals. The dragon and full-set candidates
  may need substantial budgets; they are not promised short tasks.

The stage arrows below explain plausible dependencies. Agents see the goal,
starting situation and ordinary control documentation, not a mandatory walkthrough.
Named stage observations support analysis; no universal partial-credit weights
are proposed.

## 3. Candidate overview

S = spatial interaction; P = planning/resources; T = real-time execution;
I = information/adaptation; C = peer cooperation. These are expected demands,
not measured dimension scores.

| ID | Game / actors | Player-facing goal | Native anchor | Expected emphasis |
| --- | --- | --- | --- | --- |
| INT-MC-01 | Minecraft / 1 | Complete a first enchantment from a small survival base | Enchanter | P, S, I; T during exposure |
| INT-MC-02 | Minecraft / 1 | Return from the Nether and brew a fire-resistance potion | We Need to Go Deeper; Local Brewery | P, S, T, I |
| INT-MC-03 | Minecraft / 1 | Cure and protect a zombie villager | Zombie Doctor | P, T, S, I |
| INT-MC-04 | Minecraft / 2 | Prepare a village and win its raid together | Hero of the Village | C, P, T, S, I |
| INT-MC-05 | Minecraft / 1 | Prepare for and defeat the Ender Dragon | Free the End | P, T, S, I |
| INT-VE-01 | Veloren / 1 | Acquire and wear a complete steel armor set | Native equipment progression | P, I, S; T during exposure |
| INT-VE-02 | Veloren / 1 | Obtain a collar, tame a wild companion and bring it home | Native ownership and pet behavior | P, S, T, I |
| INT-VE-03 | Veloren / 1 | Accept, execute and collect payment for a monster contract | Native Slay quest and actual reward delivery | I, P, T, S |
| INT-VE-04 | Veloren / 1 | Prepare for a Gnarling expedition and defeat its Harvester | Native dungeon and boss death | P, T, S, I |
| INT-VE-05 | Veloren / 2 | Prepare together and defeat the Haniwa Gravewarden | Native dungeon and boss death | C, P, T, S, I |

Within-Episode learning is **not automatic credit** on this table. Raid waves
and dungeon encounters offer candidate experience/application sequences, but
progression, changing opponents and survivor selection confound improvement.
The focused learning tasks carry the primary controlled measurement. Integrated
trajectories can support exploratory learning analysis only with additional
evidence and appropriate comparisons.

## 4. Minecraft candidates

### INT-MC-01: First enchantment

**Goal and recognition.** Enchant an item through the native enchanting table,
earning `minecraft:story/enchant_item` (Enchanter). Merely obtaining an enchanted
item from a chest, villager or enemy does not satisfy that trigger. [M1, M2]

**Starting chapter.** A small survival base, basic tools and food; no enchanting
table, diamonds, lapis or stockpiled experience sufficient to complete the goal.
A selected ordinary world provides reachable mining, book-making and experience
sources. Exact stock, knowledge and resource distances are future fixture choices.

**Dependency and decisions.** Develop mining access -> obtain table materials,
lapis and experience -> choose what to enchant -> perform the enchantment.
Diamonds can buy immediate equipment or enable the table; food, light and
durability support exploration and the return to a work site. Lava, falls and
ordinary hostile encounters make poor preparation consequential. No particular
mining method, enchantment choice or bookshelf count is mandatory.

**Completion/evidence.** A fresh native enchantment advancement is the success
anchor. Resource acquisition, table availability and experience consumption are
diagnostic milestones, not required proof of one prescribed recipe path.
Do not describe advancement parent links as enforced prerequisites.

**Reuse and admission.** Reuse mining, placement, crafting, survival and inventory
handling. A native enchanting-screen observation/action surface is absent from
the inspected Minecraft ST interface; no proposed tool may choose enchantments
or run the preparation loop automatically. VM has ordinary GUI input but this
workflow is not qualified. Both tracks need native advancement evidence and a
new resource-world fixture.

**Interpretation guard.** If safe mining dominates and native exposure is
negligible, report this as a progression/planning task, not a strong latency
diagnostic. Prepared-material and reduced-exposure controls can test the claimed
dependency without replacing the main mission.

### INT-MC-02: Nether brewery

**Goal and recognition.** Enter the Nether during the Episode, return to the
Overworld, and obtain a fire-resistance potion through native brewing.
`minecraft:nether/brew_potion` (Local Brewery) is a native brewing milestone;
it does not itself establish a Nether visit, potion type or ingredient origin.
Those are explicit additional mission conditions. [M1, M3]

**Starting chapter.** A modest Overworld base, an unlit portal frame, ordinary
iron-tier survival equipment, empty brewing equipment and bottles. Nether
resources, finished potions and brewing fuel are not supplied. Select a world
with feasible native access to the required resources rather than an arbitrary
long-distance fortress search.

**Dependency and decisions.** Prepare food, blocks and combat supplies -> travel
through the Nether and acquire brewing resources -> preserve a return route ->
allocate blaze-derived resources and brew at base. Route marking, combat
avoidance and retreat are legal; a player need not kill every encountered enemy.

**Completion/evidence.** Episode-bound dimension visits and native brewing
evidence, plus a retained native fire-resistance potion in the Overworld.
Bind the brewing result to the process, not just to final possession: a bartered
finished potion alone must not satisfy the published brewing goal. Alternative
native ingredient acquisition remains legal.

**Reuse and admission.** Reuse movement, building, combat and inventory handling.
Nether generation/reset, portal transitions, dimension-aware ST coordinates and
observations, brewing UI primitives and potion evidence need qualification.
A successful existing Overworld expedition does not establish these features.
VM also needs actual portal/GUI acceptance, not only keyboard availability.

**Interpretation guard.** Do not manufacture an emergency countdown for a
resource expedition. Native combat and environmental risk supply pressure.
Starting with finished ingredients is a separate dependency diagnostic.

### INT-MC-03: Zombie doctor

**Goal and recognition.** Cure a zombie villager through native mechanics and
keep the converted villager alive at completion. The fresh
`minecraft:story/cure_zombie_villager` (Zombie Doctor) advancement is the native
anchor; surviving after conversion is an explicit beneficiary-protection
condition, not part of the advancement definition. [M1, M4]

**Starting chapter.** A village-edge survival base with basic shelter materials,
an ordinary brewing station and a verified resource route for the treatment.
An uncured native zombie villager is initially in a shaded, ordinary enclosure;
neither Weakness nor conversion is pre-applied. The player is not given a
ready-to-use complete treatment kit. Avoid a randomly vanishing or already
sun-exposed target that can make a valid opening impossible.

**Dependency and decisions.** Secure a safe treatment location -> acquire or
prepare Weakness delivery and a golden apple -> apply the treatment correctly ->
maintain protection until conversion completes. Spending gold elsewhere,
damaging the patient, exposing it to daylight or leaving a dangerous approach
open can undermine earlier work. Native safe containment is a valid solution;
we must not secretly breach it to force intervention.

**Completion/evidence.** Fresh cure trigger, identity-linked zombie-to-villager
conversion and survival of that beneficiary at completion. A missing zombie or
another nearby villager is not proof. The mission ends after confirmed cure and
survival; no arbitrary extra trade or delivery is appended.

**Reuse and admission.** Reuse ordinary building, item use and combat controls.
Qualify targeted item/projectile use, brewing where needed, entity conversion
identity and actual native conversion timing. ST brewing remains a gap;
VM GUI feasibility and both-track full mission acceptance remain unverified.

**Interpretation guard.** Successful early protection may make the waiting
period safe. This is good planning, not evidence of a defective task. Do not
claim unavoidable constant reaction pressure or that waiting itself is learning.

### INT-MC-04: Village defenders

**Goal and recognition.** Two peer Agents prepare and defend one village through
a native raid. Require native raid victory, a fresh Hero of the Village
advancement for at least one team member, and both players alive in the village
at completion. Team presence is our added expedition condition. [M1, M5, M7]

**Starting chapter.** A genuine village with claimed native points of interest,
living residents, ordinary supplies and two players at different local positions.
Both have usable equipment; neither has an artificial exclusive ability. There
is no active raid yet. The team prepares and triggers a raid by the pinned
version's ordinary rules. Minecraft 1.20.4 must not inherit the newer ominous
bottle/Raid Omen procedure from a current-version guide.

**Dependency and decisions.** Inspect vulnerable approaches -> allocate building,
equipment and food -> decide when to trigger the raid -> locate and respond to
successive waves -> recover and regroup. Players may scout, fortify, protect
residents or fight; no role script or per-player kill quota is imposed.
Information is private until conveyed through native chat or observed locally.

**Completion/evidence.** Bind the actual native raid to the village and Episode,
record its victory and qualifying player advancement, then confirm team presence
and survival. Do not mistake absence of nearby raiders, a removed bossbar or
unrelated status effects for victory. Resident losses and preparation costs are
reported separately; no extra "save every villager" condition is silently added.

**Reuse and admission.** Reuse native teams, broadcast/private chat, construction
and combat. Need raid/POI fixture validation, version-bound raid and advancement
evidence, and team event evaluation beyond existing endpoint composition.
Current communication success is not raid acceptance. No mandatory peer item
handoff is assumed; adding one would require the missing ST transfer primitive.

**Interpretation guard.** A strong Agent may do most fighting while its peer
fortifies. Judge shared success, not equal action counts. Compare matched
two-player chat/no-chat conditions with equal per-role budgets; no-chat still
permits visual coordination. Raid waves alone do not demonstrate learning.

### INT-MC-05: Free the End

**Goal and recognition.** Defeat the native Ender Dragon, earning the fresh
`minecraft:end/kill_dragon` (Free the End) advancement. This is a recognized
boss/progression objective, not a claim that Minecraft has only one ending.
The pinned advancement requires a player-attributed dragon kill. [M1, M6, M8]

**Starting chapter.** A survival outpost near a disclosed stronghold region,
ordinary iron-tier equipment, and accessible ingredients for completing the
remaining expedition preparations. The End portal is not yet activated and
the dragon is alive. Earlier progression, including the available portal
ingredients, is published; this is **not** a fresh-world, empty-inventory run.

**Dependency and decisions.** Inspect portal access -> choose and obtain sufficient
food, equipment, blocks and ammunition -> enter the End -> handle crystals,
movement and dragon attack opportunities -> complete the kill. Resource
decisions before entry constrain later recovery. Allow normal alternative
combat methods and routes; do not score a prescribed sequence of crystal kills.

**Completion/evidence.** Fresh native dragon-kill advancement and the identity-bound
dragon death in the correct world/dimension. The credits, return to the Overworld
and possession of the egg are not additional requirements. Their absence must
not invalidate the stated victory.

**Reuse and admission.** Reuse survival/combat/placement primitives, not a whole
dragon-fight macro. Stronghold and End fixtures, portal/item interactions,
dimension-aware observation, dragon multipart targeting and native attribution
need qualification in both tracks. This is a high-integration-cost candidate,
not an executable extension of the current arena.

**Interpretation guard.** Retain the iconic objective without promising that a
full world-to-dragon playthrough fits the existing budget. A pre-equipped End
fight is useful as a separate diagnostic but must not replace the integrated
preparation chapter under the same task version.

## 5. Veloren candidates

### INT-VE-01: Steel outfitter

**Goal and recognition.** Acquire and wear a complete native steel armor set.
The official site presents gathering, crafting and town equipment progression
as core play; the community wiki documents steel armor pieces. This is a native
equipment milestone, **not a named achievement**. [V1, V2, V3]

**Starting chapter.** A town, basic clothing and tools, limited trade resources,
and reachable native material sources. No steel pieces are supplied. Freeze
the exact set membership and item identities from the installed revision:
Minecraft's four armor slots must not be imported into Veloren.

**Dependency and decisions.** Discover recipes and material requirements ->
choose gathering, hunting, trading or legal loot opportunities -> process
materials where appropriate -> assemble and equip the set. Limited money can
buy armor inputs or recovery supplies; carrying capacity and terrain affect
collection choices. Do not demand hundreds of repetitions merely to lengthen
the task.

**Completion/evidence.** All declared steel-set pieces equipped simultaneously.
Crafting is an allowed route, not a hidden mandatory source requirement;
legitimate purchases and loot count. If later selecting a specifically
self-crafted variant, publish that distinct goal and add provenance evidence.

**Reuse and admission.** Existing leather crafting, recipe use and merchant
interfaces are useful components. The explicit ST `EquipTool` currently exposes
only `chest`; qualify all needed equipment operations, including any legitimate
`UseItemTool` route, before admitting this task. Mining, recipe availability,
stations, set evidence and VM inventory operations need native verification.
The live wiki's recipe quantities are not pinned-runtime specifications.

**Interpretation guard.** A complete set may be too acquisition-heavy for an
initial slice. Mark that cost honestly rather than silently reducing the set to
one chest piece while retaining the same title and score.

### INT-VE-02: First companion

**Goal and recognition.** Obtain a collar, tame an eligible wild animal and bring
the same living companion to the departure settlement. Taming companions is
explicitly advertised by Veloren and documented in its wiki. Ownership is a
native result; returning home is our explicit expedition endpoint. [V1, V2, V4]

**Starting chapter.** No pet or collar; ordinary starting equipment, modest
resources, available native collar acquisition routes and suitable neutral
wildlife in a reachable area. A designated home settlement is public. The Agent
may select among eligible animals rather than having to infer a hidden target.

**Dependency and decisions.** Learn how to obtain a collar -> budget crafting or
trade resources -> locate a tameable animal -> approach and tame it -> choose
a return route compatible with its movement and survival. Choosing an animal
or a difficult shortcut can affect the return, not just the taming click.

**Completion/evidence.** Native transition from unowned wildlife to player-owned
pet, with that same animal alive beside the player at the settlement endpoint.
No substitution by a pre-owned setup pet or a same-species lookalike.

**Reuse and admission.** Reuse crafting, item use and existing owned-pet
stay/follow handling. Current companion fixtures start with ownership already
established; they do not prove wild taming. Qualify collar acquisition/use,
eligibility, ownership transitions and following in both tracks.

**Interpretation guard.** This is **not peer cooperation**. Do not assume every
species follows well, can be mounted, or never teleports: the current guide
describes native catch-up behavior. Allow native catch-up under the stated
goal; do not claim continuous physical escort without separate evidence.
Collar recipes changed historically, so verify the pinned assets rather than
copying the current guide's ingredients.

### INT-VE-03: Paid monster contract

**Goal and recognition.** Accept a native Slay contract, prepare for and defeat
its designated monster after acceptance, then return to the giver and receive
the actual native reward. This uses existing native quest settlement, not a
benchmark-invented NPC success message. [L1]

**Starting chapter.** An existing settlement guard and native monster in a
selected feasible region; ordinary player equipment and limited discretionary
preparation resources. No preaccepted quest. Any initial funding of the giver
must be disclosed, as in the existing contract fixture.

**Dependency and decisions.** Read and accept the relevant offer -> identify the
target and plan preparation/travel -> fight or withdraw and resupply -> relocate
the moving giver -> complete reward dialogue and actual delivery. The proposed
integrated scenario adds consequential travel and preparation; it is not just
the existing courtyard with a longer timeout.

**Completion/evidence.** Preserve the current identity-bound chain: new quest,
correct giver/player/target, player contribution and death after acceptance,
native resolution and the matching reward insertion. A kill, disappearing quest
or coin increase alone is insufficient. No arbitrary return-to-start marker
is added beyond returning to the real giver.

**Reuse and admission.** `slay_contract.yaml`, `game/veloren/contracts.py` and
`game/veloren/evaluators/contract.py` provide strong reusable foundations.
The current evaluator also enforces no player death and a configured endpoint;
the shared recovery proposal would require an explicit task-version change,
not silent reuse of that rule. Longer-range native quest feasibility, moving
actor identity across loading boundaries and VM dialogue remain admission work.
Keep this candidate solo: existing team endpoint scoring does not confer native
shared quest ownership or reward eligibility.

**Interpretation guard.** This has stronger repository evidence than web evidence
for widespread community use. Do not describe contracts as Veloren's most popular
activity. Native randomized offers and moving actors must remain honest; do not
replace them with scripted guaranteed dialogue to simplify evaluation.

### INT-VE-04: Gnarling expedition

**Goal and recognition.** Prepare for a native Gnarling Fortress expedition,
defeat the Harvester in its pit, and return alive to a disclosed camp outside
the site. The wiki distinguishes the fortification's Gnarling Chieftain from
the pit's Harvester; defeating only the Chieftain is not the stated goal. [V1, V5]

**Starting chapter.** A nearby town/camp, a usable ordinary weapon and incomplete
expedition supplies; the selected native site and target boss are intact.
Publish starting skills, equipment and access information. Do not place the
player directly in a boss arena with a fully optimized loadout.

**Dependency and decisions.** Prepare supplies/equipment -> navigate the native
site -> manage encounters and retreat opportunities -> fight the Harvester ->
leave the site. Early damage and wasted recovery supplies affect later options;
site geometry and encounter information can change the chosen route.

**Completion/evidence.** Identity-bound native Harvester death attributable to
the player, followed by the public outside-camp endpoint. Return is our added
expedition condition. Loot is a secondary outcome, not a demand for a rare
random drop. There is no assumed persistent "dungeon cleared" flag, nor a
requirement to kill every respawning minion.

**Reuse and admission.** Reuse encounter evidence patterns, combat, recovery and
navigation. Existing spawned courtyard enemies do not establish dungeon
generation, reset, native boss binding or defeat feasibility. Qualify the
installed revision's site/boss pairing, normal loadout, loading/respawn behavior
and ST/VM observation/action reach. No AI or boss-health reduction is proposed.

**Interpretation guard.** Ordinary retreats are legitimate; endless restored
resources must not be assumed absent without checking. Native minion encounters
can support experience analysis, but success against a later different boss
does not prove transfer or improvement.

### INT-VE-05: Haniwa team expedition

**Goal and recognition.** Two peer Agents prepare together, defeat the native
Haniwa Catacomb Gravewarden and regroup alive outside the site. The community
dungeon guide identifies Gravewarden as the boss and recommends considering
groups for higher-difficulty native dungeons. Ancient Effigy is not identified
there as the final boss. The guide's native tier is not a benchmark level. [V5]

**Starting chapter.** Both players start near the same expedition base with
different local positions and ordinary configurable equipment/supplies, sharing
one goal. The actual Haniwa site is intact. Provide viable independent starting
inventories without making an unqualified peer item-transfer operation mandatory.

**Dependency and decisions.** Exchange local observations -> prepare and choose
a division of work -> navigate and coordinate encounters -> handle the boss ->
regroup. Separate views, target pressure, recovery windows and remaining
supplies can create useful coordination. No fixed tank/healer roles, guaranteed
aggro control, revival mechanic or exclusive access lock is assumed.

**Completion/evidence.** Correct native boss death with team attribution and both
actors alive at the public outside endpoint. Bind the team and boss over actor
lifecycles; do not count disappearance from one player's observation as death.
No arbitrary requirement that both deal a fixed damage fraction. Character
survival at the endpoint does not erase recorded deaths earlier in the Episode.

**Reuse and admission.** Native peers/chat are implemented; dungeon fixtures and
team encounter attribution are not qualified by those communication checks.
Current team evaluation rejects several solo event predicates and does not
provide this boss scorer automatically. VM also lacks the currently omitted
Alt/block input; do not require a parry-only solution when native rolling or
other admitted actions are available. Qualify the pinned boss/site, both tracks,
full expedition and two-player feasibility before admission.

**Interpretation guard.** Compare same-site, same-player-count chat/no-chat
conditions, not this task against the solo Gnarling task. A teammate can help
without chatting; success does not prove communication was necessary.
This and INT-VE-04 share the dungeon-expedition family and must not receive
artificially independent weight simply because the boss names differ.

## 6. Selection, evidence and remaining decisions

Ten candidates do not imply ten independent mechanisms or twenty supported
game/track combinations. Shared dependencies include brewing in INT-MC-02/03,
equipment economics in INT-MC-01/INT-VE-01, and dungeon preparation in
INT-VE-04/05. Group correlated families before aggregate reporting.

| Work item | Proposed treatment before implementation |
| --- | --- |
| Initial detailed fixture design | Start with INT-VE-03 and INT-VE-02 for substantial reuse; inspect a real Gnarling site for INT-VE-04 |
| Minecraft native-goal integration | Inspect INT-MC-01 and INT-MC-03 interfaces/evidence first; their recognizability does not imply current ST support |
| Shared-world team expansion | INT-MC-04 and INT-VE-05 need actual raid/boss evidence, not only chat and final inventories |
| Larger integration candidates | Keep INT-MC-02/05 and INT-VE-01 in the design pool; qualify dimensions, production interfaces and acquisition cost before scheduling |
| Recovery, site scope and budgets | Review the proposed respawn rule, starting chapters, return conditions and team sizes before writing configurations |
| Learning claims | Use focused controls first; integrated trajectories alone supply no causal learning score |
| Release choice | Select after feasibility and measurement review, not because a favorite model succeeds or because all ten slots must ship |

All candidates need per-track admission. Current code evidence identifies reuse,
not completed new workflows. No task YAML, evaluator, runtime, game mechanics,
model evaluation or cloud job was changed or started for this catalog.

## 7. Source ledger and evidence limits

Public pages were accessed for this design on 2026-10-26. The live wiki pages
are mutable and can differ from installed versions. The Minecraft JSON links
are **community-maintained extracted versioned game data**, not an official
Mojang repository; later admission must compare with the installed 1.20.4 jar.
Veloren site/item recipes and boss mappings likewise require the pinned source
and assets, not just the latest website.

- **M1:** [Minecraft Wiki: Advancement](https://minecraft.wiki/w/Advancement).
  Defines the native progression system and explains that parent advancements
  are not enforced prerequisites.
- **M2:** [1.20.4 Enchanter data](https://raw.githubusercontent.com/misode/mcmeta/1.20.4-data/data/minecraft/advancements/story/enchant_item.json).
  Trigger: `minecraft:enchanted_item`.
- **M3:** [1.20.4 Local Brewery data](https://raw.githubusercontent.com/misode/mcmeta/1.20.4-data/data/minecraft/advancements/nether/brew_potion.json).
  Trigger: `minecraft:brewed_potion`, without the extra expedition constraints.
- **M4:** [1.20.4 Zombie Doctor data](https://raw.githubusercontent.com/misode/mcmeta/1.20.4-data/data/minecraft/advancements/story/cure_zombie_villager.json).
  Trigger: `minecraft:cured_zombie_villager`.
- **M5:** [1.20.4 Hero of the Village data](https://raw.githubusercontent.com/misode/mcmeta/1.20.4-data/data/minecraft/advancements/adventure/hero_of_the_village.json).
  Trigger: `minecraft:hero_of_the_village`.
- **M6:** [1.20.4 Free the End data](https://raw.githubusercontent.com/misode/mcmeta/1.20.4-data/data/minecraft/advancements/end/kill_dragon.json).
  Player-killed-entity trigger constrained to `minecraft:ender_dragon`.
- **M7:** [Minecraft Wiki: Raid](https://minecraft.wiki/w/Raid).
  Native village defense and waves; the live page describes newer initiation
  rules and must not specify the pinned 1.20.4 setup.
- **M8:** [Community dragon guide](https://minecraft.wiki/w/Tutorial:Defeating_the_ender_dragon).
  Explicitly connects preparation, limited return options and boss combat.
- **V1:** [Veloren official site](https://veloren.net/).
  Explicitly presents town crafting, cave mining, native bosses, taming and
  multiplayer adventure as central activities.
- **V2:** [Veloren Wiki: Getting Started](https://wiki.veloren.net/wiki/Getting_Started).
  Describes equipment/skills progression, gathering, crafting, trade, combat
  and taming; also warns about pet pathfinding and native catch-up.
- **V3:** [Veloren Wiki: Steel Armor](https://wiki.veloren.net/wiki/Steel_Armor).
  Lists the native armor set and material routes. Do not import its current
  quantities or statistics without a source-version check.
- **V4:** [Veloren Wiki: Collar](https://wiki.veloren.net/wiki/Collar).
  Documents eligible wildlife, native collar use and historical recipe changes.
- **V5:** [Veloren Wiki: Dungeons](https://wiki.veloren.net/wiki/Dungeons).
  Gnarling fortification/pit and Haniwa boss identities; supplies and group-play
  guidance. This verifies a documented activity, not a quantified consensus.
- **L1:** Repository evidence at `3917b89`:
  [archived contract task](../back/legacy-config-20261026/config/veloren/tasks/structured_tools/slay_contract.yaml),
  [native preparation](../../game/veloren/contracts.py),
  [identity-bound evaluator](../../game/veloren/evaluators/contract.py).
  The existing fixture relocates real actors and funds the giver before play;
  it is not proof of a natural long-distance integrated contract run.
- **L2:** Current interfaces and team limitations:
  [Minecraft ST](../../game/minecraft/structured_tools/interface.py),
  [Veloren ST](../../game/veloren/structured_tools/interface.py),
  [team evaluator/lifecycle](../../game/team.py),
  [peer protocol](native_peer_team_v1.md).

The search service was unavailable; accessible public pages and versioned data
were retrieved directly instead. Unavailable pages were not treated as evidence.
This is a targeted design-source review, not exhaustive community research or
independent runtime reproduction.
