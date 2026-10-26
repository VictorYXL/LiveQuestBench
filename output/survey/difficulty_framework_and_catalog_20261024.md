# Difficulty Framework and Current Catalog Classification

> **Superseded organizing framework, 2026-10-26:** the current design uses six
> capability dimensions, not L1-L5. Read the [English current design](current_design_en_20261026.md)
> or [Chinese companion](current_design_zh_CN_20261026.md). The historical
> decisions, classifications and evidence below remain intact; they do not
> prescribe current release quotas, radar axes or difficulty bands.

**Date:** 2026-10-24

**Catalog baseline:** `5bfa95970d785b4026786f93bca1037fdbbcc189`

**Updated:** 2026-10-24, following the user-confirmed mechanism-oriented ladder discussion.

**Decision:** Adopt basic perception and action, single-mechanism workflows, goal-driven planning, long-horizon adaptive planning, and autonomous role-based activity. The user reaffirmed these five core requirements on 2026-10-24. They describe capability demands, not calibrated empirical difficulty bands. Mechanism categories are open and game-dependent, not an exhaustive RPG taxonomy. This revision supersedes earlier level wording, including L5 "complex expedition composition."

**Classification status:** Provisional source-grounded assignments, not empirically calibrated difficulty bands.

**Historical classification scope:** 31 paired objectives at the stated baseline, corresponding to 62 independently executable task YAMLs. Later definitions do not automatically reclassify or certify that snapshot.

This document records the agreed design framework and retains its historical
catalog classification. Definition updates do not change task YAML, budgets, tools, experiment membership,
scorers or historical results. Scoring recommendations below remain proposals,
not an approved or implemented leaderboard protocol.

The subsequent [100-slot candidate design](candidate_task_slots_20261024.md)
applies this framework to ten candidate slots per level per game, allowing
materially different initial-condition variants while explicitly grouping
related families. It does not replace the current-catalog classification below
or certify the proposed 200 task-mode combinations.

## 1. The five-level capability ladder

| Level | Capability requirement | Added requirement over the preceding level | Example |
| --- | --- | --- | --- |
| L1: Basic perception and action | Recognize the current state, select an appropriate object or action, and execute a basic interaction. | Establish usable perception and control without cross-stage planning. | Select a supplied item; collect an exposed object; place one block. |
| L2: Single-mechanism workflows | Complete a predictable action chain centered on one dominant mechanism. | Understand the mechanism's rules and execute its short dependencies correctly. | Process supplied materials through a known recipe chain; sell supplied goods and buy an affordable item. |
| L3: Goal-driven planning | Independently decompose a goal and coordinate resources, order and dependencies. | Organize a multi-stage plan rather than merely execute a supplied procedure; a focal mechanism may require supporting mechanisms. | Plan equipment production with resource search and fuel allocation; prepare supplies for a hunt and return. |
| L4: Long-horizon adaptive planning | Coordinate interdependent mechanisms over an extended process with incomplete information and a changing world. | Retain substantial L3 demands while using cross-stage memory, discoveries and action consequences to revise strategy. | Explore an expedition region, discover new access requirements, and reconsider preparation, resupply and routes using earlier findings and expenditure. |
| L5: Autonomous role-based activity | Pursue an open but evaluable role mission, choosing worthwhile subgoals, organizing activity and accumulating outcomes. | Decide what is worth doing next, not merely how to execute a given plan. | Conduct a bounded regional survey, develop a settlement, or pursue a native trading career with verifiable progress. |

### Purpose of each level

- **L1 asks whether the Agent can perceive, select and act:** establish elementary
  state recognition, interaction and control, not cross-stage planning proficiency.
- **L2 asks whether the Agent can use a mechanism:** understand its rules, follow
  short dependencies and execute a mostly predictable workflow.
- **L3 asks whether the Agent can plan around a goal:** decompose the goal and
  coordinate a dominant mechanism with supporting mechanisms, preparations,
  constraints and local changes. This is the intended planning-discrimination layer, not a
  proven claim that every non-planning heuristic must fail.
- **L4 asks whether the Agent can adapt using experience:** discover relevant
  facts, revise assumptions and change plans while the world continues. It is
  not simply faster reactions or a longer predetermined sequence.
- **L5 asks whether the Agent can sustain purposeful autonomous play:** turn a
  role mission into a sequence of useful, self-chosen activities and verifiable
  accumulated outcomes. It is neither an L4 checklist repeated at greater
  length nor aimless wandering rewarded for duration.

The progression is **operation -> composition -> planning -> adaptation ->
long-term autonomy**. Informal easy-to-extremely-difficult names are shorthand,
not calibrated success-rate bands. L5 primarily adds autonomy and openness;
it need not have a lower completion rate than every L4 task.

Task descriptions should separate mechanism tags, capability level, and measured
difficulty/cost under a specified Agent, interface and protocol. Within a related
task family, L4 should retain substantive L3 planning demands while adding
consequential discovery and cross-stage plan revision, not replace them with a
shorter route-choice exercise. This is not a requirement that every L4 take
longer than every unrelated L3. The accepted definitions do not automatically
reclassify existing tasks, certify the current expedition as measuring adaptation,
or change the planned catalog size or first-release scope.

### Open mechanism coverage for L1-L3

The ladder above is an accepted design principle. The categories below are a
working coverage aid, not a validated, exhaustive or mutually exclusive taxonomy
of 3D RPG mechanics. Games need not support every category. Extend, split or merge
categories when native systems and concrete task needs justify it; do not invent
gameplay to fill a rectangular checklist. Examples are proposals, not new tasks
implemented or qualified by this documentation update.

| Dominant mechanism | L1: Atomic interaction | L2: Mechanism workflow | L3: Goal-oriented planning |
| --- | --- | --- | --- |
| Items and containers | Take a specified nearby item. | Select and retrieve supplies from known containers. | Plan a limited expedition loadout while preserving later requirements. |
| Crafting and processing | Execute a recipe with prepared inputs. | Complete a predictable processing chain. | Allocate competing materials and fuel across multiple needed products. |
| Trading | Inspect an offer or make a prepared exchange. | Sell supplied resources and buy a target item. | Allocate purchasing power among equipment, food and retained funds. |
| Exploration and information use | Identify a nearby landmark or read accessible information. | Follow a short discoverable clue to a destination. | Compare information from candidate sites to plan a route and return. |
| Combat and recovery | Equip a weapon, strike once or use a recovery item. | Complete a simple encounter with preparation supplied. | Plan preparation, combat and recovery around downstream requirements. |
| Construction and traversal | Place/remove a block or execute a basic movement. | Build a simple supplied-material structure or follow a known route. | Plan materials and geometry to enable access or protect a goal. |
| Communication and contracts | Open a native interaction and select an option. | Obtain information or complete a short native delivery workflow. | Combine information or commitments with acquisition, exploration or combat. |

Other possible areas include farming and husbandry, equipment repair and
progression, stealth and detection, transport, and native cooperation or group
management. These are illustrative omissions to investigate, not approved scope,
mandatory additions, or claims that Minecraft and Veloren expose these systems
through the current benchmark. Distinguish a game mechanic from a general Agent
capability: memory, information use and planning can span many mechanic families.

L1 is not "outside all mechanisms": it isolates a basic interaction within one.
L2 has a dominant mechanism, not a prohibition on supporting movement or item
selection. L3 typically combines a focal mechanism with supporting ones, but
mechanism count is not a grading formula: complex construction alone can require
substantial planning. L4 needs consequential long-horizon revision, not merely
more mechanisms. All examples require mode-specific checking of actual initial
conditions, observations and tool assistance.

For L1-L3 expansion, prioritize missing mechanisms and prerequisites of complex
tasks over additional near-duplicate recipes or enemies. Record the focal
mechanism, supporting mechanisms, required information, resource dependencies,
native success evidence and ST/VM gaps. A high-level failure can be interpreted
alongside corresponding basic tests, but passing them does not by itself prove
that a later failure is caused by planning or memory.

Historical labels need reassessment under these definitions, not automatic
promotion: an iron-pickaxe task may be upper L2 with a known prepared production
chain, or L3 if resource search, excavation and fuel allocation require planning.
A single-enemy fight is not automatically L3. This update leaves existing
classification tables intact as provisional historical evidence.

### L5 boundary: sustained agency, not inferred personhood

"A complete life" is a motivating long-term vision, not a literal first-release
episode requirement. Operationalize it as a bounded role mission with autonomous
subgoal selection, an evolving understanding of the world, long-term organization,
coherent role-related choices and accumulated verifiable outcomes. Do not claim
to measure consciousness or human-like worldviews, life philosophy or moral
values from gameplay or self-description. Multiple legitimate strategies and
preferences should remain acceptable under the public mission criteria.

### Use in task design and paper writing

Present the hierarchy as an intended progression from operating interfaces to
using mechanisms, planning around goals, adapting over time and organizing
autonomous role activity. Support it with concrete dependency, information,
resource, real-time and spatial demands, then calibrate empirically. The central
claim is coordination between long-term goals and immediate action, not task
duration, mechanism count or a universal RPG skill hierarchy. Low-level tasks
provide diagnostic references for interpreting composed tasks; not every
diagnostic is itself a core long-horizon real-time task. The 200-YAML coverage
target is a development goal, not evidence of independent mechanism coverage.

### Interpretation rules

1. Higher levels compose lower-level **capabilities**, not necessarily every
   preceding task. Concatenating unrelated objectives does not raise the level.
2. Count game-level demands, not tool calls or key presses. ST can compress
   several inputs into one fixed skill; VM can require many inputs for the same
   operation. The supported skill semantics must still be disclosed.
3. Levels require both capability progression and empirical calibration.
   Individual controller-specific inversions can occur, but systematically
   easier or substantially shorter L4 tasks cannot be justified solely by an
   adaptation label. Compare within the same game, mode and Agent settings.
4. Local enemy motion calls for reactive execution, but does not by itself
   establish L4 strategic replanning. A strong enemy is not automatically L4.
5. A good L4 agent may plan contingencies in advance. The requirement is that
   relevant facts become available during play and affect decisions, not that
   advance planning is forbidden or necessarily useless.
6. "Experience" initially means observations and outcomes within the same
   episode. "Self-evolution" is not a claim of parameter learning or self-modifying
   software. Cross-episode learning, generated skills, code modification and
   model updates require separately declared permissions and protocols.
7. Human playtime and "expert player" labels are intuition, not measured
   definitions. No human study currently supports hour-based thresholds.
8. L5 may remain empty. Universal failure or missing feasibility evidence does
   not qualify a task as extremely difficult.
9. Use normal player mechanics. Administrative setup, control bridges, private
   scoring and authored geometry are disclosed benchmark facilities, not
   permission to grant flight, invulnerability, remote interaction or hidden help.
10. Adaptation needs behavioral evidence, not just a verbal claim of learning.
    Examine later decisions under related conditions, account for changed
    equipment or encounter difficulty, and test informative task variants.
    Do not require a particular written plan or reasoning style.
11. Core L4/L5 activities must retain consequential real-time interaction and
    persistent resource effects. Openness alone does not satisfy the benchmark's
    long-horizon, real-time research claim.

### Calibration clarification: 2026-10-24, after reconnaissance trials

The user requires L4 to retain substantial L3 planning demands while adding
environmental change, experience-informed revision and long-horizon analysis.
A short route-choice exercise is not sufficient. The roughly 30-minute active
play horizon discussed for L4 is a design target to investigate, not an approved
hard minimum or a reason to add waiting, repetitive movement or slow inference.
Exact admission thresholds and calibration cohorts remain undecided.

Assess success rate, successful active completion time, model request count
and token consumption together. Control game/mode, model, scaffold, tools,
inference settings and budget policy; retain sample sizes and uncertainty.
Separate successful completion times from early deaths and deadline failures.
Distinguish logical model decisions from retry attempts, input from output
tokens, and cumulative input/context replay from newly generated content.
These measures describe workload and outcomes, not direct proof of reflection.
Do not introduce token/call quotas or reward inefficiency to force progression.

The current eight reconnaissance task YAMLs are implemented short adaptation
prototypes, not admitted mature L4 tasks. Minecraft ST succeeded in about
204-214 seconds, versus historical iron-pickaxe ST success at 422 seconds
(provisional L2) and diamond ST success at 647 seconds (provisional L3).
These small, non-controlled samples flag a design concern rather than establish
a stable ranking. Initial equipment, compressed execution and limited unknown
route choices weaken the claimed progression. Native feasibility and valid
Baseline runs do not resolve this design gate; publication as qualified L4
is on hold pending redesign and calibration. Preserve all existing results.

Counting clarification: one independently executable task YAML is one task.
The historical tables below count paired objectives at the stated baseline;
their 31 rows correspond to 62 task YAMLs. The new increment adds eight YAMLs
(two per game/mode), but does not yet add eight admitted L4 tasks.

### Exploration and prompt contract: user clarification, 2026-10-24

L4 supplies, equipment and useful facilities may be distributed across
discoverable map locations rather than granted at spawn. Preparation is part
of the Agent's problem. Public task text should state the basic objective,
success constraints and limited starting hints, not prescribe the production,
scouting, combat and return sequence or disclose all useful coordinates.
Control documentation remains explicit and separate from solution guidance.

Relevant locations, affordances and relationships must be discoverable through
each admitted mode. Use persistent ordinary world evidence and coherent native
mechanics or learnable map structure, not invisible arbitrary rules. Exploration
should reveal information that can be recalled and applied later; do not replace
it with a benchmark-provided discovered-location list, route planner or automatic
reminder. Agent-owned memory remains allowed under the declared scaffold and
budget; no particular internal reasoning or written reflection is mandated.

The evaluator may privately know locations and native facts, but must not hide
success requirements or require an undisclosed route/action sequence. Any hints
must be available consistently to Agents evaluating the same task version.
Failure to find, remember or use legitimately available information can be a
valid Agent failure, but only after checking discoverability, observation/tool
delivery, lifecycle and scoring. Do not attribute an interface defect, accidental
information loss or an impossible instance to model memory or reasoning.

This clarification governs the next task revision; existing coordinate-rich
reconnaissance YAMLs and their recorded results remain prototype evidence.

### Feasibility acceptance clarification: 2026-10-24

The user does not require a Baseline, another Agent or a scripted reference to
complete the full task as a mandatory acceptance gate. Do not repeatedly tune a
controller or weaken a task merely to obtain a successful run. Baseline execution
remains required, and valid failures remain part of the evidence.

Instead, establish evidence-backed feasibility: required materials exist and
can be acquired; relevant clues are accessible through each admitted mode;
locations and objects are reachable with native mechanics; recipes and tools
work; scoring matches the public goal; and at least one coherent solution fits
the joint resource and time constraints. Check for circular dependencies,
unavoidable expiry and other cross-stage conflicts, not only isolated step
feasibility. Clues need not prescribe every action or reveal a walkthrough.
Fix impossible configurations, inaccessible essential information and interface
defects; do not fix legitimate Agent mistakes by adding hidden help.

An end-to-end successful trajectory is stronger optional evidence, not a
prerequisite. If acceptance relies on native world inspection, dependency
analysis and focused runtime checks, disclose that basis and explicitly retain
the lack of an observed full success. Feasibility does not by itself establish
calibrated difficulty or prove that the task measures long-horizon adaptation.
This clarification supersedes earlier mandatory successful-reference wording
in this document and development receipts.

## 2. Three separate descriptions

Each task should eventually report:

- **Design level:** L1-L5, with a short capability rationale.
- **Empirical difficulty:** outcomes by task version, mode, Agent, model, budget
  and instance; sample sizes and uncertainty; failure stage and termination cause.
- **Research role:** basic diagnostic, spatial/resource diagnostic, reactive
  combat diagnostic, or coupled real-time core candidate.

L3 is not sufficient for core admission. A static construction task can require
L3 spatial composition without measuring consequential real-time planning.
Likewise, an unused terminal resource reserve is not proof of downstream coupling.
Apply the [core-task admission rules](coupled_task_design_20261024.md) separately.

Baseline is the first implementation/difficulty check, not the sole definition
of difficulty. Selected additional Agents help distinguish a controller-specific
weakness from broadly excessive difficulty. Do not assign fixed percentage bands
from one or two episodes, pool ST with VM, or count initialization failure as an
Agent loss. Success references establish feasible public-control solutions, not
model success rates. Current source review did not rerun any game or model.

## 3. Current Minecraft classification

Links below point to ST definitions; every row has a corresponding VM definition.
Assignments consider actual starting inventories, not just task titles.
The eleven island tasks currently have a uniform 2,100-second limit; this legacy
cap is not a calibrated difficulty measure. Coupled tasks have 600/900-second
development limits.

| Task | Level | Rationale and research role |
| --- | --- | --- |
| [island.collect_logs](../../config/minecraft/tasks/structured_tools/collect_logs.yaml) | L1 | Collect three exposed logs; elementary gathering diagnostic. |
| [island.collect_dirt](../../config/minecraft/tasks/structured_tools/collect_dirt.yaml) | L1 | Collect three dirt blocks; elementary gathering diagnostic. |
| [island.collect_cobblestone](../../config/minecraft/tasks/structured_tools/collect_cobblestone.yaml) | L2 | Starts with no tools: prepare a pickaxe before obtaining cobblestone. Not a one-operation collection task. |
| [island.craft_wooden_pickaxe](../../config/minecraft/tasks/structured_tools/craft_wooden_pickaxe.yaml) | L2 | Gather and process raw materials through a predictable recipe chain. |
| [island.craft_stone_pickaxe](../../config/minecraft/tasks/structured_tools/craft_stone_pickaxe.yaml) | L2 | Extend the deterministic gathering/tool chain; length alone does not create adaptive planning. |
| [island.smelt_iron_ingot](../../config/minecraft/tasks/structured_tools/smelt_iron_ingot.yaml) | L2 | Prepare mining, furnace and fuel through a known production chain; upper end of L2, pending calibration. |
| [island.craft_iron_pickaxe](../../config/minecraft/tasks/structured_tools/craft_iron_pickaxe.yaml) | L2 | Longer but largely predictable mining/smelting/crafting chain; upper end of L2. |
| [island.collect_diamond](../../config/minecraft/tasks/structured_tools/collect_diamond.yaml) | L3 | Coordinate tool progression with ore search and excavation; resource/navigation diagnostic, not yet qualified dynamic exploration. Borderline assignment to revisit if search is effectively a fixed recipe. |
| [island.build_plank_wall_2x2](../../config/minecraft/tasks/structured_tools/build_plank_wall_2x2.yaml) | L2 | Four placements with 64 planks supplied; no material preparation requirement. |
| [island.build_plank_cube_2x2x2](../../config/minecraft/tasks/structured_tools/build_plank_cube_2x2x2.yaml) | L2 | Small regular eight-block solid structure with supplied planks; extra placements do not alone justify L3. |
| [island.build_plank_enclosure_5x5x2](../../config/minecraft/tasks/structured_tools/build_plank_enclosure_5x5x2.yaml) | L3 | Coordinate multiple sides, height and an empty interior with exact final geometry; static spatial diagnostic, not a real-time core task. |
| [forge_hunt_return](../../config/minecraft/tasks/structured_tools/forge_hunt_return.yaml) | L3 | Preparation, approach, live combat and same-life return; lower-complexity coupled candidate despite the historical "entry" label. |
| [two_outposts_return](../../config/minecraft/tasks/structured_tools/two_outposts_return.yaml) | L3 | Two encounters, persistent resources, optional cache and cargo return; more composed than the entry task, but routes/objectives are substantially disclosed. |
| [trade_outposts_return](../../config/minecraft/tasks/structured_tools/trade_outposts_return.yaml) | L3 | Trade funding, weapon/food allocation, two encounters and cargo return; local adjustments, not demonstrated L4 information-revealing planning. |

**Minecraft totals:** L1 = 2, L2 = 7, L3 = 5, L4 = 0, L5 = 0.

## 4. Current Veloren classification

| Task | Level | Rationale and research role |
| --- | --- | --- |
| [move_2_metres](../../config/veloren/tasks/structured_tools/move_2_metres.yaml) | L1 | One short movement and stop; control diagnostic. |
| [known_food](../../config/veloren/tasks/structured_tools/known_food.yaml) | L1 | Recipe already known and all ingredients supplied; recipe execution diagnostic, not a preparation chain. |
| [gather_food](../../config/veloren/tasks/structured_tools/gather_food.yaml) | L2 | Obtain a missing ingredient and execute a known recipe; native item expiry is disclosed, but no substantial competing objective is established. |
| [learn_food](../../config/veloren/tasks/structured_tools/learn_food.yaml) | L2 | Use a supplied recipe collection, then craft with supplied ingredients. |
| [craft_equip](../../config/veloren/tasks/structured_tools/craft_equip.yaml) | L2 | Known hide/leather/armor chain, station visits and equipment swap; largely deterministic with sufficient supplied hides. |
| [recover_health](../../config/veloren/tasks/structured_tools/recover_health.yaml) | L2 | Use limited recovery, account for delayed effects and preserve a reserve; narrow consumable/timing diagnostic, not demonstrated long-term resource competition. |
| [wall_detour](../../config/veloren/tasks/structured_tools/wall_detour.yaml) | L2 | One disclosed wall and fixed endpoint; simple route execution. |
| [staggered_detour](../../config/veloren/tasks/structured_tools/staggered_detour.yaml) | L2 | Two disclosed walls and opposing openings; deterministic route composition. |
| [elevation_steps](../../config/veloren/tasks/structured_tools/elevation_steps.yaml) | L2 | Use a disclosed staircase to a known endpoint; precision may be demanding, but little adaptive planning is required. |
| [long_detour](../../config/veloren/tasks/structured_tools/long_detour.yaml) | L2 | Disclosed 220-metre route and obstacles; potentially difficult sustained control, not evidence of L4 unknown-region exploration. |
| [food_reserve](../../config/veloren/tasks/structured_tools/food_reserve.yaml) | L3 | Coordinate recipe learning, expiring ingredient collection and several retained quantities; lower-complexity resource diagnostic, not proof of downstream resource consequences. |
| [defeat_legoom](../../config/veloren/tasks/structured_tools/defeat_legoom.yaml) | L3 | Adapt aim, spacing, attack and recovery to a moving enemy; reactive combat diagnostic. |
| [defeat_wolf](../../config/veloren/tasks/structured_tools/defeat_wolf.yaml) | L3 | Same local combat capability category, with high/uncertain execution difficulty. Successful feasibility qualification remains insufficient; not promoted to L4 for failure rate. |
| [dual_legoom](../../config/veloren/tasks/structured_tools/dual_legoom.yaml) | L3 | Multi-target spacing, attack order and recovery under local dynamics; combat composition without strategic information revelation. |
| [combat_supply_return](../../config/veloren/tasks/structured_tools/combat_supply_return.yaml) | L3 | Expiring supply, live combat, limited healing and settled return; coupled candidate, though the retained-potion endpoint alone does not prove later resource dependence. |
| [prepare_hunt_return](../../config/veloren/tasks/structured_tools/prepare_hunt_return.yaml) | L3 | Prepare armor before damage, fight and return in the same life; simple expedition structure with difficult reactive execution. |
| [provisioned_hunt_return](../../config/veloren/tasks/structured_tools/provisioned_hunt_return.yaml) | L3 | Expiring hide collection, processing/equipment, two encounters and persistent supplies; upper-complexity L3 candidate, not yet a demonstrated L4 task. |

**Veloren totals:** L1 = 2, L2 = 8, L3 = 7, L4 = 0, L5 = 0.

## 5. Coverage and measured difficulty are not the same

| Level | Minecraft | Veloren | Total distinct tasks |
| --- | ---: | ---: | ---: |
| L1 | 2 | 2 | 4 |
| L2 | 7 | 8 | 15 |
| L3 | 5 | 7 | 12 |
| L4 | 0 | 0 | 0 |
| L5 | 0 | 0 | 0 |
| Total | 14 | 17 | 31 |

These provisional assignments supersede earlier informal "entry/intermediate/
harder" design labels, not the underlying episode results. In particular,
**L3 does not assert that current Baseline reliably solves the task**.

| Coupled task | Recorded Baseline ST | Recorded Baseline VM | Additional evidence |
| --- | --- | --- | --- |
| Minecraft forge/hunt/return | Success | Failure | Public ST reference succeeds. |
| Minecraft two outposts | Success | Failure | Public ST reference succeeds. |
| Minecraft trade-funded outposts | Success | Failure after native purchase | Public ST reference succeeds; a separate initialization failure is excluded from Agent outcomes. |
| Veloren prepare/hunt/return | Failure, including optional-Strike retry | Success | Public ST reference succeeds. |
| Veloren provisioned hunt | Failure, including optional-Strike retry | Failure | One Hermes ST run succeeds; public ST references succeed. |

Sources:
[coupled expansion qualification](coupled_expansion_qualification_20261024.json),
[native trade qualification](native_trade_qualification_20261024.json), and
[earlier encounter qualification](veloren_encounter_expansion_20261023.json).
These are small development cohorts across documented tool/runtime versions,
not a fresh complete sweep of the current catalog. Some runs were concurrent;
they are not latency comparisons. Earlier assisted Veloren results must not be
used as current unassisted calibration.

## 6. L4 design readiness and admission

The current framework supports persistent world/inventory state, continuously
running native games, bounded public controls, private evaluation evidence,
recordings and failure classification. Minecraft also has native construction,
mining and trading interfaces. These provide a foundation for a **bounded L4
prototype**, not proof that a qualified L4 task already exists.

The current Veloren integration is more restricted: authored platforms,
limited designated encounters and station types, with natural-region and
NPC/contract qualification still incomplete. The first L4 prototype is more
practical in Minecraft; neither game requires a promise of unrestricted
continent-scale support.

An L4 candidate should provide:

1. A clear objective and public rules, with relevant facts not fully known at
   departure. Hidden information must be discoverable through admitted controls.
2. At least one consequential information-to-plan dependency: different
   discoveries make different strategies appropriate.
3. Feasible alternatives, such as construction versus detour, or continued
   exploration versus resupply. No guessing an unobservable unique solution.
4. Persistent consequences: earlier spending, damage or route discoveries
   affect later choices and goal feasibility.
5. Native dynamic pressures that matter during reasoning and execution,
   rather than a purely static search puzzle.
6. Native outcome evidence plus enough trajectory evidence to analyze use of
   information and experience. A final success alone does not isolate adaptation.
7. Validated instances and successful public-control references, followed by
   Baseline checks and selected diagnostics. A fixed route working everywhere
   is counterevidence to the intended adaptive interpretation.

**Example, not implemented:** recover supplies in a bounded region with multiple
candidate sites. Native terrain and target placement vary at initialization.
Discovering a blocked passage or locating the cargo changes the appropriate
route, tool preparation or resupply decision. The evaluator does not secretly
move the goal or create arbitrary obstacles during play to force "surprises."
Advance contingency planning remains a valid solution.

## 7. L5 design: open mission, bounded world, verifiable progress

### Distinction from L4

L4 supplies a relatively explicit goal but requires discovery and adaptation of
the solution. L5 supplies a **role mission and evaluation boundaries**, while
leaving substantial subgoal selection, exploration priorities and activity
organization to the Agent. A meaningful L5 episode has cumulative development:
earlier knowledge, infrastructure, relationships supported by native mechanics,
or economic assets enable later activities.

The public mission should explain what counts as useful progress without
prescribing an exhaustive route or a fixed sequence of mandatory actions.
The Agent may discover that an initial direction is unproductive and choose
another, provided the mission remains the organizing objective.

### Candidate roles and native-mechanics limits

| Candidate role | Possible mission | Qualification boundary |
| --- | --- | --- |
| Ecological field researcher | Build an evidence-backed record of species, biomes and habitats within a bounded region. | Define biome versus species coverage and verify which targets actually exist. Do not imply a richer ecosystem model than the game provides. |
| Geological surveyor | Investigate terrain and mineral distribution, collect samples and establish useful survey coverage. | Minecraft is a plausible starting point, but survey submission, coverage and observation-provenance evaluation are not implemented. |
| Trader | Develop verifiable wealth and useful trading opportunities while managing travel, danger and resources. | Use genuine native transactions. Define asset valuation and the comparison population before using "richest"; avoid rewarding only a repetitive exchange exploit. |
| Settlement builder | Develop functional shelter, storage, production and resident safety. | Validate each claimed native function and measure actual outcomes, not merely decorative construction or building counts. |
| Political organizer or commander | Form alliances, negotiate disagreements or coordinate residents. | Aspirational only: no currently qualified political disagreement, coalition or resident-command mechanism. Do not invent an LLM society and present it as existing Minecraft/Veloren gameplay. |

Role narratives never grant new player powers. Supporting a political or military
career depends on the chosen game's actual systems; it is not justified merely
because the evaluator can generate a story about it.

### Boundaries and fairness

- Replace unbounded "explore the entire continent" goals with a validated region
  and explicit time, inference and action budgets. Enumerate the actual target
  universe privately where possible; disclose what constitutes coverage.
- "Find all" is appropriate only when completeness is meaningful and feasible.
  Otherwise score verified breadth, accuracy and cumulative progress within
  the budget, with any completion threshold declared in advance.
- Keep objectives, permissions, region limits and evaluation dimensions public.
  The private scorer may know target locations; the Agent must not receive
  hidden answers through observations or mid-episode evaluator feedback.
- Preserve the real-time protocol through long runs. State any persistence,
  interruption, death/respawn and recovery rules explicitly; do not silently
  reset resources or excuse lost progress.
- Sample and freeze task instances for comparisons. More freedom does not
  justify unlimited compute, incomparable seeds or changing criteria after runs.

### Layered evaluation, including bounded AI-assisted judging

1. **Native fact layer:** verify visits, observations under track-specific
   visibility rules, item acquisition, transactions, construction, deaths and
   resource changes. Proximity alone need not establish identification; a report
   of a discovery is not proof that it occurred.
2. **Mission-quality layer:** use a declared rubric for coverage, correctness,
   useful information gain, functional development, activity continuity and
   evidence-backed final outputs. Deduplicate repeated records and avoid
   rewarding action count, elapsed time or verbosity by themselves.
3. **Optional AI-assisted layer:** judge evidence-supported synthesis, mission
   coherence and justified adaptation where fixed rules are insufficient.
   Require evidence citations, blinded Agent identity, pinned judge settings,
   consistency checks and human calibration/audits. Treat Agent text as untrusted
   evaluation material, never instructions to the judge.

AI judgment must not override contrary native facts or reward persuasive
role-playing prose over genuine accomplishments. Unsupported claims should
remain unsupported; absent or broken evidence must be distinguished from
legitimate poor performance. Report uncertainty and judge disagreement.
Weights, quality dimensions and thresholds require validation and freezing
before formal evaluation; this document does not implement an AI judge.

L5 may report an outcome profile rather than a single binary verdict. A scalar
summary, if used, must have predeclared aggregation rules and retain its
component scores. L5 results should not be silently pooled with binary L1-L4
results as though their measurement scales were identical.

## 8. Scoring and next-design recommendations (not yet enacted)

- Keep L1 as an engineering/basic-control report, outside the proposed core
  score. Keep representative L2 diagnostics rather than deleting their evidence.
- Report L3/L4 core-qualified tasks separately from static or isolated skill
  diagnostics at the same level. Do not call all twelve L3 tasks core tasks.
- Report ST and VM separately. Aggregate repeated instances within tasks and
  tasks within families before any overall score; predeclare and freeze weights.
- For bounded goal tasks, use full-task success as the primary outcome. Stage
  progress explains failure but should not hide inability to complete the goal.
  For open L5 missions, use the validated layered outcome profile above, with
  any binary completion threshold or aggregate score specified beforehand.
- Do not make the primary score depend dynamically on which competitors enter.
  Baseline-relative or latent-difficulty analyses may be supplementary once
  sufficient fixed-version data exist.
- First improve L3 coverage and mode-specific solvability. Then add an L4
  candidate with a concrete information-to-plan dependency and successful
  public-control feasibility evidence. Do not manufacture L4 coverage by
  relabeling a long known route, adding stronger enemies or multiplying steps.
- Calibrate legacy budgets separately; neither a long cap nor a short lethal
  episode is a reliable standalone difficulty measure.
- After a bounded L4 prototype is qualified, consider an L5 regional survey
  using the same verified native systems but greater freedom of subgoal choice.
  Keep L5 empty in the implemented catalog until its gameplay and evaluation
  are both qualified; do not fill it by increasing enemy strength or task length.
