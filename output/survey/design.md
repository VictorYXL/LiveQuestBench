# LiveQuestBench Design Discussion Archive

**Current-design entry point (2026-10-26):**
[Six dimensions and task redesign, English](current_design_en_20261026.md) /
[Chinese companion](current_design_zh_CN_20261026.md). Section 31 records the
latest decision. Earlier implementation-status statements are historical,
dated claims, not the status of today's working tree.

Date: 2026-10-21 (UTC+08:00). Latest discussion update: 12:29.

**Status: proposal for review, not an implemented or frozen specification.**

## Archive purpose and reading guide

This is the canonical, self-contained archive of the design discussions through **2026-10-21 12:29 UTC+08:00**, created at the user's explicit request to preserve continuity if the conversation is lost. It retains the framework draft and subsequent discussion, with superseded proposals identified rather than presented as simultaneous requirements. It is an organized English record of requirements, reasoning, alternatives and proposals, not a verbatim chat transcript.

**Current implementation direction:** read Sections 24-25 and the revised Section 4.3 first. They incorporate the discussion after 11:19: a simplified BaseGame/game-class organization, game-first evaluation configuration and fixtures, autonomous agents, snapshot ownership, reuse-first bottom-up implementation, and a small layered test suite rather than tests for every code change. Sections 22-23 preserve the earlier layout discussion and are explicitly historical where they conflict. Exact interfaces and most numeric/protocol choices remain unimplemented proposals.

The former `14_framework_and_protocol_design.md` is retained as a pointer to this file. Continue future design edits here rather than maintaining two divergent copies.

### Project context to retain

Core research question: **Can agents preserve and execute long-horizon objectives when a persistent 3D world continues evolving during their reasoning, and immediate timing/resource choices affect later feasibility?**

The provisional domain is 3D RPGs and RPG-like survival/adventure sandboxes. The initial games are Minecraft and Veloren. Do not assume every task already demonstrates the proposed planning/reaction coupling, or claim that the broad combination is scientifically unprecedented.

Existing projects:

- [GameAgentVisual](../../../GameAgentVisual/): Minecraft visual/motor implementation is on `xianya/init_mincraft`, not the initialization `main` checkout. Inspect Git objects without unnecessary branch switching.
- [GameAgentResearch](../../../GameAgentResearch/): Minecraft structured-state/tools implementation, tasks, evaluators and agent/provider integrations.
- [VelorenBench](../../../VelorenBench/): multiple RPG task families, profiles, native evidence and result-validity machinery. Preserve existing uncommitted work.

Confirmed development sequence: core question -> framework/protocol -> games/tasks -> model/agent experiments -> analysis/iteration -> frozen evidence and publication. This archive belongs to step 2, not authorization to implement the full framework or launch experiments.

Working conventions: communicate with the user in Chinese; new code, identifiers, logs, prompts and technical deliverables in English. Survey/design outputs belong in `output/survey`; temporary exploratory scripts belong in `output/temp`. Preserve existing code, results and unrelated edits. Discuss major protocol/scope choices rather than silently adopting them. The user asked not to be interrupted with questions during the initial overnight design review; unresolved choices are recorded below.

### Decisions versus recommendations

| Topic | Discussion status |
| --- | --- |
| Extensible games, tasks, mods and input/output settings; decoupled runner and model/agent integrations | Explicit user requirements |
| Task definition -> experiment configuration -> common launcher | User-proposed structure, retained by the review |
| Top-level `config/`, `game/`, `agents/`, `core/`, plus external entry/documentation files | User confirmed the organization and, at 11:19, accepted Section 22's separation of evaluation configuration from game implementations |
| External users can supply their own configurations | User-requested direction; proposed resolution/validation rules in Section 5.6 |
| User-selected output root -> task directory -> per-attempt directory with artifacts | User-requested structure; exact names and multi-run/retry rules remain proposals |
| One game per experiment, one resolved interface/variant condition | User preference and recommended v1 rule; exact schema not frozen |
| Baseline reuse, thin adapters, reference agents in this repository | Discussed recommendation; no third-party agent selected or implemented |
| Shared client for reference agents, common accounting records for external agents | Recommended response to the user's instrumentation question; compatibility not yet certified |
| VM / Visual-Motor; ST / Structured-Tool; Task, Task Instance, Episode, Repetition, Attempt, Experiment, Run, Track, Profile, Variant | User approved the proposed terminology at 11:14; configuration names are normalized to TaskConfig and ExperimentConfig |
| Exact output filenames and schema fields | Illustrative conventions, not implemented contracts; legacy output names remain unchanged |
| Precise action concurrency, clock/cutoff, retries, budgets, reset tolerances and logging policy | Proposed defaults, requiring agreement and qualification |
| Free Veloren reference path and optional/comparison Minecraft path | Recommendation, not a finalized mandatory-suite or ranking policy |
| Executable framework, calibrated budgets and runtime guarantees | Not implemented or validated by this design discussion |
| Episode management and snapshots | Confirmed: core owns Episode orchestration and calls snapshots; each game implements snapshot acquisition; evaluators interpret evidence |
| Agent execution and initialization | Confirmed at 11:57: autonomous Agent operation in both VM/ST; fully initialize mutable Agent episode state on each attempt |
| Implementation base and scope | Confirmed: Linux first, reuse GameAgentResearch and GameAgentVisual, adapt Veloren as needed; include several mainstream agents, with names still to select |
| Simplified game classes and module placement | Latest discussed working proposal: game/base_game.py and per-game game.py; no mandatory adapter/runtime/manifest split; model clients under agents/llm |
| Game-first configuration and task fixtures | Latest discussed working proposal: config/<game>/{tasks,experiments,fixtures}; task-specific assets move with evaluation resources, not necessarily into Git |
| Agent image capture | Verified existing Minecraft path is on-demand; recommended v1 default retains it alongside independent periodic recording; no shared frame cache or 30-FPS default was verified |
| Testing scope | User explicitly rejects excessive per-change unit tests; latest working approach is a small layered suite focused on core behavior, with real-game checks explicitly enabled. No numerical test/coverage quota |
| Next phase | At 12:29 the user requested updating this archive first, then considering bottom-up implementation. This turn does not authorize code, installs or evaluations |

### Discussion sequence and where to find it

1. **Game selection and free access:** retain Veloren + Minecraft initially; do not add a third game merely for count. Summary below and supporting report 13.
2. **Shared visual I/O:** OS/display backend reuse with game-specific window/control configuration; Section 7 and the source evidence in Section 3.
3. **Initial ten architecture questions:** Sections 1-19, with an exact question mapping in Section 17.
4. **Baseline code ownership:** reuse official code when viable; reference agents and thin adapters in this repository, heavyweight implementations optionally external; Section 20.
5. **Meaning of experiments:** experiments are the user's level 3.2 input configuration, not another layer and not output artifacts; Sections 5 and 21.
6. **Configuration-centric directory revision:** Section 4.3 and external config rules in Section 5.6.
7. **Task-grouped output, LLM wrappers/accounting and names:** Section 21.
8. **Preservation request:** this complete archive, with the old entry point preserved.
9. **Simplified game integration and assets:** Sections 4.3 and 24 consolidate BaseGame, model-client placement, fixtures, autonomous agents, capture/recording and snapshots.
10. **Testing scope and implementation handoff:** Section 25 records the bounded public-repository inspection, the user's preference against excessive tests, and the lean validation policy for the next phase.

### Game-selection rationale carried into the design

Veloren provides an open-source action-RPG foundation with combat, equipment, recovery and NPC/contract mechanisms. Minecraft supplies resource and crafting dependencies plus a strong connection to prior embodied-agent research. Existing implementations make this pair a reasonable starting point, but this is not proof that all tasks/profiles are reproducible today.

Do not assign long planning exclusively to Minecraft and fast reaction exclusively to Veloren: representative tasks should couple both within the same episode. Both games have voxel-style visuals, so conclusions should not be generalized automatically to all 3D or photorealistic games.

Minecraft is proprietary; an open benchmark wrapper does not make its game client free or freely redistributable. A substantive Veloren path could let users try the benchmark without buying a commercial game. Full-suite versus single-game results would need explicit coverage labels. Free access also does not remove hardware, installation, model-cost or maintenance barriers.

If every mandatory game must eventually be free/open source, investigate replacing Minecraft's mandatory role rather than automatically adding a third game:

- **Luanti + VoxeLibre:** promising free Minecraft-like survival sandbox; substantial overlap with Minecraft, and existing Minecraft tools/protocols/worlds are not assumed portable.
- **Luanti + Exile:** interesting fatigue, temperature, water, shelter and seasonal consequences; slow survival pressure is not automatically fast reaction, and long durations would require careful calibration.
- Luanti is an engine, not a task suite. Its singleplayer pause behavior illustrates why runtime clock qualification remains necessary even with open-source games.

A third game should supply a specific missing measurement mechanism, lawful complete acquisition, viable reset/scoring and enough scientific benefit to justify integration. An open engine needing purchased assets does not satisfy zero-purchase access.

Supporting sources and caveats remain in [game selection and free access](13_game_selection_and_free_access.md), [interaction/release audit](11_scope_influence_and_interaction_audit.md), and [local implementation audit](01_code_review.md). These are evidence supplements; the design recommendations themselves are included here. In particular, offline recorded-game questions are not interchangeable with closed-loop gameplay, and paused interaction is not continuous-live evaluation.

### How to resume work from this archive

Read this status table, Sections 4-5 and 24-25 first, with Section 21 for terminology/accounting. Review the unresolved details in Section 24 before implementing. Later discussion additions refine earlier proposals; they do not imply approval of all preceding defaults. In particular, the earlier single-action reference scaffold is not a universal Agent restriction, the earlier separate runtime/manifest layout is not required, and the acceptance checklist is not a demand for one unit test per item. This is not an implementation or historical-result migration.

No game process, model evaluation or new agent repository was created by this archive operation. The survey directory is currently Git-ignored: this file is persistent local storage, not automatically a Git commit or remote backup. No ignore rules, staging or commits were changed to archive it.

---

## Framework and protocol draft retained in full

The user requested an initial architecture assessment and answers to ten design questions without interruption for clarification. Recommendations below remain proposals where they decide new behavior. No game implementation, runtime settings, or historical results were changed. No game or model evaluation was launched.

Review completion: the existing draft was preserved and supplemented with a concrete directory layout, repetition/instance semantics, permission enforcement, result-policy details, and a mapping that follows the user's original question numbering. These additions are also proposals.

## 1. Executive recommendation

Retain the proposed three user-facing levels:

1. **TaskConfig:** one independently evaluable episode definition.
2. **ExperimentConfig:** one homogeneous evaluation cell with selected tasks, trials, an agent configuration, and a gameplay/interface condition.
3. **Launcher:** execute one or more ExperimentConfigs, manage operational resources, and produce reports.

A TaskConfig may itself contain a long, multi-stage objective. Calling it an "atomic task" should mean an independently scheduled unit, not necessarily an atomic motor skill. A sequence of independently reset TaskConfigs is **not** a persistent long-horizon task.

Within the implementation, separate:

- game lifecycle and fixture construction;
- agent-facing observations and action execution;
- private measurement evidence;
- task objectives, evaluators, and terminal rules;
- common orchestration and result contracts;
- agent scaffolds and model-provider clients.

**Standardize contracts and lifecycle, not every game's state vocabulary.**

The most important corrections to the initial proposal are:

1. Treat setup/admin access, agent access, and evaluator access as separate privileges.
2. Support endpoint predicates, historical events, and interval invariants, rather than requiring every evaluator to use only two snapshots.
3. Select immutable, versioned game/interface profiles instead of allowing arbitrary information/tool combinations in official runs.
4. Make continuous time, cutoff, cancellation, and reset semantics explicit before enlarging the task catalog.
5. Distinguish native task outcome from execution failure and measurement validity.

## 2. Decisions and their status

### User direction retained

- Begin with Minecraft and Veloren; reuse existing implementations.
- Support adding games, tasks, and game variants without rewriting the common runner.
- Use separate visual/motor and structured/fixed-skill settings.
- Keep task definitions and run definitions declarative.
- Support independent model and full-agent integration.
- Preserve the continuously evolving world and long-horizon consequences as the main research purpose.

### Recommended defaults, pending confirmation

| Topic | Proposed first-version rule |
| --- | --- |
| Run scope | One game, one pinned variant, one track/profile combination, one agent configuration per ExperimentConfig |
| Multiple models/games | Launcher executes multiple ExperimentConfigs; grouping is not a merged episode |
| Structured observation | One canonical allowlisted observation profile per game/variant initially |
| Tools | One canonical fixed-skill profile per game/variant initially; subsets are named diagnostic conditions |
| Track names | Visual-Motor (VM) and Structured-Tool (ST); names confirmed at 11:14, detailed profiles still proposed |
| Main clock | Continuous wall-clock evaluation, with world progression independently checked |
| Within-episode control | Confirmed autonomous Agent execution in VM/ST; reference-scaffold action sequencing is not imposed on all agents; limits/cancellation/concurrency must reflect admitted interfaces |
| Trial isolation | Fresh fixture; full mutable Agent episode-state initialization confirmed; no implicit memory carryover |
| Task success signal | Evaluator decides; agent "done" requests termination/evaluation, not success |
| Reset target | Task-relevant validated initial-state equivalence, not a universal bitwise-determinism promise |
| Evidence policy | Minimal audit evidence mandatory; extra videos and full conversation retention optional |
| Run aggregation | Separate game/track/profile cells; no automatic cross-game score averaging |

These recommendations are not silently adopted merely because they appear in examples.

## 3. Evidence from existing implementations

The following code was read for this design. These are static observations, not new runtime qualification.

### Minecraft visual project

Project: [GameAgentVisual](../../../GameAgentVisual/), branch `xianya/init_mincraft`, revision `696257de4ba7788f68026084b794d1265677f75b`. The current checkout remains on `main`; branch files were read through Git objects.

- `benchmark/config.py` already separates task and experiment YAML, validates recognized fields, and resolves world paths relative to the task file.
- `benchmark/tasks/island/craft_wooden_pickaxe.yaml` asks the agent to craft and retain a wooden pickaxe; the evaluator checks final count and net increase.
- `benchmark/evaluator/InventoryEvaluator/evaluator.py` reads `world.before` and `world.after`, with `min_count`, `max_count`, and optional `min_delta`.
- `benchmark/run_benchmark.py` prepares a world with initialized player state, retains `world.before`, and copies it to the live `world.after` directory.
- `game/capture.py` has a reusable XComposite capture mechanism but Minecraft-specific window matching.
- `game/actions.py` has generic XTest keyboard/mouse primitives, focus checks, input release, and a warning that accepted X11 input is not proof of game consumption.
- Subsequent source checks traced `Agent.run_task` -> `session.observe` -> `capture.capture`: Agent observations are acquired on demand. `WindowRecording` creates a separate capture instance and independently samples into FFmpeg. Both paths reuse MinecraftCapture, but do not share cached frames.
- Recorder, launcher and benchmark defaults are 10 FPS, configurable from 1 to 60. The recorder waits `1/fps` between iterations in addition to capture/write work, so the configured rate is not proof of achieved capture frequency. A particular historical run may have used another setting; it was not rechecked here.
- A separate query agent exists in the experiment configuration. Such a helper must be included in scaffold identity, knowledge permissions, budgets, and cost accounting.

**Reuse:** task/run split, frozen-world fixtures, inventory/structure predicates, capture/input backend, result provenance. **Do not assume:** the current task wording proves crafting provenance, or copied saves guarantee identical live trajectories.

### Minecraft structured project

Project: [GameAgentResearch](../../../GameAgentResearch/).

- [AgentProvider](../../../GameAgentResearch/benchmark/agent_provider.py) separates provider creation, task delivery, completion waiting, stopping, logs, and usage collection.
- [Run orchestration](../../../GameAgentResearch/benchmark/run_benchmark.py) has readiness, baseline/final snapshots, startup attempts, warmup, settling, agent cancellation, and cleanup.
- The current [inventory evaluator](../../../GameAgentResearch/benchmark/evaluator/InventoryEvaluator/evaluator.py) checks final inventory; it is not identical to the visual project's delta evaluator.
- The [experiment configuration](../../../GameAgentResearch/benchmark/experiments/vega.yaml) separates agent bindings, scaffold configuration, provider/model settings, and task lists.

**Reuse:** agent/provider lifecycle and existing fixed-skill execution. **Reconcile:** baseline timing, end-of-run settling, evidence cutoffs, and failure classification rather than copying an old runtime's incidental behavior into the new common contract.

### Veloren project

Project: [VelorenBench](../../../VelorenBench/). Inspected files are the current working-tree snapshot, including pre-existing modifications; they are not attributed to this task.

- [Capability negotiation](../../../VelorenBench/harness/scripts/rpg_benchmark/capabilities.py) already checks observation/action compatibility and rejects unsupported renderer/headless combinations.
- [Suite dispatch](../../../VelorenBench/harness/scripts/rpg_benchmark/suite.py) separates setup and scoring by task family; scoring takes fixtures, final state, receipts, events, and samples.
- [Setup](../../../VelorenBench/harness/scripts/rpg_benchmark/setup.py) includes readiness checks and opening-state validation rather than assuming a file copy is sufficient.
- [Contract scoring](../../../VelorenBench/harness/scripts/rpg_benchmark/npc_contracts.py) checks ordinary acceptance, quest identity, native resolution, actual reward insertion, and, for Slay tasks, target death and player contribution after activation. It also checks player death history and actor/session identity.
- [Result handling](../../../VelorenBench/harness/scripts/rpg_benchmark/results.py) distinguishes native outcome, measurement validity, error timing, unknown effects, and cleanup.
- [Observation projection](../../../VelorenBench/harness/scripts/rpg_benchmark/observations.py) restricts image-mode fields and explicitly marks unsynchronized state/frame timing.

**Reuse:** capability admission, evidence journals, task-family evaluators, reset/readiness checks, and result validity. **Do not assume:** image/native controls already equal OS keyboard/mouse controls, or that native tick counts imply identical wall-clock behavior across backends.

## 4. Architecture and dependency direction

```text
Launcher
  |
  +-- ExperimentConfig loader/resolver and admission
  |
  +-- Common episode runner --------------------------+
        |                                             |
        +-- Agent adapter                             |
        |     +-- reference scaffold                  |
        |     |     +-- model-provider client         |
        |     +-- external full-agent integration     |
        |                                             |
        +-- Agent-facing interface                    |
        |     +-- observation projector               |
        |     +-- action dispatcher                   |
        |           +-- shared OS motor backend       |
        |           +-- game-specific fixed skills    |
        |                                             |
        +-- Game lifecycle adapter                    |
        |     +-- launch / reset / ready / cleanup    |
        |     +-- privileged fixture construction     |
        |                                             |
        +-- Private evidence channel ----> Evaluator -+
                                          ^
                                          |
                                      TaskConfig
```

This is a responsibility diagram, not a requirement for a separate process or class for every box. Start with ordinary modules and a small explicit registry. Introduce process isolation where permissions, external-agent integration, or input isolation require it; do not introduce a distributed plugin platform preemptively.

### 4.1 Responsibility table

| Component | Owns | Must not own |
| --- | --- | --- |
| Launcher | Scheduling ExperimentConfigs, operational directories/resources, report collection | Game-specific success logic; hidden changes to gameplay budgets |
| Common runner | Episode lifecycle, admission, deadlines, stopping, evidence coordination, accounting | Minecraft/Veloren-specific item or quest rules |
| Game adapter | Game process/server lifecycle, fixture restoration, readback and game capabilities | Agent planning; arbitrary benchmark-wide score policy |
| Agent interface | Whitelisted observations, allowed actions, bounded execution and receipts | Private scorer fields, setup commands, unrestricted game/admin handles |
| Evaluator | Read-only interpretation of required evidence under a versioned rule | Acting on behalf of the agent; modifying the game to make a goal pass |
| TaskConfig | Public goal, fixture, evaluator parameters, terminal conditions, supported profiles, environment horizon | Model credentials or provider-specific inference options |
| Agent adapter/scaffold | Reasoning, memory, tool selection, permitted observation use | Resetting the task or reading evaluator-only evidence |
| Model-provider client | Request/response conversion, provider capabilities, usage and request metadata | Controlling the game directly or deciding success |

Game-specific predicates and state readers may live next to each other inside the game's package for maintainability. Their **logical permissions** must remain separate even if their source files are adjacent.

### 4.2 Small common contracts

Conceptual operations, not committed Python APIs:

| Contract | Operations / records |
| --- | --- |
| Game lifecycle | describe capabilities; provision variant; reset task fixture; validate opening; start measurement; stop/quiesce; close |
| Agent interface | observe; submit bounded action; cancel; release controls |
| Evidence reader | baseline; subscribe/read journal; interval samples; cutoff-consistent final view; completeness manifest |
| Evaluator | declare evidence requirements; check online terminal predicates when supported; finalize an immutable result |
| Agent session | initialize allowed context; run through restricted interface; stop; report usage/provenance |
| Model client | generate multimodal/tool-capable output; report actual model identity and usage; declare supported features |

Do not force all full agents into a one-request/one-action API. A full agent can contain planners, controllers, and memory, while the benchmark boundary continues to enforce observation/action permissions and total resource accounting.

For fixed-scaffold model comparison, the reference scaffold must be unchanged across models except for declared provider serialization/capability requirements. A provider's lack of images or tool calls must not trigger an undisclosed text-only or semantic fallback.

### 4.3 Proposed directory layout

The following is the **latest simplified working layout**, not existing code or a frozen list of files. It incorporates discussion through 12:29. The four top-level directories are agreed; detailed placement below is the latest discussed proposal. Evaluation resources are grouped by game under `config/`; task-specific fixtures are colocated with tasks, while executable game integration stays in `game/`. The three user-facing levels remain TaskConfig, ExperimentConfig and launcher.

```text
LiveQuestBench/
  run_benchmark.py
  README.md
  config/
    minecraft/
      tasks/
      experiments/
      fixtures/
      profiles/              # Optional reusable declarations
      variants/              # Optional pinned game/mod combinations
    veloren/
      ...same evaluation-resource groups...
  core/
    contracts.py
    config.py
    runner.py
    evaluation.py
    results.py
    backends/
      desktop_x11/
    utils/
  agents/
    base_agent.py
    reference/
    adapters/
    llm/
      base_client.py
      providers/
  game/
    base_game.py
    minecraft/
      README.md
      setup/
        setup.sh
      game.py
      guide/
      evaluators/
      evidence.py            # Optional extraction from game.py
      structured_tools/
        actions/             # Extract only when useful
        observations/
        tools/
          get_observation/
            tool.py
            description.md
      visual_motor/          # Only game-specific VM work
      mods/                  # Only when game-side changes are needed
    veloren/
      ...same responsibility groups...
  tests/
    core/
    game/
    integration/             # Explicit opt-in real-environment checks
  output/
    survey/
    temp/
    runs/
```

Responsibilities:

- `game/base_game.py`: common game contract and genuinely shared helpers, without game-specific branches or Episode orchestration.
- `game/<game>/game.py`: concrete game class implementing launch/reset/readiness, restricted interface creation, private snapshots and close. It already performs the adapter role. A separate runtime helper is optional internal extraction, not another manager.
- `game/<game>/setup/`: explicit platform provisioning, not a per-episode installer. Linux is the current focus; do not create unsupported platform scripts just for symmetry.
- `structured_tools/observations/`: allowed structured-state acquisition/projection; `actions/`: underlying execution; `tools/`: callable schema, documentation and implementation. Avoid redundant forwarding modules.
- Each ST tool may have `tool.py` and `description.md`, with one authoritative parameter schema. `get_observation` may itself be a tool. Query versus mutating effects remain explicit.
- `visual_motor/`: optional game-specific window/control compatibility. Shared capture/input code stays in `core/backends/`.
- `game.py` or an extracted `evidence.py`: private snapshots/events, never automatically registered as agent tools.
- `evaluators/`: game-specific scoring over private evidence.
- `config/<game>/tasks/` and `experiments/`: task definitions and evaluation plans.
- `config/<game>/fixtures/`: task-scene assets or generation descriptors; fixed island saves belong here conceptually, with large assets optionally referenced externally by hash.
- `config/<game>/profiles/` and `variants/`: optional reusable interface/knowledge and build/mod selections; no duplicate authoritative definitions.
- `guide/` and optional `mods/`: allowed guide content and game-side integration/changes with licenses preserved. Task-specific world assets are distinct from general game resources.
- `agents/llm/base_client.py` and `providers/`: model-call abstraction/provider implementations; common accounting contracts and aggregation belong in core.
- `core/`: common runner, config validation, results, budgets/telemetry as needed, shared backends and small utilities.

The directory names describe ownership, not a requirement to create empty folders or one class for every concept. Start with tasks and experiments; extract profile/variant files when they are usefully reused, without duplicating competing definitions. This logical top-level layout does not settle a future Python packaging/import strategy. Use a small explicit registry rather than arbitrary YAML-specified Python imports. Trusted evaluator/adapter code can be shared within a game; the common runner must not gain game-specific branches for ordinary extensions.

An on-disk directory boundary is not a permission boundary. External agents that can execute code must not receive the private fixture/evaluator tree, admin credentials, unrestricted process handles, or private journal paths. A separate process under the same unrestricted account is not sufficient isolation. Grant only the declared public workspace and controlled agent interface, and qualify filesystem/network/display access for the claimed evaluation mode.

## 5. Configuration: retain three levels, add reusable profiles as data

A profile is a versioned bundle of choices, not a fourth required orchestration layer. It can initially be a packaged manifest referenced by a ExperimentConfig. Reuse profiles to avoid copying large field lists and tool schemas into every experiment.

### 5.1 TaskConfig

Recommended fields:

- schema version, stable task ID and revision;
- game ID; compatible game variants;
- public task instruction and public constraints;
- fixture/reset reference and task-specific setup parameters;
- initial-state acceptance checks and tolerances;
- evaluator ID/version/parameters;
- required evidence (derived from or validated against the evaluator);
- terminal semantics: what ends the episode, whether success is latched, death rules;
- canonical task horizon and environment constraints;
- admissible observation/action profile combinations;
- split, family, difficulty and mechanism labels, without claiming those labels are validated;
- artifact/asset provenance.

The public instruction is separately projected from the complete TaskConfig. Never hand an external agent the private YAML containing target coordinates, evaluator rules, hidden objects, or fixture internals unless explicitly part of its allowed setting.

**Long tasks:** a TaskConfig can specify milestone predicates or refer to a game-specific evaluator for a whole dependency chain. Do not run a new reset for each milestone. Do not build a general graph language before concrete tasks require one.

### 5.2 ExperimentConfig

Recommended canonical granularity:

```text
one game
  x one pinned game variant
  x one track + observation/action profile pair
  x one protocol and knowledge condition
  x one agent configuration
  x selected tasks, fixture instances and repetitions
```

A ExperimentConfig may vary fixture seeds/instances through its explicitly scheduled task instances. It should not silently vary game version, mods, action abilities, or knowledge permissions between tasks.

Fields:

- game and immutable variant reference;
- selected task IDs/revisions, instances/seeds, repetition count and schedule;
- track, observation profile, action profile, timing protocol;
- knowledge/guide profile;
- agent mode (fixed-scaffold model comparison or full-agent comparison), agent version/configuration;
- actual provider/model configuration and explicit reasoning settings where supported;
- run-level resource budget profile;
- retention choices beyond required audit evidence;
- study/split identifiers and output labels.

A homogeneous model sweep can later be syntactic sugar that **expands into distinct resolved ExperimentConfigs**. It must not make one agent's model choice leak into another cell.

### 5.3 Launcher

Suggested future CLI shape:

```text
run_benchmark.py --config veloren-vm.yaml --config minecraft-ss.yaml
                 --output results/run-group --record-video
```

This command is illustrative; no such new CLI has been implemented.

Operational options can include output root, labels, scheduling concurrency, allocated device/display, optional video, and resume of completed episodes. Multiple configs are enough initially; a separate campaign YAML is optional later.

**Not all apparently operational flags are scientifically neutral.** Recording load, capture cadence, concurrency on one GPU, network routing, and display settings can affect latency. Save their resolved values and check overhead. Required evidence cannot be disabled by a convenience flag.

### 5.4 Ownership and override rules

| Setting | Definition authority | Run selection / override |
| --- | --- | --- |
| Game/mod/build version | Variant manifest | Run selects immutable variant |
| World/map and initial NPC/player state | Fixture + TaskConfig | Run selects admitted instance/seed, not arbitrary edits |
| Public goal, scorer and terminal policy | TaskConfig | Cannot override in an official run |
| Episode horizon | TaskConfig | Official run uses canonical value; shorter/longer diagnostics create a labeled variant |
| Token/model-call/cost caps | Run budget profile | Fixed across a comparison; actual accounting method recorded |
| Minimum control guide and allowed knowledge | Knowledge profile | Run selects compatible profile |
| Observation fields and visibility | Observation profile | No ad hoc official-run field lists |
| Fixed skills and parameters | Action profile | Named subsets are separate conditions |
| Frames delivered to agent | Observation protocol/profile | Resolved run setting; not video-recording FPS |
| Video retention / full chat retention | Output policy | CLI may select optional extras, not remove required audit evidence |

Resolution should be shallow and explicit: packaged defaults + selected versioned references + permitted ExperimentConfig values + operational CLI options. Reject unknown fields and conflicting assignments rather than using unrestricted recursive dictionary merging. Record both requested and fully resolved configs and content hashes.

Official task time and run inference budgets are separate upper limits: the first exhausted applicable limit terminates control. A changed task horizon is not silently treated as the original condition. Startup and cleanup have their own infrastructure timeouts outside the measured episode.

### 5.5 Task definitions, instances, repetitions, and attempts

Use explicit terminology:

- **Task definition:** the objective, rules, evaluator and fixture family.
- **Task instance:** a concrete admitted fixture/seed/parameter assignment for that definition.
- **Episode:** one measured attempt by an agent on one instance. Multiple dependent stages can occur inside it.
- **Repetition:** another planned episode under the same instance and condition, beginning from a fresh game state and fresh agent episode state.
- **Infrastructure retry attempt:** a separately recorded attempt associated with a scheduled episode, not another success opportunity silently substituted for a failure.

Repetition counts belong to **ExperimentConfig (3.2)** because they determine sample size and the experiment plan. A run-level default is convenient; a task entry may explicitly override it. Use one rule: task-entry count wins over the run default, and a missing count without a default is rejected. Never define competing repetition counts in task YAML and launcher flags.

For the example in Section 6.3, two instances with three repetitions each schedule **six episodes** for one agent configuration. The launcher does not interpret that as three episodes or six retries. Store the expanded schedule before execution.

Use paired instance schedules across agents, but do not infer identical trajectories or model randomness from equal world seeds. Distinguish world seed, task-generation seed, schedule seed, and a model seed if the provider actually supports it. Trials with the same world are repeated observations, not independent evidence of generalization to new worlds.

The proposed reference condition resets mutable agent memory and learned state between episodes. A fixed pre-trained model or frozen prior skill library need not be erased, but its identity must be recorded. Cross-episode learning and memory are separate explicit conditions, not consequences of reusing a process.

If a convenience CLI option for repetitions is added later, it must generate a new resolved ExperimentConfig/condition manifest and must not alter an official frozen study silently. The simpler first version has no such CLI override.

### 5.6 User-owned configuration outside the repository

The bundled `config/` directory supplies discoverable defaults and examples, not the only permitted location. The proposed launcher accepts an experiment YAML path outside the repository. Users should not need to edit source code or copy files into the checkout to select existing tasks, change an experimental condition, or define a new parameterized task.

Resolution rules:

- Resolve explicit relative file references against the YAML file containing that reference, not the shell's current working directory.
- Keep file references distinct from registered versioned identifiers. Named task/profile/fixture references resolve through an explicit catalog; conflicting definitions must fail rather than silently shadow an official identifier.
- Validate task game identity, adapter/evaluator availability, parameter schemas, interface compatibility and evidence capabilities before launching.
- Load configuration as data. New executable skills, evaluators or engine hooks require installed, registered implementations; YAML alone cannot create those capabilities.
- Do not allow configuration to expand the agent's setup/admin/scorer permissions.
- Preserve the requested files and a secret-redacted resolved configuration with hashes of referenced definitions and assets. Credential values remain external.

Custom configurations are supported research conditions, but changing task rules, tools, timing, guides or budgets can change score comparability. Official comparability is established against a frozen resolved-condition manifest, not by file location, filename, or a user-supplied `official: true` flag. An external file with the same resolved condition may remain comparable; a modified file inside the bundled directory is not automatically official.

Task YAML is declarative but not necessarily public to the evaluated agent. Private fixture coordinates, hidden goals and scoring parameters remain inaccessible; project documentation and the launcher expose only the task's declared public projection to the agent.

## 6. Illustrative YAML

**Design examples only.** IDs, profiles, evaluator registrations, and fixture assets below are proposed names, not existing working packages. Values are deliberately illustrative, not calibrated benchmark budgets. YAML parsing can check their syntax; it cannot verify implementation or task validity.

### 6.1 Endpoint task with no provenance claim

```yaml
schema: livequest.task/v0
id: minecraft.obtain_and_keep_pickaxe
revision: draft-1
game: minecraft
compatible_variants:
  - minecraft.island_reference@draft-1
public:
  instruction: Obtain and keep at least one wooden pickaxe before time expires.
fixture:
  ref: minecraft.island_empty_inventory@draft-1
evaluator:
  ref: minecraft.inventory_delta@draft-1
  parameters:
    item: minecraft:wooden_pickaxe
    min_count: 1
    min_delta: 1
  required_evidence:
    - baseline_inventory
    - cutoff_inventory
    - authoritative_player_death_events
terminal:
  success_check: at_episode_end
  player_death: fail_and_stop
  agent_done: stop_and_evaluate
  horizon_seconds: 600
admission:
  interface_profiles:
    - minecraft.vm_reference@draft-1
    - minecraft.st_reference@draft-1
split: development
```

The evaluator is consistent with **obtain and keep**, not proof of crafting. If the instruction explicitly requires crafting, change the evaluator/evidence or qualify a fixture that excludes every alternative acquisition path. Do not claim that a delta check alone establishes the process.

`interface_profiles` reference bundles of one observation and one action profile, preventing an accidental cross-product of incompatible inputs/outputs.

### 6.2 Historical long task

```yaml
schema: livequest.task/v0
id: veloren.accept_slay_return
revision: draft-1
game: veloren
compatible_variants:
  - veloren.rpg_reference@draft-1
public:
  instruction: Accept the offered contract, defeat its target, and return to claim the reward without dying.
fixture:
  ref: veloren.contract_expedition@draft-1
evaluator:
  ref: veloren.contract_history@draft-1
  parameters:
    require_acceptance_before_target_death: true
    require_player_contribution: true
    require_return_to_giver: true
    require_actual_reward: true
    prohibit_player_death: true
  required_evidence:
    - baseline_identity
    - authoritative_contract_events
    - authoritative_target_and_player_death_events
    - authoritative_player_contribution_events
    - authoritative_return_region_events
    - authoritative_reward_events
    - cutoff_state
terminal:
  success_check: online_latched
  player_death: fail_and_stop
  agent_done: stop_and_evaluate
  horizon_seconds: 900
admission:
  interface_profiles:
    - veloren.vm_reference@draft-1
    - veloren.st_reference@draft-1
split: development
```

This builds on the *kind* of evidence already present in Veloren, but the fixture and interface pair are hypothetical. In particular, an OS-motor Veloren profile is not certified by the existing native image interface. A return-region event is a proposed requirement, not a claim that the current implementation supplies it.

### 6.3 One-game ExperimentConfig

```yaml
schema: livequest.experiment/v0
id: veloren_vm_reference_development
game: veloren
variant: veloren.rpg_reference@draft-1
condition:
  track: visual_motor
  interface_profile: veloren.vm_reference@draft-1
  protocol: continuous_reference@draft-1
  knowledge_profile: veloren.controls_only@draft-1
tasks:
  - ref: veloren.accept_slay_return@draft-1
    instances: [development-001, development-002]
    repetitions: 3
agent:
  mode: fixed_scaffold
  ref: reference_reactive@draft-1
  model:
    provider: example_provider
    model_id: example_pinned_model_revision
    credentials_ref: MODEL_API_KEY
budgets:
  ref: development_small@draft-1
output:
  video: false
  full_conversation: true
```

The environment-variable name is a credential reference, not a key. Never persist the secret's value in resolved artifacts.

For a structured run, select `structured_tool` and its admitted interface profile. Do not retain the visual profile while changing only a track label.

### 6.4 Example referenced interface profile

This is an earlier restrictive reference-profile example, retained to illustrate the data shape. Its one-action limit and release-on-completion policy are not approved universal requirements for autonomous Agents; see Sections 11.4 and 24. Profile values and schema remain illustrative.

```yaml
schema: livequest.interface/v0
id: veloren.vm_reference
revision: draft-1
track: visual_motor
observation:
  source: rendered_window
  delivery: on_request_latest
  max_capture_hz: 5
  frames_per_observation: 1
  resize: none
  include_capture_timestamps: true
action:
  source: os_keyboard_mouse
  allow_relative_pointer: true
  allow_window_absolute_pointer: true
  max_action_duration_ms: 1000
  max_mutating_in_flight: 1
  release_on_completion: true
  release_on_terminal: true
```

This profile caps permitted capture frequency; it does not promise five observations each second or five model decisions each second. On-demand capture/delivery and maximum action length must be measured and calibrated. No frame/turn normalization should quietly rescale the world clock.

## 7. Track definitions and common visual backend

### Visual-Motor (VM)

- Input: actual game images, public goal, versioned allowed guide, transport/timing metadata.
- Output: bounded keyboard/mouse primitives or explicitly qualified mechanical equivalents.
- No hidden coordinates, inventory transcription, entity lists, evaluator progress, or state-dependent semantic shortcuts.
- Pixel resizing/encoding must be declared. OCR or visual grounding performed by an agent is part of that agent; benchmark-provided semantic extraction would change the observation condition.

### Structured-Tool (ST)

- Input: a fixed versioned whitelist of game-state fields with documented visibility/range/precision.
- Output: a fixed versioned skill/action inventory with disclosed internal sensing, control, duration, termination and cancellation.
- A skill must not silently solve the whole benchmark objective or select the crucial high-level plan.

These names describe the access conditions, not a claim that their score difference measures only visual competence. Retain existing `image`/`structured` labels in legacy imports, mapping them to new profile identities only after qualification.

### What is shared and what is game-specific?

| Shared by a qualified OS/display backend | Game/variant-specific configuration or verification |
| --- | --- |
| Window image acquisition, encoding, geometry and timestamps | Window selection, rendering compatibility, HUD and cursor behavior |
| Keyboard/button down/up, relative motion, absolute window-coordinate motion | Key bindings, camera mode, sensitivity, input capture/raw-input behavior |
| Input release, focus detection, bounded durations | Whether the game consumes events and whether menus/blur pause simulation |
| Action receipts and basic transport failures | Correct resize/click transform and game-specific interaction effects |

X11, Wayland, Windows, and macOS are not a single interchangeable platform. An XTest session is not per-window input isolation. Parallel visual episodes need isolated display/input contexts and qualified compute allocation.

Do not hardcode game knowledge into the generic backend. A game-specific mapping may translate declared mechanical controls, but automatic object finding, path planning, or inventory selection belongs to ST or to the evaluated agent, not invisible VM infrastructure.

## 8. Structured information: fixed does not mean unrestricted

The user's goal of avoiding configuration sprawl is sound. Adopt one canonical structured profile initially, but define **all of its permitted fields**, not “all internal information.”

Example policy categories:

| Category | Possible ST treatment |
| --- | --- |
| Own health, inventory, equipped items | Usually allowed, with exact semantics |
| Nearby entities/blocks | Declare range, occlusion rules, identity stability, and precision |
| Quest log | Ordinary player-known quests may be allowed |
| Unexplored global map / hidden targets | Not automatically allowed; requires an explicit privileged diagnostic |
| RNG state, unrevealed spawns, setup handles | Private, excluded |
| Evaluator progress, private success flags, event journal | Private unless a task explicitly exposes an equivalent ordinary gameplay cue |
| Administrative spawn/teleport/heal/set-state | Setup only, never an ordinary action profile |

Different games may have different vocabularies and ordinary player knowledge. Consistency means declared permissions and stable conditions, not equal byte counts or identical fields.

The observation projection must also apply to tool results, errors, logs, task instructions, helper-agent inputs, and filesystem/network access. Filtering only the first observation is insufficient.

If a genuinely omniscient state condition is useful, define an explicitly named diagnostic profile and separate its results. Do not change the canonical ST profile silently.

## 9. Guides, frames, tools, and knowledge

### Guide conditions

Distinguish:

1. **Control reference:** key bindings and interface syntax; necessary to use the game.
2. **Static game knowledge:** recipes, item descriptions, general mechanics.
3. **Task solution material:** routes, target locations, demonstrations, hidden setup information.

The first can be common baseline documentation. The second is a declared knowledge condition. The third can invalidate the intended task unless explicitly part of a separate experiment.

Record guide version/hash, language, modality, delivery method (prompt/file/retrieval), and whether retrieval invokes another model. Mandatory included context counts under the chosen context/accounting policy; model-based guide consultation counts as inference, even if it is called a query helper. No unrecorded live web/wiki access in a closed reference condition.

### Frame and action rates

Keep at least four rates distinct:

- engine simulation/render rate;
- capture rate or capture-on-request behavior;
- frames actually delivered to the agent;
- model decisions/actions.

Video-recording FPS is a fifth, independent setting. A buffer size, sampling policy, dropped/duplicated-frame policy, resolution, crop, cursor inclusion and compression affect information and latency.

Recommended simple reference condition: one newly captured frame per permitted observation request, subject to a declared maximum request/capture rate; record capture and delivery times. Do not queue an unbounded stream while the model reasons. Video/streaming-capable agents can be admitted in a separately specified condition.

### Skill profiles

For each fixed skill disclose:

- ID/version, parameters and preconditions;
- privileged/internal observations used;
- whether it contains pathfinding, tracking, or an internal feedback controller;
- termination conditions, maximum duration and cost;
- cancellation acknowledgment and possible partial effects;
- returned public information;
- errors and unknown-effect handling.

Changing tool descriptions alone can change agent behavior; hash them along with schemas and implementation versions.

## 10. Evaluators: evidence acquisition versus task meaning

### 10.1 Recommended placement

Evaluator logic belongs conceptually to the **task/evaluation layer**. Its native evidence readers belong to the **game adapter's private measurement side**, not the agent's signal-conversion path.

The common evaluation library can offer small reusable operations such as:

- final predicate;
- delta predicate;
- event occurrence/count;
- ordered events;
- invariant over an interval;
- conjunction and normalized metric summaries.

Minecraft item names, Veloren quest IDs, reward attribution, and native death semantics remain game-specific.

Start with registered evaluator functions/classes and validated parameters, not arbitrary executable code embedded in YAML. Custom family evaluators remain legitimate when simple predicates are insufficient.

### 10.2 When two snapshots are sufficient

They are sufficient when the objective is genuinely an endpoint property and the snapshots are complete, fresh, and associated with the right actor:

- own at least N items at cutoff;
- net inventory increase of at least N;
- a structure exists in a specified region at cutoff;
- finish at a location, with a specified equipment/health condition.

Even here, specify the item accounting scope: backpack only, equipped slots, containers, dropped entities, durability/metadata, and actor ownership. A world-directory snapshot without correct player identity can score the wrong inventory.

### 10.3 Why collecting or crafting is not always a delta

Let final count be initial count plus acquisition and production, minus consumption, transfer, and loss. The same net delta can arise through multiple histories.

Examples:

| Intended goal | Why endpoints can mislead | Minimal additional evidence |
| --- | --- | --- |
| Craft a pickaxe | Looting or trading for it gives the same final inventory | Authoritative player crafting event, or a validated fixture excluding alternatives |
| Gather ten logs, then consume them in construction | Final inventory may show no increase despite success | Acquisition history plus final construction evidence |
| Smelt ingots and hand them over | Successful delivery removes the ingots | Production and delivery events, with identity/amount |
| Heal an ally | Net HP can be unchanged because damage followed healing, or rise due to natural regeneration | Sourced healing application events |
| Defeat a target yourself | Target absent/dead can result from another actor or environment | Death identity and player contribution |
| Never die | Death and respawn may restore a plausible final state | Complete death history or trusted persistent death counter |
| Visit A before B, then return | Start/end position can be identical without proving the route | Ordered region-entry events or trusted history |
| Hold a location for ten seconds | Two endpoints cannot prove continuous occupancy | Authoritative interval/transition evidence |
| Accept a contract, then kill its target, then claim reward | A final reward-like item does not prove ordering or source | Quest activation, target/contribution, resolution and reward chain |

These are not hypothetical API concerns only: the inspected Veloren contract scorer already checks several such histories.

The existing visual wooden-pickaxe task's delta scorer proves a new retained pickaxe under its fixture, not crafting in every possible world. Do not relabel historical results as event-proven crafting. If the fixture eliminates other acquisition paths, document and validate that assumption.

### 10.4 Exploration and stopping on arrival

“Stop as soon as the agent reaches the region” still requires an online detector. An authoritative region-entry event or equivalent engine hook can latch success even if the player leaves before the final snapshot. Polling can be acceptable for a task with declared tolerance/dwell requirements, but may miss a fast visit.

A final snapshot taken because an independently trusted detector saw arrival can be sufficient supporting evidence. A final snapshot alone, without that detection record, cannot establish that a visit occurred earlier.

### 10.5 Minimum evidence tiers

- **Endpoint:** baseline/cutoff state.
- **Event:** timestamped native event journal with actor, source, sequence and task identity.
- **Interval:** authoritative state transitions, counters or continuous monitor for invariants.

A task declares its minimum evidence. Do not record every engine detail for every task. Conversely, video or periodic screenshots do not prove a “never” invariant without a validated measurement method.

Admission must take the union of evaluator requirements, terminal-monitor requirements and opening-validation requirements. An inventory-only score does not remove the need for death evidence when death is a terminal failure. Reject a task/profile combination if any required channel is unavailable.

An authoritative final quest flag or accumulated counter may summarize history sufficiently. Two *rich* snapshots can then work because the game retained the relevant history, not because endpoints can reconstruct arbitrary events.

### 10.6 Evidence integrity and online checks

Required evidence properties:

- episode/session/actor identity and setup-versus-agent origin;
- authoritative timestamps or a documented clock mapping;
- ordering, deduplication and event sequence coverage;
- visibility separated from private score inputs;
- a baseline boundary and terminal cutoff;
- completeness status, including dropped samples/journal gaps.

Use receipts to distinguish requested, accepted, applied and completed actions. A request log proves intent, not effect.

The online monitor should latch only predicates whose success is irrevocable under the task's terminal rule. “Keep the item until timeout” cannot finish early simply because the item appeared once. Progress may be provisional; final score is authoritative over the sealed evidence.

### 10.7 Minimal history, not continuous full-world snapshots

Supporting historical goals does not require recording the entire world every frame. Prefer the smallest authoritative sufficient record:

| Task requirement | Example sufficient record | Important boundary |
| --- | --- | --- |
| Own an item at cutoff | Consistent cutoff inventory | No claim about how the item was obtained |
| Craft at least one item | Episode-scoped player crafting counter or crafting event | Reset baseline; distinguish production from pickup/trade |
| Visit a region at least once | Native latched region-entry flag with episode identity | Define region geometry and whether traversing counts |
| Never die until task completion | Complete death counter delta or death journal through cutoff | Final `alive` state alone is insufficient after respawn |
| Do A before B | Native milestone state machine or ordered events | Merely observing both final flags loses order |
| Maintain health above a threshold | Trusted minimum-health accumulator over the measured interval | Sparse samples cannot prove an uninterrupted invariant |

These records can be extracted only at the end if the game or instrumented observer maintained them throughout the episode. The key distinction is **state without history versus state that faithfully summarizes history**, not the number of snapshot files.

Do not log every private engine event by default. The evaluator declares a compact evidence requirement; admission rejects unavailable requirements before the agent runs. Instrumentation used to accumulate counters must be private, versioned, and checked for gameplay side effects.

## 11. Episode lifecycle and the real-time contract

### 11.1 Lifecycle

```text
resolve -> admit -> allocate -> launch/reset -> validate opening
        -> arm evidence -> measured start -> execute/observe
        -> terminal cutoff -> quiesce controls -> seal evidence
        -> evaluate -> archive -> cleanup
```

The runner owns orchestration; each game implements the actual reset, evidence and shutdown mechanisms. Cleanup is attempted on every path, and cleanup failure is retained separately.

### 11.2 Measured start

Before start:

- initialize providers and agent processes without revealing live task state;
- restore/setup the fixture and isolate it from unrelated users;
- wait for explicit readiness predicates;
- attach private evidence and verify actor identity;
- acquire a cutoff-aligned baseline and initial observation;
- perform final opening validation.

Define `t0` at the game adapter's release into the measured episode. Public live task delivery must not grant uncharged task-specific planning before that point. Evidence is armed before release, and the initial observation's capture time is recorded even if it precedes delivery.

If the game cannot freeze/stage safely during setup, readiness must be validated at the actual handoff. Record drift and bounds; reject starts outside acceptance. Do not claim an atomic universal start where the adapter cannot provide one.

### 11.3 World progression and clocks

In the continuous main condition, the world continues during:

- model computation and tool selection;
- network waiting, retry backoff, and guide/model helper calls;
- screenshot encoding/transport;
- ordinary action execution and inter-action gaps.

A host timeout alone does not prove this. Verify relevant game dynamics while the agent is deliberately delayed. Also verify the effect of menus, loss of focus, unloaded regions and server tick behavior.

Use host monotonic time for local elapsed deadlines, UTC for human-readable provenance, and native game clock/tick values as additional evidence. Foreign monotonic clocks cannot be compared directly. Record clock source/mapping/uncertainty; do not invent exact alignment or equate update counts to 60 Hz.

Record both real elapsed time and simulation progression. Paused, slowed, and controlled-delay conditions are separately labeled diagnostics.

### 11.4 Reference action semantics

**Scope correction at 11:57:** the following is an earlier optional reference-controller proposal, not a universal VM/ST protocol. The user chose autonomous Agent execution and reuse of existing Minecraft semantics. Do not force all agents into a single active action, automatic release after every call, or a one-frame/one-request loop. Resolve allowed overlap, held inputs and cancellation against actual backend capabilities, and disclose reference-scaffold policies.

Proposed simplest reference controller:

- allow at most one active mutating action per actor;
- allow several simultaneously held buttons inside one bounded motor action;
- permit one declared fixed skill to execute its internal loop up to a bound;
- do not create a hidden FIFO backlog of stale actions;
- release motor inputs when the action completes or on terminal/abort;
- record accepted/applied/completed/cancel-requested/cancel-ack times and partial effects.

The world does not pause when the controller becomes idle. Holding keys across model calls, asynchronous planners, or overlapping observation/action are not categorically deferred; their admissibility depends on the declared interface and verified backend capabilities, not a forced Runner decision loop.

Cancellation is not rollback. An attack, consumed item, projectile, crafting job or movement can leave effects after cancellation. An action timeout with uncertain effects must not be blindly retried; query authoritative status by action ID where supported, otherwise record unknown effects.

### 11.5 Deadlines, stopping, and final evidence

Recommended first-version cutoff policy:

- Stop accepting new actions at the earliest terminal boundary: task success/failure, horizon, declared resource exhaustion, or agent stop.
- Count measured effects at or after `t0` and at or before the cutoff, excluding setup-origin effects and journal entries at/before the baseline sequence. Native sequence order resolves boundary ties where available.
- Require authoritative task effects to occur within the scoring interval. Action submission before the deadline is not enough if completion occurs after it.
- At a success/death event, use its authoritative time when comparable and within the interval; separately record detection latency.
- If the adapter only supplies poll-time evidence, declare its uncertainty. Do not silently backdate a result to a guessed crossing time.
- On ambiguous ordering that changes success, report unknown/invalid measurement rather than choosing the favorable interpretation.
- Cancel in-flight work and release controls; preserve already incurred effects.
- Seal evidence through the cutoff, including delayed delivery of earlier events with valid timestamps and completeness guarantees.
- Cleanup can continue after cutoff, but new gameplay after cutoff cannot improve the score.

A complete journal or a cutoff snapshot/readback mechanism is necessary for strict endpoint scoring. A snapshot taken later while the game continued changing is not automatically the cutoff state. If no qualified method exists, reject the strict profile or create an explicitly different diagnostic condition.

Do not carry an old `settle_sec` into the new protocol as free extra gameplay. If delayed effects are intended to count during a grace interval, its duration and rules belong to a separate task/protocol definition.

Task terminal precedence is explicit. Proposed default: forbidden player death invalidates a simultaneous success when authoritative evidence establishes the same terminal step; if order is unknowable, preserve the ambiguity. A task that intentionally allows death after completion must declare its different terminal scope.

## 12. Reset and initial-state comparability

No universal reset method guarantees bit-identical evolution across arbitrary real-time games. Require an equivalent **task-relevant starting state**, and report how strongly that claim is validated.

### 12.1 Supported reset strategies

| Strategy | Suitable circumstances | Important caveats |
| --- | --- | --- |
| Copy immutable save/world fixture | Saveable sandbox with validated load behavior | Stop/quiesce writes or use an engine-supported consistent snapshot; player/server/global state may live outside the copied directory |
| Seeded generation plus setup | Stable generator and authored initialization | Seed alone does not restore NPC AI/RNG, elapsed time, quests, inventory or pending jobs |
| Native scene/reset API | Engine can recreate actors and state | Verify all task-relevant hidden state, not only visible coordinates |
| Restart isolated local server/process plus restore | Persistent server state must be cleared | Startup cost and readiness; avoid affecting other users |
| Limited manual restoration | Exploratory integrations only | Label as manual/limited reproducibility; not automatic qualification |

Prefer a game's existing reliable strategy rather than forcing world copying everywhere.

### 12.2 Reset result and admission

Each reset produces a private receipt containing:

- game/build/mod/settings hashes;
- fixture ID/hash and reset method/version;
- intended instance/seed and observed world identity;
- actor/NPC logical-role bindings;
- health, inventory, equipment, recipes/skills/quests, location/orientation;
- relevant world time, weather, threats, cooldowns, ongoing effects/jobs;
- readiness and initial acceptance checks with tolerances;
- timestamped baseline and isolation identity.

Some values must match exactly (inventory counts, quest phase); others may tolerate a documented range (position, animation settling). Nondeterministic runtime UIDs can be rebound to logical fixture roles rather than required to be identical.

If validation fails, mark **setup failure**, not agent failure. Bounded retries before measured start are allowed only under a recorded policy; do not silently resample easier seeds. Every setup attempt and acceptance outcome remains in the manifest.

Restoring the same save is useful but insufficient: load-time simulation, rendering, scheduling, asynchronous NPC decisions and RNG can diverge. Evaluate repeated episodes over declared fixture instances/seeds; match instance schedules across agents. Repeated model runs on one map and generalization across maps are separate statistics.

## 13. Results, budgets, and reproducibility

### 13.1 Orthogonal result axes

Avoid a single ambiguous `success: false`.

| Axis | Example values |
| --- | --- |
| Admission | admitted / unsupported_configuration / invalid_configuration |
| Execution | completed / setup_failure / runtime_infrastructure_failure / interrupted |
| Task outcome | success / failure / unknown / not_evaluated |
| Measurement | valid / invalid / unknown |
| Terminal reason | goal / death / horizon / budget / agent_stop / adapter_error |
| Cleanup | completed / failed / not_needed |

A result may have authoritative native success but invalid measurement. Preserve both. A post-terminal cleanup error must not automatically erase a previously valid task outcome, but it may prevent resource reuse.

Task metrics are namespaced and carry units, definitions and evaluator versions. A game's score need not fit another game's scale.

**Do not classify ordinary agent mistakes as infrastructure failures.** Invalid action syntax, an unavailable recipe, a skill precondition failure, or an agent deciding to stop are agent/game interaction outcomes under a published policy. The world continues while permitted correction/reasoning occurs. In contrast, a broken input backend, failed reset, missing required journal, or provider outage must be recorded with its actual cause. A provider outage is not automatically a game loss or grounds for deleting the attempt: the frozen protocol specifies whether and how such episodes enter capability and reliability summaries.

Finite grace periods and retries must be explicit. Transport retries can continue within a live episode only under the declared budget and duplicate-effect policy. An uncertain mutating action is not safe to retry solely because no response arrived.

### 13.2 Accounting

Record:

- task wall time, native simulation progression and end reason;
- model/provider identity, resolved aliases, request IDs where available;
- input/output/reasoning/image usage when reported;
- model calls and all helper/subagent calls;
- retries, transport failures, backoff and tool duration;
- actual cost when pricing is available, otherwise unknown with pricing provenance;
- hardware, concurrency and relevant runtime settings.

Token counts are provider-dependent, especially for images and hidden reasoning. Never convert missing token/cost information to zero. A hard token-cap condition requires a declared enforceable accounting method; otherwise classify that capability as unsupported or use a separately named wall-time/call-budget condition. Reserve/check budget before requests where feasible and record in-flight overshoot.

In full-agent mode, the agent may use multiple models but must disclose the system and route or report all measured calls under the declared accounting contract. Fixed-scaffold results and full-agent results must not be merged.

### 13.3 Artifacts and optional logging

Required audit artifacts:

- requested and resolved configuration with hashes and versions;
- scheduled episode/attempt manifest, including unsuccessful setup attempts;
- reset/opening receipts and selected instance identity;
- observation/action timing and action receipt records;
- evidence required by the evaluator and completeness/cutoff records;
- evaluator result, validity, errors and cleanup status;
- agent/model usage and provenance sufficient for the declared evaluation mode.

Optional extras: continuous video, additional debug traces, full prompt/response content beyond required provenance. Actual agent-input frames can be required by a published audit level, even when a continuous video is optional. Disabling full dialogue must not remove action/usage records; any reduced reproducibility is disclosed.

Keep privileged evidence and agent outputs in separate access paths. Redact credentials and unrelated desktop/user content. Artifact retention and releases must respect game and asset licenses.

### 13.4 Reports and resumes

- Show scheduled, admitted, attempted, valid, invalid, unknown and unsupported counts.
- Report valid-task success together with coverage; do not hide invalid attempts to make a score look better.
- Do not count an unsupported configuration as a game loss or as a successful skip.
- Use per-game/track/profile tables. Cross-game aggregation, if later adopted, requires explicit fixed weights and coverage.
- Distinguish repetitions within an instance from independent instances when estimating uncertainty.
- Resume completed episodes by immutable condition/instance/attempt identities. Incomplete episodes restart from a fresh fixture unless exact agent+game checkpoint continuation is explicitly supported and separately identified.
- Do not selectively rerun model failures or overwrite earlier attempts. Infrastructure reruns follow a predeclared policy and preserve the original records.
- Keep development and held-out fixtures/tasks separate; freeze official tasks, protocols and evaluation policies before confirmatory testing.

Publish both task success and diagnostic progress where useful, but do not infer that a model which reaches many milestones has completed the long goal. Use equal predeclared task/instance weights rather than accidentally giving a task more weight because it has more repetitions. Show uncertainty with the declared sampling unit; a large number of repetitions of one fixture does not replace diverse instances.

When evidence permits offline rescoring, create a new result tied to the original immutable evidence and the new evaluator version. Do not overwrite the old result. If a scoring change requires evidence that was never collected, rescoring is insufficient and a versioned rerun is necessary.

## 14. Extension workflows

### Add a game

Implement lifecycle/reset/readiness, one qualified agent interface, private evidence sufficient for selected tasks, and a capability manifest. Reuse OS capture/input if compatible. Add minimal reference tasks and protocol checks; do not rewrite the common runner.

### Add a task in an existing game

Reuse a fixture and evaluator with new parameters if sufficient. Add a new evaluator or native evidence hook only when the task requires new semantics. Adding YAML cannot create engine capabilities that do not exist.

### Add a mod or environment variant

Create a pinned variant manifest with base build, mod versions/hashes/load order, settings, assets and reset compatibility. Check whether the variant changes observations, physics, recipes, timing or score semantics; qualify affected tasks/profiles. Do not assume “same game name” means the same benchmark condition.

### Add an observation/action setting

Register a new profile and supported mapping. Keep task IDs only if objective/evidence semantics remain unchanged; still use a different condition identity. Do not permit arbitrary cross-products without admission.

### Add a model

Implement a provider client with multimodal/tool features, cancellation and usage semantics; reuse the reference scaffold. Report unsupported capabilities rather than silently changing inputs/tools.

### Add a full agent

Implement the restricted episode lifecycle and usage/provenance boundary. Allow internal architecture diversity, but not hidden setup/evaluator access or extra unreported models.

## 15. Representative walkthroughs

### 15.1 Minecraft VM endpoint task

1. Resolve task, fixture, actual client/server versions and VM profile.
2. Confirm legal prerequisites and allocate an isolated display/session.
3. Restore the immutable world and player state; validate empty inventory and location.
4. Arm baseline and a cutoff-state mechanism; prepare agent without live-state access.
5. Start the measured episode and deliver public goal plus initial frame.
6. Run bounded keyboard/mouse actions while the world continues through model waits.
7. On agent stop or deadline, stop control and obtain cutoff-consistent inventory.
8. Evaluate new retained item counts, not crafting history.
9. Archive validity and usage, release inputs and close only the owned resources.

A strict cutoff inventory mechanism is a qualification requirement, not assumed from the existing eventual saved world.

### 15.2 Veloren ST contract history task

1. Admit the exact structured field/skill profile and native evidence support.
2. Restore or construct the contract fixture and validate player, giver, target and offer.
3. Arm private journal at a known sequence; exclude setup/admin effects.
4. Deliver only public task and allowed state.
5. Agent chooses ordinary skills; their bounded internal controllers operate while the world advances.
6. Evaluator checks activation, subsequent target death and attribution, return, settlement and survival.
7. Native success is latched at the task-defined final event; stop and seal evidence.
8. Missing events/unknown action effects affect measurement validity rather than being silently interpreted as task failure or success.

VM can use the same private evaluator if the game/profile combination supports the necessary evidence and ordinary acceptance semantics. An evaluator must not require one exact tool-call spelling if an equivalent legitimate action exists through another admitted interface; use authoritative effects and profile-specific intent evidence where justified.

## 16. Acceptance checks before implementing the full framework

These are measurement and engineering acceptance concerns, not completed results or a required inventory of separate unit tests. Under the later lean-testing policy in Section 25, cover relevant high-risk behaviors with a few focused tests and bounded integration checks. Do not translate this list into one file per concern, per function, or per task.

1. **Configuration:** unknown keys, mixed games, missing versions and inadmissible track/tool combinations are rejected before launch.
2. **Information boundary:** private coordinates, journal fields, admin commands and scorer errors do not enter observations/tool returns.
3. **Clock:** injected model/network delay advances relevant game dynamics and is counted.
4. **Deadline:** effects before/at/after cutoff follow explicit boundary rules; late snapshots cannot receive extra gameplay credit.
5. **Cancellation:** held controls are released; a canceled skill retains known partial effects and does not get retried blindly.
6. **Reset:** repeated restoration satisfies each exact/tolerant opening predicate; deliberate mismatches are classified as setup failures.
7. **Endpoint scorer:** initial inventory cannot earn unearned net-increase credit.
8. **Historical scorer:** crafted-then-consumed succeeds only for an acquisition/process task; traded-for-item does not masquerade as crafting.
9. **Ordering/invariants:** accept-kill-return, death-respawn, and brief region visits are classified correctly.
10. **Evidence loss:** missing journal sequences and unsynchronized cutoff evidence become invalid/unknown, not ordinary loss.
11. **Result axes:** success followed by unrelated cleanup failure preserves native outcome; preterminal adapter failure remains visible.
12. **Provider:** missing image capability or usage data is explicit, not a silent downgrade.
13. **Resume:** original attempts remain immutable, and only qualified completed cells are reused.
14. **Full episode:** one existing representative task per game/track is qualified before adding larger task catalogs.

Use small fakes or saved evidence for critical pure-logic checks, followed by bounded native smoke checks. Avoid a large mock framework, redundant unit/integration coverage, or an expensive model campaign as the first validation tool.

## 17. Mapping to the user's ten questions

| Question | Recommendation |
| --- | --- |
| 1. Shared pixels/keyboard/mouse? | Shared OS/display backend plus window/control profile and game compatibility checks; not universal zero-adaptation |
| 2. One game per run? | Yes for v1; same variant/profile/agent cell too; launcher accepts multiple run configs |
| 3. Which guide/frame/state/tool settings belong in 3.2? | ExperimentConfig selects versioned game, interface and knowledge profiles. Profiles define resolution/cadence, field allowlists, tools and guide access; fixed information does not mean unrestricted internals |
| 4. Evaluator in interface layer or task layer? | Task/evaluation logic over a private game evidence interface; game-specific implementation can live under that game's directory |
| 5. Three layers and repetition ownership? | Keep TaskConfig/ExperimentConfig/launcher. Repetitions and instance schedules belong in ExperimentConfig, while launch/output operations belong in the launcher |
| 6. Before/after sufficient? | For endpoint goals, yes; provenance/order/invariants need history or trusted persistent summaries. Online arrival detection is itself evidence collection |
| 7. Same initial state? | Game-specific reset plus task-relevant acceptance checks; save copying is one strategy, seed alone is not enough |
| 8. Names? | Visual-Motor (VM), Structured-Tool (ST); versions and permissions remain explicit |
| 9. Directory structure? | Task/experiment YAML under config/; game-specific implementations/assets under game/<game>; Agent code under agents/; shared runner/contracts/backends/utilities under core/ |
| 10. Missing issues? | Clock/cutoff, cancellation/partial effects, privileges, capability admission, budgets, guide/helper costs, failure validity, reset drift, isolation, provenance, aggregation and freeze policies |

## 18. Small implementation path and deferred choices

Recommended sequence after discussing this draft:

1. Follow the bottom-up, reuse-first sequence in Section 24; exact method signatures remain to discuss.
2. Extract minimal game and Agent contracts alongside representative existing implementation paths; test them without launching expensive model runs.
3. Wrap Minecraft launch/reset/snapshots and VM/ST interfaces, preserving existing behavior except for explicitly reviewed changes.
4. Adapt Veloren to the same external contract, retaining native evidence and measurement validity.
5. Connect config resolution, autonomous-Agent orchestration, episode artifacts and accounting.
6. Qualify timing/reset/scoring and integrate several selected mainstream agents before considering the initial deliverable complete.

Deferred decisions for the next discussion:

- exact track/profile permissions (VM/ST terminology is now confirmed);
- exact canonical ST fields and fixed skills per game;
- whether per-actor action overlap is allowed outside the reference scaffold;
- knowledge/guide conditions and helper-agent policy;
- observation delivery/rate bounds and action-duration bounds;
- cutoff precision and any intentionally allowed grace condition;
- budget/accounting definitions and terminal precedence;
- reset tolerance and instance schedule;
- official reporting/coverage requirements;
- minimum artifact retention and precise supported Linux/display configurations (Linux-first is confirmed).

These choices are listed for review; no immediate answer was requested from the user. This design deliberately avoids a third game, a general temporal DSL, an arbitrary plugin loader, a mandatory distributed service architecture, or a universal engine-state schema.

## 19. Validation performed on this draft

- Parsed all four fenced YAML examples with the existing GameAgentVisual environment's YAML library; the default shell Python lacked that dependency, and no dependency was installed or changed.
- Checked the example ExperimentConfig's task, game variant, interface profile, and track references for internal consistency.
- Checked that both example tasks' death terminal rules declare corresponding death evidence.
- Checked that local Markdown reference targets exist and all ten questions appear in the response mapping.
- Confirmed the report is saved in the survey directory. This directory is Git-ignored; persistence does not mean the report was committed.

These checks validate document syntax and selected design relationships only. No executable schema validator, proposed adapter/profile/evaluator, gameplay behavior, runtime timing, reset fidelity, or model score was validated.

## 20. Baseline agents: implementation, repository ownership, and publication

Added after the initial architecture review on 2026-10-21. This section recommends an integration and release strategy; it does not select particular third-party agents or claim they have been reproduced.

### 20.1 A baseline result requires an executable evaluated system

A related-work citation does not require reimplementing that work. A baseline score produced for LiveQuestBench does require an executable agent implementation or accessible system, an admitted interface, and an actual run under the reported condition. Do not import a score from a different benchmark and present it as a LiveQuestBench result.

Use the least invasive viable route:

| Available material | Recommended action | Result label |
| --- | --- | --- |
| Licensed, usable official code | Pin and reuse it; add a thin adapter | Official implementation with documented adapter |
| Official code requiring changes | Keep upstream provenance; release permitted patches/fork and adapter | Adapted implementation, with substantive changes disclosed |
| Paper but no usable implementation | Reimplement only if justified and sufficiently specified | Our reimplementation of the method |
| Inaccessible model/system or insufficient details | Retain as related work or explicitly unavailable comparison | Not evaluated; never fabricate a baseline score |

An adapter normally translates task delivery, observations, action calls, stop/cancel signals, usage and output artifacts. If integration replaces the controller, memory policy, skills, or timing assumptions, it is no longer merely transport adaptation. Reproducing a method's design does not establish reproduction of its original published results.

### 20.2 Recommended repository strategy for the first release

Keep **benchmark-owned reference agents, thin third-party adapters, exact experiment configurations, and reproduction instructions in this repository**. Keep substantial third-party implementations in their upstream repositories or isolated optional installations whenever possible.

This is a hybrid arrangement, not a choice between copying every agent into the benchmark and creating a separate repository for every baseline.

- `agents/reference/`: small benchmark-maintained reference scaffold(s).
- `agents/adapters/`: optional adapters for external full agents.
- `agents/llm/providers/`: model API clients used by the reference scaffold; these are not full-agent implementations.
- `config/<game>/experiments/`: frozen baseline configurations, including agent/model revisions and all declared budgets.
- Third-party source/checkpoints: pinned external dependencies with acquisition instructions, hashes, and license records; optional installation rather than mandatory benchmark-core dependencies.

Do not install every baseline framework merely to use the benchmark or run one agent. Optional dependency groups are suitable where dependencies coexist; conflicting frameworks may need separate virtual environments, containers, or external processes. An external process alone does not supply the access isolation required by Section 4.3.

A dedicated agents repository becomes useful when:

1. an agent is a separate research contribution with its own training and release cycle;
2. dependency size or ownership makes independent maintenance materially easier;
3. external teams want to maintain agents without changing benchmark internals.

It is not required merely because a baseline is a separate algorithm. If a first-party baseline is moved out later, keep its paper-reproduction configuration and compatible revision reference discoverable from the benchmark.

### 20.3 Dependency direction and external integration

The intended direction is:

```text
benchmark runner -> stable agent-session contract
reference agent -> public observation/action contract + model client
external adapter -> public contract + upstream agent
game adapter -> game implementation + benchmark contracts
```

The core runner does not import upstream agents unconditionally, and game adapters do not import agent-specific planners. An explicit registry can select optional adapters when requested.

For an external agent repository, offer a lightweight public contract/client or a documented process protocol. It need not import the benchmark's full game stack, private evaluator, or fixtures. The benchmark remains the authoritative owner of initialization, budgets, permitted actions, termination and scoring.

Prefer a persistent episode session over a single opaque `run()` returning a self-reported score. The host must be able to observe/account for interactions and stop the agent. This need not force a fixed one-model-call/one-action architecture.

### 20.4 Compatibility and scientific fairness

Sharing a function signature does not make agents comparable.

- A pixel-only agent cannot be silently given internal state to make an integration work.
- An agent requiring semantic navigation cannot be called a raw-motor baseline without documenting a changed controller or a different action profile.
- Benchmark-supplied skills are part of the fixed interface. Extra agent-owned skills/controllers are part of the complete system and must use only permitted observations/actions.
- A system designed around paused inference cannot be advertised as unchanged when ported to continuous time. Report the adaptation and any separately run paused diagnostic.
- All planners, controllers, guide helpers and extra models contribute to resource accounting.
- Lack of access to proprietary weights or required inputs can make a cell unsupported; it does not justify a silent substitute.

For model comparison, keep the scaffold, tools, memory and guide policy fixed. For full-agent comparison, preserve legitimate architectural differences, but fix or explicitly stratify environment access, task distribution, timing and resource conditions. Do not weaken the benchmark's main protocol to make every historical framework fit.

### 20.5 Minimal baseline portfolio before broad integrations

Suggested categories, not a finalized experiment plan:

1. A small reference agent for fixed-scaffold model comparison, qualified separately for each admitted track.
2. A planning/memory-capable variant for a targeted scaffold ablation, without assuming it will outperform the simple reference.
3. A small number of relevant external full-agent systems selected after checking actual interface and code compatibility.
4. Scripted/reference behaviors for solvability, reset and timing diagnosis. Privileged oracle runs are labeled diagnostics, not ordinary leaderboard entries.

An agent with a new name is not necessarily a distinct scientific baseline. Conversely, reproducing every related framework is not required for a useful benchmark. Selection should test the central planning/execution claim and provide representative comparisons within the feasible budget.

### 20.6 What must accompany the paper's baseline results

For each evaluated baseline, retain and release where permitted:

- upstream repository, exact revision and license; checkpoint/model identity;
- adapter version, patches and a clear distinction between reused and reimplemented components;
- dependency locks or equivalent version records and supported setup instructions;
- prompts, guide versions, scaffold/memory/skill settings and experiment configuration;
- seeds/instances, repetitions, retry policy, timing and resource budgets;
- measured results, coverage, invalid/unsupported cases and sufficient audit artifacts;
- known deviations from the original work and limitations of reproduction.

Publicly viewable source without a reuse license is not automatic permission to copy or redistribute it. Preserve notices and comply with component licenses. Do not redistribute restricted checkpoints, proprietary game assets, secrets, or credentials. If full reproduction depends on an unavailable external service, state that limitation even when the adapter itself is open source.

**First-release recommendation:** same-repository reference agents and thin adapters, external pinned third-party implementations, and a stable public integration contract. No new repository or baseline implementation is created by this proposal.

## 21. Episode artifacts, model-call instrumentation, and terminology

Discussion update: 2026-10-21. The output structure requested by the user is retained in principle. At 11:14 the user approved the terminology, including VM/ST. Integration defaults and exact schema fields remain proposals; illustrative identifiers have been normalized without changing implementations or historical results.

### 21.1 Output root and per-episode directories

The visual project's inspected branch currently uses `<output>/<task-id>/exp<N>`, with per-trial runtime/result records and `results/evaluation.json`. Reuse the task-grouped design. Prefer a stable task ID over a display title, and recommend `episode_0001` for new output to avoid confusing one episode with the entire experiment.

```text
<root_dir>/                         # One resolved experiment execution
  manifest.json                    # Run ID, resolved condition, planned schedule
  config.resolved.yaml
  summary.json
  report.md
  minecraft.obtain_pickaxe/
    episode_0001/
      manifest.json                # Task/instance/repetition/attempt identities
      config.resolved.yaml         # Complete condition or immutable references
      result.json                  # Authoritative episode result and validity
      evaluation.json              # Evaluator details and evidence references
      usage.json                   # Aggregated model/resource usage and coverage
      logs/
        agent.jsonl
        runtime.jsonl
        model_calls.jsonl
      observations/
      actions.jsonl
      evidence/                    # Private baseline/cutoff/events as required
      recordings/                  # Optional video
    episode_0002/
```

This is a proposed output convention, not a claim that all listed artifacts are mandatory for every task. Required audit records remain governed by Section 13; videos and full conversation contents follow the retention policy. Reusable large assets need not be copied into every episode if immutable references and acquisition information suffice. Shared manifest/evidence files must remain immutable while dependent results exist.

The hierarchy is task-grouped, not agent-grouped: one root must identify one resolved experiment execution. Repeating a launch creates a new run identity rather than overwriting prior results. If one launcher invocation executes multiple experiment configs, place each in a unique `<root_dir>/<run-id>/` subtree; record that mapping in a group manifest. This avoids task-name collisions across agents, profiles and games.

Each episode directory represents one actual isolated attempt, including attempts that fail before measured start. Record `task_id`, `instance_id`, `repetition_index`, `scheduled_episode_id`, `attempt_index`, and `episode_id`; do not derive identity solely from its folder number. A permitted infrastructure retry gets a new directory linked to the same scheduled episode. Preserve the failed attempt and follow the declared retry/denominator policy instead of counting it as another planned repetition or overwriting it.

If retaining `exp_1` is preferable for familiarity, it can name the same unit, but document it as an episode directory. Legacy `exp1` outputs should remain readable without mass renaming.

Validate filesystem-safe task IDs and exclusive output ownership. Refuse accidental reuse of existing output unless explicit resume validation succeeds. Resume must validate condition hashes and completed manifests; directory existence alone is not completion. Partial/interrupted records remain distinguishable from finalized results. Only the owner process writes the final record atomically after required evidence/result checks; cleanup status is retained.

Artifact storage is not an agent workspace. Private evidence and other trials' logs must not become accessible to the running agent merely because files share an output root.

### 21.2 Common model client for first-party agents; common accounting for all

The inspected visual `BaseLLMClient` already separates model requests from agent-owned history/tool execution/persistence. It has `chat`, a provider request implementation, and an `on_request` callback reporting attempt duration, outcome and usage. This is useful prior art, but the callback alone is not a complete conversation or multi-agent accounting ledger.

Recommend two contracts:

1. A common **ModelClient** for benchmark-maintained reference agents and integrations that can accept it.
2. A common **ModelCallRecord** for all admitted systems, irrespective of their internal SDK.

Possible external integration paths:

| Agent capability | Integration route | Qualification needed |
| --- | --- | --- |
| Accepts an injected client/model callable | Wrap the common client in the signature expected by that agent | Preserve messages, tool schemas, streaming and cancellation semantics |
| Uses a configurable compatible API endpoint | Optional gateway/proxy with the expected wire protocol | Verify endpoint/features; an OpenAI-compatible label alone does not guarantee compatibility |
| Exposes native callbacks or request hooks | Keep its SDK and export normalized call records | Account for internal retries, subagents and model routing |
| Exposes only summary logs or inaccessible remote execution | Import explicitly agent-reported usage, or classify coverage as partial/unavailable | Do not claim enforced token/cost caps or complete conversations |

Do not build a universal gateway before concrete integrations justify it. Start with the first-party client and a small telemetry interface; use per-agent wrappers where needed. Not all mainstream frameworks can be presumed compatible without inspecting their versions and extension points.

Client wrapping must not silently change reasoning settings, tool semantics, supported media, prompt serialization, caching, streaming or retry policy. Preserve provider-specific replay fields where required. Reject unsupported capability combinations, rather than stripping unsupported inputs. A wrapper observes and normalizes transport; it does not own the agent's planning loop.

Each physical request attempt should have a stable request/attempt identity and logical-call/parent identifiers, so adapter, gateway and provider records can be joined without double-counting. Include episode identity, agent component/model role, provider/model version, send/first-output/completion timestamps where available, outcome, retries, reported usage, cost basis and accounting source. Distinguish input, output, cached and reasoning tokens according to provider definitions; do not add overlapping categories blindly.

Record usage provenance such as observed provider/gateway, exported SDK hook, agent-reported or estimated, together with coverage and missing fields. SDK-internal retries and failed/cancelled requests can incur cost; missing usage is unknown rather than zero. Provider pricing estimates, subscription billing and actual invoice cost are not interchangeable.

Store request/response content or references only under the declared retention policy; redact secrets and preserve tool-call ordering and image references as permitted. Hidden model reasoning that the provider never returns cannot be logged or reconstructed. A chronological model-call ledger can represent multiple independent conversations; do not flatten a multi-agent system into an invented single chat.

Uniform accounting schemas do not prove completeness. Hard token/cost limits require a controllable, sufficiently observable request path and explicit treatment of in-flight overshoot. External systems that can bypass instrumentation cannot be certified under such a cap based only on self-reported totals. They may be admitted to an explicitly different wall-time/partial-accounting condition if the study allows it. Gateway overhead and model-network latency count during continuous-live execution and must be disclosed.

### 21.3 Recommended vocabulary

| Term | Meaning | Suggested identifier |
| --- | --- | --- |
| Task | Versioned objective, fixture family, evaluator and terminal rules | `task_id` |
| Task instance | Concrete admitted world/seed/parameters | `instance_id` |
| Episode | One actual isolated task attempt, potentially multi-stage | `episode_id` |
| Repetition | Planned repeated evaluation of an instance and condition | `repetition_index` |
| Attempt | Original or retried execution for a scheduled episode | `attempt_index` |
| Experiment | Tasks/instances/repetitions plus one agent and one declared condition | `experiment_id` |
| Run | One execution of a resolved experiment | `run_id` |
| Run group | Optional launcher grouping of multiple runs | `run_group_id` |
| Track | High-level observation/action access category | `track` |
| Profile | Versioned concrete interface or knowledge configuration | `profile_id` |
| Variant | Pinned game build/mod/settings combination | `variant_id` |
| Agent | Complete decision-making system | `agent_id` |
| Model client/provider | Model-call abstraction/service adapter, not the full agent | `provider`, `model_id` |
| Tool | Callable interface exposed to an agent | `tool_id` |
| Skill | Behavior implemented by a controller or macro, potentially behind a tool | `skill_id` where needed |
| Action | A submitted game-control command or invocation | `action_id` |
| Evaluator | Interprets authoritative evidence into outcome/metrics | `evaluator_id` |
| Evidence | Private scoring observations, events or sufficient summaries | `evidence` |
| Fixture | Initial-state assets and initialization recipe | `fixture_id` |
| Guide | Allowed control reference or declared static knowledge | `guide_id` |

Use **TaskConfig** and **ExperimentConfig** to match the `tasks/` and `experiments/` subdirectories under `config/<game>/`. Earlier discussion called these roles TaskSpec and RunSpec; they are aliases for the same two configuration roles, not extra layers. A resolved execution manifest is not another user-authored experiment.

**Tool versus skill:** tool describes the callable interface; skill describes the behavior. A keyboard primitive can be exposed through tool calling, while a navigation tool may invoke a closed-loop skill. Thus “tool calling” alone does not distinguish the two benchmark tracks.

Track names approved by the user at 11:14:

- **Visual-Motor (VM)** / `visual_motor`: images plus bounded motor controls.
- **Structured-Tool (ST)** / `structured_tool`: allowlisted structured observations plus a fixed, versioned tool set, including declared skills.

Use “structured,” not “structure,” for the observation adjective. ST emphasizes the public API and includes both primitive actions and longer skills; the earlier Structured-Skill proposal emphasized skill abstraction. The approved name does not substitute for a full action profile or broaden the fixed-tool and hidden-state permissions.

Task/Instance/Episode/Experiment/Run and the two track labels are now agreed. Exact file names and schema fields remain design details. No code or historical artifacts are renamed by this discussion.

## 22. Configuration ownership versus game-specific organization

**Historical layout discussion:** the configuration/implementation separation remains agreed, but task-first subdirectories and task fixtures under `game/` below were refined at 11:43. Use Sections 4.3 and 24 for the latest game-first configuration/resource layout.

User update at 11:14: the user asked whether per-game configuration should be colocated with each game's implementation. **At 11:19 the user accepted the configuration-centric recommendation below.** The detailed game-module breakdown in Section 23 is the next design discussion, not yet a frozen implementation.

Both layouts are legitimate. They optimize different navigation tasks:

- `game/<game>/config/` groups everything a game-integration maintainer needs.
- `config/tasks/<game>/` and `config/experiments/<game>/` group the declarative evaluation resources users inspect and customize.

Being game-specific is a compatibility property, not a requirement to share a directory. A task's `game` field, typed parameters and capability admission establish its game association independently of its filesystem location. Conversely, a YAML file is not automatically user-selectable experiment configuration.

### Recommended boundary

Retain the currently proposed configuration-centric layout for this project:

| Resource | Recommended home | Reason |
| --- | --- | --- |
| Task definitions | `config/tasks/<game>/` | Evaluators and fixtures are selected/parameterized without changing game code |
| Experiment definitions | `config/experiments/<game>/` | They select an Agent, tasks, interface and schedule; the game should not own the experiment's model choices |
| User-selectable interface/knowledge profiles | `config/profiles/<game>/` when reuse warrants it | Declarative choices constrained by the adapter's supported capabilities |
| User-selectable game/mod combinations | `config/variants/<game>/` when needed | Select pinned artifacts/settings rather than implement them |
| Adapter capabilities and internal defaults/templates | `game/<game>/` | Describe supported implementation, not arbitrary claims users may enable |
| Mod code, skills, evidence readers, evaluators | `game/<game>/` | Executable game-specific behavior |
| World fixtures, guide content, asset manifests | `game/<game>/` or immutable external asset storage | Material referenced by task/profile configuration |

For example, a task config selects a Minecraft inventory evaluator and an item threshold, while the game directory implements the inventory reader and evaluator. A variant config may select a Mod version; it does not contain that Mod's code. Do not maintain duplicate authoritative definitions under both directories.

The rationale is **declarative evaluation plan versus capability implementation**, not a promise that game code never changes. Game upgrades, bug fixes and new evidence requirements will change adapters too; all relevant components need versioning.

No new configuration tiers are required: start with tasks and experiments, and extract profiles/variants only when useful. External user configuration remains supported under Section 5.6 regardless of the bundled directory choice. External game plugins can later ship example configuration in their own distribution; catalog registration and immutable identities matter more than forcing contributors to mirror this repository's paths.

If a future project prioritizes independently distributable, self-contained game packages, colocating default task/profile resources with each game would also be defensible. Do not support both as silently competing lookup roots now. Keep one authoritative bundled convention, explicit external references and conflict rejection.

## 23. What a game integration provides

**Historical responsibility breakdown:** the subsequent discussion removed any requirement for separate adapter/runtime/manifest files. BaseGame and concrete game classes provide the required interfaces, and core alone orchestrates the Episode. Read Sections 4.3 and 24 for the current simplified layout. The permission and responsibility distinctions below still apply without separate directories.

Discussion at 11:19: the user proposes a per-game `setup.sh` and requests a concrete explanation of the remaining directories. Treat the earlier directory tree as a responsibility map, not a requirement to create every folder.

### 23.1 Responsibility and lifetime

| Component | Purpose | Typical lifetime | Boundary |
| --- | --- | --- | --- |
| `setup.sh` | Install/check supported prerequisites and obtain/build pinned, legally distributable components | Explicit environment provisioning | Not an implicit install on every episode; no credentials or proprietary binaries bundled without permission |
| `README.md` | Explain prerequisites, supported platforms, setup, configuration and known limitations | Human-facing integration documentation | Not automatically part of the agent's allowed guide |
| `manifest.yaml` | Declare adapter identity/version and supported builds, tracks, profiles, reset and evidence capabilities | Admission before launch, verified against actual environment | Describes implementation capability, not a user assertion that an unsupported feature exists |
| `adapter.py` | Implement the common game contract and compose the modules below | One provisioned game/session context | Thin integration facade; not a second benchmark runner or a catch-all implementation |
| `runtime/` | Launch/connect, isolate resources, reset, readiness, start/cutoff coordination and cleanup | Session and episode lifecycle | Only manages owned resources; does not perform agent planning or decide task score |
| `observations/` | Produce agent-visible images or allowlisted state, including projected action results | During agent interaction | No evaluator-only journal, hidden coordinates or admin access |
| `actions/` | Validate/execute allowed controls/tools, report receipts, bound duration, cancel and release inputs | During agent interaction | No setup teleport/spawn operations disguised as gameplay tools |
| `evidence/` | Collect private state, authoritative events/counters, identities, completeness and cutoff records | Armed before start through evidence sealing | Records what happened; does not choose the task's success thresholds |
| `evaluators/` | Interpret evidence using the selected task rule and parameters | Online terminal checks where supported and final evaluation | Read-only measurement; does not act to make the task succeed |
| `fixtures/` | Store or reference initial-state templates, maps and initialization recipes | Reset inputs | Immutable source assets, not live mutated episode directories or TaskConfig copies |
| `guides/` | Public controls and optional game knowledge content | Selected by knowledge profile | No private fixture solutions exposed implicitly |
| `mods/` | Game-side plugins/patches for gameplay or measurement integration | Build/startup under a pinned variant | Distinguish gameplay changes from instrumentation; keep licenses and hashes |

A script is an entry point, not a required platform implementation. If Windows or another platform is supported later, use a suitable setup entry point or a shared implementation with a shell wrapper. Installation must be explicit, fail clearly, check versions and avoid disturbing unrelated environments. Account/entitlement preparation and source-license requirements remain documented manual prerequisites where necessary.

### 23.2 Examples that clarify overlapping-looking names

**Manifest versus profile:** the manifest declares that an adapter supports a particular image backend or evidence stream. A profile selects allowed observation fields and tools among those capabilities. Runtime checks establish that the installed build actually provides them. Neither file can manufacture a capability.

**Adapter versus runtime:** the runner calls the adapter's reset contract; the adapter delegates to runtime to restore a fixture, start the owned process if needed and validate readiness. The adapter returns the standardized reset receipt. Common scheduling, budgets and report aggregation remain in core.

**Fixture versus TaskConfig:** a fixture provides a map/save or a deterministic setup recipe. A task selects that fixture plus supported initial-state parameters, a public objective and an evaluator. One fixture can serve multiple tasks; every task does not need a new world file. Runtime materializes a writable episode copy or constructs a fresh scene and checks the resulting opening state. Large immutable assets may be stored externally by hash.

**Observation versus evidence:** both may derive from the same native bridge, but use separate projections and access paths. For VM, the agent sees pixels while the private evaluator can read inventory or death events. For ST, an allowed own-inventory field may appear in both channels, but the evaluator's complete journal remains private. Share low-level parsing internally where appropriate without exposing the unrestricted reader to agents.

**Evidence versus evaluator:** an inventory reader reports an authoritative inventory; an evaluator compares it with the task threshold. A contract journal reports acceptance, target death and reward insertion; an evaluator checks their identity, order and task-specific constraints. Evidence completeness itself is evaluated as measurement validity, not silently treated as success or failure.

**Mod versus bridge:** a Mod may emit authoritative events or implement a required game-side control endpoint. Host-side `evidence/` or `actions/` consumes that bridge. An existing engine API can make a new Mod unnecessary. A game modification does not automatically make its private endpoints agent-accessible.

### 23.3 Motor controls, tools, and internal skills

`actions/motor.py` is the VM-facing game binding: key/control configuration and any qualified mechanical mapping. Reuse `core/backends/` for OS screenshot/input transport. Do not copy an X11 implementation into every game or claim the existing Veloren native visual interface is already equivalent to OS input.

For the ST callable surface, prefer `actions/tools/` as the next proposed refinement of the earlier `actions/skills/` layout. Its tools may be primitive actions or execute a multi-step controller. A separate `skills/` directory is optional only when substantial reusable internal controllers justify it; it is not a required peer folder and is not the track name. A tool that reads public state must pass the same observation whitelist as the regular observation channel.

Tool definitions include schemas, permitted information, duration, termination/cancellation and public result semantics. Setup commands remain private in runtime or its initialization helpers, even if they use the same underlying bridge.

### 23.4 Minimal first integration and one episode walkthrough

The minimum is a supported install path, a capability declaration, a game adapter providing lifecycle and one agent interface, a fixture/reset validator, and sufficient evidence/evaluation for one selected task. Guides should supply the controls needed by that interface. A Mod, advanced skill library, separate native source tree, and both tracks are not mandatory for every game.

Start small: `runtime.py`, `observations.py`, `evidence.py`, and a compact action/evaluator module are legitimate instead of directories. Split modules when concrete complexity or reuse justifies it. Keep the responsibilities stable without imposing empty scaffolding.

Example flow:

1. User explicitly provisions the environment using the supported setup entry point.
2. Launcher resolves an ExperimentConfig and checks the manifest, installed build and task requirements.
3. Core allocates an episode; adapter/runtime restores or constructs the chosen fixture and validates the opening.
4. Private evidence collection is armed; measured start and agent task delivery follow the timing contract.
5. Agent consumes projected observations and submits permitted actions; the game continues during reasoning.
6. Private evidence supports terminal monitoring and a cutoff-consistent final view.
7. Evaluator produces outcome, metrics and validity; core records the episode artifacts.
8. Runtime releases controls and cleans up owned resources; failed cleanup is recorded separately.

This update clarifies ownership only. No installation, directory scaffolding, game modification or runtime qualification was performed.

## 24. Consolidated working direction before bottom-up implementation

Consolidates the discussion from 11:26 onward, retained and reviewed for the user's **12:29** archive-update request. This section takes precedence over earlier conflicting module/layout/reference-controller proposals. Section 25 adds the subsequent testing policy. These sections do not freeze unresolved method signatures, limits or evaluation policies, and do not authorize implementation in the documentation-update turn.

### 24.1 Confirmed requirements and remaining proposals

**Explicitly confirmed by the user:**

- Core/Benchmark owns the complete Episode lifecycle. Games provide executable operations, not independent Episode managers.
- Snapshot acquisition is implemented by each game; core calls it at the appropriate boundaries and supplies output locations. Evaluators interpret the saved evidence.
- Agents run autonomously in both VM and ST. Benchmark does not prescribe their internal reasoning/observation/action loop.
- Each episode initializes Agent state anew, following the existing Minecraft projects.
- Linux is the initial platform; several mainstream agents are intended for the initial deliverable, with more added later.
- Implementation should primarily reuse GameAgentResearch and GameAgentVisual, adapting Veloren appropriately rather than rebuilding all three.
- This discussion is now to be archived; bottom-up implementation will be considered next.

**Latest working proposals, not separately frozen requirements:**

- `game/base_game.py`, concrete per-game `game.py`, and `agents/llm/` rather than a mandatory adapter/runtime/manifest hierarchy.
- `config/<game>/{tasks,experiments,fixtures}`, with profiles/variants only as useful.
- On-demand Agent capture with independent periodic video recording, retaining current Minecraft behavior.
- The exact method names, capability-return format, tool package shape and output filenames.

Agent autonomy does not authorize bypassing the public interface, time/budget limits, private evidence restrictions or terminal shutdown. Reference-scaffold scheduling is Agent behavior, not a Runner requirement.

### 24.2 BaseGame, concrete games, and model-client ownership

A concrete `MinecraftGame` or `VelorenGame` implements the BaseGame contract and may compose helpers. Do not put all observation/tool/evaluator code in a single class, but do not add modules that only forward identical arguments either.

BaseGame defines operations and shared behavior, not a game-name switch or the experiment loop. Each live object binds to an isolated game session; avoid global mutable state shared across concurrent episodes.

The distinction previously called adapter versus runtime is:

- **Adapter:** the role of translating a game's mechanisms into the public benchmark contract. The concrete game class already has this role.
- **Runtime:** optional internal code for processes, connections, saves and resets. If later extracted, it is composed by the game class, not another orchestrator or a required base class.
- **Manifest:** optional serialization of supported capabilities. Initially the game class can describe them; do not maintain a redundant YAML and class definition that disagree.

The runner may depend on `game/base_game.py` without importing every concrete game. Keep that base independent of the runner. Agent-facing handles expose only allowed observation/action operations, not the complete game object's reset, snapshot or administration methods. A narrow object alone is not a security boundary for untrusted code; actual process/filesystem/network permissions must match the claimed access condition.

`agents/llm/base_client.py` defines the first-party model abstraction; `agents/llm/providers/` handles provider-specific requests. Core owns normalized accounting records, aggregation and enforcement where observable. External agents can use adapters/hooks rather than inheriting our client, with explicit accounting coverage. This preserves the integration alternatives in Section 21.

### 24.3 Game-specific configuration and assets

The user's island-map example clarified two independent classifications:

1. **Asset versus parameter:** a saved island world is an asset; its ID/path is a reference; seed, radius and initial inventory are parameters.
2. **Configuration versus implementation ownership:** task-scene assets can belong with evaluation configuration even though they are not small YAML files.

Consequently, the latest proposal places an island fixture alongside the game's task definitions:

```text
config/minecraft/
  tasks/obtain_pickaxe.yaml
  experiments/vm_reference.yaml
  fixtures/island_v1/
    fixture.yaml
    world/                       # Optional local immutable asset
```

An external immutable asset reference with a hash can replace `world/`; no commitment is made to distributing proprietary or large content in Git. A generated fixture may contain only an initialization descriptor, with generation/load code in the game implementation. A launcher is the mechanism, a seed is one input, and neither is a complete starting state.

The dependency is task -> fixture/parameters -> game initialization implementation. Game versions, Mod requirements, scene schema and initial acceptance checks still constrain compatibility. Source fixtures are never the writable live world. Instance parameters, player state, quests/NPCs, time/weather and load-time drift must be validated where relevant. Equal files or equal seeds do not promise equal trajectories.

External configurations/fixtures remain supported. Resolve explicit paths relative to the declaring file, preserve hashes and reject ambiguous identifiers. Configuration storage is private to the harness where it contains hidden task details; it is not automatically an Agent workspace.

### 24.4 Snapshot implementation and invocation

**Agreed ownership: core decides when; game implements how; evaluator interprets what it means.**

| Responsibility | Owner |
| --- | --- |
| Declare a common snapshot operation | BaseGame contract |
| Select before/after boundaries and episode destination | Core runner |
| Flush/read/copy the appropriate state for a specific game | Concrete game implementation |
| Reusable file copy/hash primitives | Shared helpers, if actually useful |
| Record failure, timing, identity and evidence status | Core plus game snapshot receipt |
| Score the retained task evidence | Evaluator |

An operation such as `save_snapshot(destination)` is illustrative, not a finalized signature. Avoid defining a universal whole-world serializer. A game snapshot may be a saved world, database, structured state export or a bundle of relevant evidence. Its receipt should make the actor/session, state scope, capture interval/native boundary, content identity and validity limitations clear.

Before must represent the **actual initialized episode state**, not merely the unmodified asset selected by TaskConfig. After must represent the **intended scoring cutoff**, not arbitrary later gameplay. A snapshot operation may need native readback, coordinated save, quiescence or a boundary snapshot followed by later disk serialization. Core requests the boundary; the game supplies and reports the supported mechanism. The fact that disk writing finishes later need not change an already captured state, but a later live read is not the same thing.

Agent stop does not stop the world. Likewise, canceling an Agent can close a bridge needed for final evidence, as the existing structured runner's comments explain. Therefore do not hardcode "destroy Agent and game, then collect state." Coordinate input termination, evidence boundary and connection lifetime so the required readback survives. Detailed ordering depends on the game's capabilities and must not grant unreported extra gameplay.

Retain Minecraft's established `world.before` / `world.after` approach as the starting implementation. Core need not understand its directory format. Other games need not create Minecraft-like directories; standardized metadata can refer to game-specific artifacts. Snapshot failure must be explicit and cannot be interpreted as an empty inventory or ordinary task loss.

Snapshots are run artifacts, not modifications to configuration fixtures. A scoring snapshot need not be restorable, and a restorable save may still omit evidence needed for a particular score. Declare these capabilities separately.

### 24.5 Start with before/after; retain necessary history

The user has not yet settled a general event/evaluator API. Do not require a large EvidenceBundle implementation or full event system before working endpoint tasks.

Start from existing inventory/structure evaluators and before/after evidence. Keep an extension point for task-specific events or trusted counters. Do not delete Veloren's existing contract/death/contribution/reward evidence just to force identical storage formats.

Examples retained from the discussion:

- Obtain and keep a new item can be an endpoint/delta objective.
- Proving crafting rather than looting needs authoritative production evidence or validated exclusion of alternative sources.
- Death/respawn, visit-and-return, and contract ordering require history or a trustworthy persisted summary.
- "Stop on arrival" still needs an online arrival detector.

Precise cutoff and any `settle_sec` treatment remain to reconcile against current code. The existing structured runner waits before final capture; its rationale must be checked and any change explicitly versioned. An eventual save cannot be assumed to satisfy an exact earlier cutoff.

### 24.6 Capture and recording: verified distinction

Static source inspection of GameAgentVisual's `xianya/init_mincraft` branch established:

- The reference Agent calls observation before its model requests as its own policy.
- `session.observe()` invokes a fresh `MinecraftCapture.capture()` read.
- `WindowRecording.start()` creates its own MinecraftCapture and an asynchronous recording loop.
- The recorder waits approximately `1/fps`, performs capture (in a worker thread in its loop) and writes to FFmpeg.
- The two consumers share the implementation and target window, **not one capture object or cached frame stream**.
- Current defaults are 10 FPS, with configurable range 1-60. Actual rate depends on capture/write/scheduling overhead. No historical 30-FPS run was established by these source checks.

Recommendation: retain on-demand Agent capture and independent periodic recording for v1. It allows recording to continue while the Agent reasons and lets Agent capture work with recording disabled. New window readback does not prove a newly rendered engine frame; preserve timestamps and do not claim zero latency.

A shared periodic frame producer is an alternative if measured overhead or streaming agents justify it later. It would require explicit frame age, buffer/drop rules, and recording-independent producer lifetime. Neither capture design makes world progression conditional on observation requests.

This recommendation does not prescribe when external Agents must use a frame or how many model calls they make per observation.

### 24.7 Initialization, baselines and bottom-up implementation

Each episode starts with fresh mutable Agent state: history, transient plans and mutable per-episode memory must not leak from previous attempts. A fixed pretrained model or declared frozen skill library is not erased. The implementation mechanism can be a new session/process or an equivalent verified fresh instance; the requirement is state isolation.

Linux-first narrows platform work but does not automatically certify every Linux display backend. Reuse the qualified X11 path initially where appropriate, and document unsupported combinations.

The intended initial system includes several mainstream agents. A single reference Agent can bootstrap engineering, but is not the entire requested baseline deliverable. Exact frameworks, compatible tracks, checkpoint/code availability and adapter fidelity remain to select. Preserve the upstream/reimplementation distinction and all helper-model accounting.

Proposed bottom-up sequence for the next implementation discussion:

1. Identify the smallest BaseGame/Agent-facing/snapshot interfaces from existing Minecraft code, without redesigning every method in advance.
2. Wrap one Minecraft fixture/reset/snapshot path and verify before/after semantics with a non-model reference behavior.
3. Reuse VM capture/input/recording and ST tool infrastructure, maintaining clear public/private boundaries.
4. Reuse the model client/Agent session patterns and establish normalized call/artifact records.
5. Connect strict TaskConfig/ExperimentConfig resolution and the common autonomous-Agent runner.
6. Adapt Veloren to the same external contracts, preserving its existing native evidence and result validity.
7. Qualify representative endpoints and process-sensitive tasks, then add the selected mainstream baselines and reproducible configurations.

These are proposed engineering increments, not authorization to install dependencies, run games or incur model costs in this documentation turn. Avoid requiring a universal plugin system, all-platform installer, complete event DSL or all baseline frameworks before verifying one end-to-end contract.

### 24.8 Remaining questions, not silently decided

- Exact BaseGame methods and restricted Agent-handle shape; process versus session reuse.
- Definitive observation/tool return semantics, parallel access and cancellation for each actual backend.
- Measured start, snapshot cutoff, late effects and settling policy.
- Minimal extensible evaluator API beyond endpoint snapshots.
- Mainstream baseline shortlist and capability/accounting requirements.
- Quantitative budgets, frame/action limits, reset tolerances and required retention.
- Precise packaging/import layout and final schema/output names.

The high-level lifecycle/snapshot ownership, Agent autonomy, per-episode initialization, Linux focus, VM/ST terminology and reuse-first direction should not be reopened as if undecided merely because detailed signatures remain open.

## 25. Lean layered testing and implementation handoff

Discussion through 12:29. The user was concerned that prior AI-assisted development produced too many low-value unit tests and proposed either omitting unit tests or retaining only a few layered core tests. The recommended working choice is the latter. The user then requested updating this archive before considering bottom-up implementation.

**Policy: test important behavior and actual regressions, not every function, module, configuration file or edit.** No coverage percentage, test-count quota or one-test-per-change rule is adopted. This does not authorize removing existing tests without checking their purpose.

### 25.1 What the public-project inspection established

The preceding discussion inspected public repository trees and selected source/CI files, not executing their suites. Counts below are files, not collected test cases or proof of passing tests.

| Project and checked revision | Observation |
| --- | --- |
| [VideoGameBench](https://github.com/alexzhang13/videogamebench/tree/faab53179cb4babdd102f35cb83c24a5f2c29d05) | No conventional test directory or test-named source files found in the checked tree; checkpoint images are benchmark scoring assets, not software unit tests |
| [Orak](https://github.com/krafton-ai/Orak/tree/c14e5a01f998c222c76e09da2564aa8b72ebc75e) | No conventional test suite found; mentioning `tests` in a type-check configuration does not establish published tests |
| [OmniGameArena](https://github.com/mxlin043/OmniGameArena/tree/6731902675e4f409da98ce6f2730723fe02ae6ea) | No conventional test-named suite found; benchmark checkpoint code is not itself a software test |
| [MineDojo](https://github.com/MineDojo/MineDojo/tree/2731bc27394269643b43828d9db8ab3a364601f0) | No conventional Python test suite found; a Test-named Java logging class was not counted as one |
| [MineStudio](https://github.com/CraftJarvis/MineStudio/tree/278aa8553668d591339dbf30d281594ed06ee882) | Nine top-level `tests/test_*.py` files, with more test-named files inside the package. Inspected top-level examples include manual configuration/data-conversion scripts, while MineRL/Herobraine code also contains assertion-based tests |
| [DSLE](https://github.com/ConnAALL/dsle/tree/8bab89534253bd6d6c4fd894eb9414d8c2ab31d9/tests) | 26 unit, 5 contract and 3 integration test files, plus helpers. CI explicitly runs unit/contract tests; inspected real-game tests require opt-in environment flags |

This small sample shows variation, not an industry-wide testing requirement. A missing conventionally named suite does not prove authors never tested, and a `test_*.py` filename does not prove an automated unit test. No causal quality/adoption judgment follows from test counts.

Useful examples are DSLE's [reward tests](https://github.com/ConnAALL/dsle/blob/8bab89534253bd6d6c4fd894eb9414d8c2ab31d9/tests/unit/test_rewards.py), which check scoring formulas and missing-state behavior, and its [live boss checks](https://github.com/ConnAALL/dsle/blob/8bab89534253bd6d6c4fd894eb9414d8c2ab31d9/tests/integration/test_live_boss.py), which exercise real reset/step behavior only when enabled. Borrow separation and purpose, not its test volume.

### 25.2 Small repository-owned test hierarchy

Proposed initial organization:

```text
tests/
  core/          # Configuration, Episode boundaries, result/artifact handling
  game/          # Critical evaluator and state-projection logic
  integration/   # Explicit opt-in native game/display checks
```

These are development support files, not a fifth business module or a complete mirror of the source tree. No empty hierarchy or test file is required until useful. A small number of modules can cover multiple related behaviors with table-driven cases.

Prioritize:

1. **Scoring correctness:** initial inventory does not earn new-acquisition credit; missing evidence does not become success; historical conditions are tested only where actually used.
2. **Lifecycle correctness:** normal exit, timeout and failure preserve required evidence and release control/resources; a few fake-driven scenarios may cover several modules.
3. **Configuration and output identity:** incompatible selections are rejected; existing results are not overwritten or resumed under different conditions.
4. **Information boundaries:** private scorer/admin information does not leak through VM/ST observations or tool results.
5. **Accounting where implemented:** retry/duplicate records and unknown usage are handled correctly, without requiring every provider to have an identical synthetic suite.
6. **Real integration:** a small per-game smoke path exercises launch, initialization/reset, an observation/action, snapshot and shutdown without requiring paid model inference.

Default fast tests should not install/start games, download model weights, change a shared display, or make paid/network model requests. Real-environment checks require explicit selection and appropriate isolated resources. If those checks are skipped or prerequisites are missing, report that qualification has not been performed; do not call mock-only success a real-game pass.

### 25.3 Avoiding test proliferation

- Do not generate tests for every getter, dataclass, trivial wrapper or internal forwarding call.
- Do not duplicate evaluator tests for each task YAML. Test a shared evaluator's substantive rules and validate compatible configuration entries together.
- Prefer output/behavior assertions over fragile assertions about private call order. Assert ordering only where it is a real protocol requirement, such as evidence capture before closing its bridge.
- Use independent expected outcomes; copying implementation formulas into the test can reproduce the same bug.
- Avoid exhaustive Cartesian products of games, profiles, seeds and providers in routine unit tests.
- Do not build a parallel fake game engine to prove behavior that requires native execution.
- Do not keep every exploratory script as a permanent test or reorganize existing tests merely to match a new tree.
- Add focused regression cases for important fixed bugs. Reuse or extend an existing case instead of creating a new file by default.
- Keep model capability evaluations in ExperimentConfigs and reported benchmark runs, not stochastic default unit tests.

The goal is less maintenance with meaningful protection against incorrect scores, leaked state and damaged runs. Test count alone is neither a success metric nor a deletion criterion.

### 25.4 Next-session handoff

The next phase is **discussion and execution of bottom-up implementation**, following Section 24.7 rather than recreating the full framework in one step:

1. Inspect the exact reusable Minecraft paths and agree on the smallest concrete game operations needed for launch/reset/snapshots.
2. Implement one game path with a limited set of high-value checks; preserve existing behavior unless a change is explicitly agreed.
3. Reuse public VM/ST interaction capabilities and model/Agent integration, keeping private evidence inaccessible.
4. Connect the common runner, configuration and per-episode artifacts around those working operations.
5. Adapt Veloren while retaining its existing meaningful evidence and qualification logic.
6. Integrate the selected mainstream Agent baselines and validate admitted conditions.

Do not require all numeric budgets, all test scenarios, all platforms or all baselines to be implemented before the first bounded working path. Conversely, exact start/cutoff semantics and unresolved interface decisions must be made explicit when implementing the affected path, not silently guessed.

This update changed only the design archive and survey index. It created no tests, source scaffolding or implementation, and did not run games or model evaluations. Documentation checks, if performed, verify archive integrity and examples only.

## 26. Resource accounting, autonomous Agents and minimal baselines

Discussion update: 2026-10-21 19:08 (UTC+08:00). This records the user's
latest direction and source checks; no runner or Agent is implemented here.

- The user proposes task wall time as the primary limit, with inference use
  measured rather than capped. The recommended main protocol therefore has no
  mandatory token, model-call or monetary quota. Faster local models may make
  more decisions within the same live-world deadline. This revises the earlier
  recommendation to require run-level inference budgets; exact timing and
  reporting fields remain to be implemented.
- Compute is not thereby equalized. Record model and reasoning configuration,
  hardware, concurrency, observed latency, calls and available usage/cost.
  Missing usage is unknown, not zero. Operator safety caps, if enabled, must
  produce a disclosed termination condition rather than silently masquerading
  as the normal task deadline. Shared game/inference hardware can alter game
  performance and must be disclosed.
- The user confirms autonomous Agents: the harness owns initialization,
  termination, admitted interfaces, evidence and scoring, not Agent reasoning,
  planning, observation cadence or internal scheduling. The public interface
  and deadline remain enforced even when computation is uncapped.
- A minimal reference Agent can directly pass the public task, allowed
  observations, control documentation, tool schemas and interaction history to
  the model, execute its tool calls and return their results. It needs no
  separate planner, reflection module, skill learning or task solution hints.
  History retention and output/termination rules are still scaffold choices,
  not requirements imposed on every external Agent.

### Verified source evidence

GameAgentVisual branch `xianya/init_mincraft`, commit
`696257de4ba7788f68026084b794d1265677f75b`, was inspected without checkout:

- `agent/agent.py` resets conversation state for each task, supplies a fresh
  screenshot per decision request, passes tool schemas and accumulated
  messages, executes returned calls sequentially and appends tool results.
  A complete text-only answer ends the Agent run, not an independent score.
  There is no separate explicit planner/reflection loop or history truncation
  in this inspected Agent implementation.
- Its system prompt includes controls, tool sequencing, held-input semantics,
  real-time behavior and stopping rules. It is a thin direct-model scaffold,
  not literally an instruction-free invocation.
- `launch/launcher.py` wires both the action tool and a QueryAgent-backed
  documentation tool. `agent/query_agent.py` sends the complete supplied static
  documents with each independent question. Consequently the wired system has
  an additional model helper, even though the main decision loop is simple.

Previously checked public examples:

- [BALROG NaiveAgent](https://github.com/balrog-ai/BALROG/blob/main/balrog/agents/naive.py)
  requests one action without extra output; its
  [history builder](https://github.com/balrog-ai/BALROG/blob/main/balrog/prompt_builder/history.py)
  controls retained observations/actions.
- [Orak Minecraft zero-shot prompt](https://github.com/krafton-ai/Orak/blob/release/src/mcp_agent_servers/minecraft/prompts/text/zeroshot_agent/action_inference_system.py)
  requests explanation, planning and generated code with skill/API guidance;
  its name must not be interpreted as an action-only, unassisted baseline.

These are source-level findings, not local reproductions or baseline scores.

## 27. Cross-domain Agent integration research and proposed contract

Discussion update: 2026-10-21, following the user's 19:57 request for substantial
research before choosing BaseAgent. The companion
[Agent integration research and design](agent_integration_research_and_design_20261021.md)
contains the pinned evidence, full proposed contract, lifecycle semantics,
termination mapping, fairness boundaries and implementation acceptance checks.
It is supporting research for this canonical archive, not a second independently
maintained framework specification.

The intervening discussion confirmed public rather than hidden initial
observations, autonomous Agents in a continuously evolving world, and optional
automatic observation within a reference Agent rather than a mandatory runner
loop. Directory proposals evolved to `agents/{llm,implementations}` with one
directory per concrete Agent and optional adapters; flattening `llm/providers`
was recommended but not performed.

The researched recommendation is:

- Keep full autonomous `run`, not a universal `get_action` method.
- Return a typed AgentExit; interpret upstream final-text, submit, idle, process
  exit or step termination inside each adapter.
- Separate cooperative `stop` from resource-owning `close`; add optional,
  task-blind `prepare` outside measured play.
- Preserve independent authorized observation/action capabilities. Automatic
  observation is ordinary Agent code, not necessarily another model call.
- Allow model injection or a supported gateway, with declared model roles and
  explicit parameter/feature mappings. Inspect's Agent Bridge is important
  reuse prior art, not a selected or installed dependency.
- Keep public task/guide/profile information common, while treating Agent
  prompts/history/auxiliary models as declared implementation choices.
- Revoke input at an authoritative runner cutoff, keep native game access for
  final evidence, and distinguish Agent return from evaluator success.

All contract names and new lifecycle details remain proposals for approval.
No runtime code, Agent implementation, launcher or directory layout was changed.

## 28. Supported Agent scope and model-client fairness follow-up

Discussion update: 2026-10-21, after the user's 22:38 research request.

The user clarified that the initial integration scope can exclude step-only
Agents requiring a benchmark-supplied decision loop and generated-code execution
Agents. The intended target is autonomous tool-using Agents with their own run
and normal termination mechanisms. This is a chosen support boundary, not a
claim that excluded architectures are incomplete or invalid Agents.

The discussed AgentWrapper composes an upstream Agent and maps the lifecycle
and public game interactions. It may also configure the model backend or inject
a client adapter; model adaptation is not inherently a mandatory BaseAgent
method. Public game/interface instructions and the episode goal are separate
logical inputs, even if a wrapper delivers them as one upstream task string.
An upstream custom system-prompt parameter is not a universal prerequisite.

The companion
[model-client fairness follow-up](model_client_fairness_followup_20261021.md)
records freshly checked official sources. AgentLab, tau2 reference Agents,
SWE-agent and BALROG demonstrate shared model layers or factories. Harbor
combines native model abstractions with external-program adapters that configure
upstream clients. Inspect bridges supported native SDK/HTTP requests. These
are different mechanisms and must not be conflated with universally rewriting
Agents to import one client.

A common client is neither necessary nor sufficient for fixed-model method
comparison. Proposed admission must check actual backend/model revision,
auxiliary roles, required capabilities and parameter semantics. Preserve and
disclose Agent strategy differences; keep native full-system comparisons
separate. No new production implementation, dependency or benchmark run was
introduced by this follow-up.

### 28.1 Prominent benchmark implementation reading list

The user's 22:49 follow-up requested highly visible benchmarks, including recent
2026 work, as concrete implementation references. The
[reading-list report](prominent_agent_benchmark_integration_20261021.md)
records official repository attention snapshots, version-pinned source paths,
and limits on interpreting popularity.

The strongest immediate reference is Terminal-Bench's current Harbor execution
path: experiment-level Agent/model configuration plus native-process adapters.
SWE-bench Pro's current V2 adds protocol-specific subclasses to existing Harbor
integrations. OSWorld/WebArena illustrate benchmark-driven step contracts,
not a requirement to change the selected full-run scope. SkillsBench explicitly
labels model-harness combinations; CommerceAgentBench shows a 2026 native runtime
integration with configuration injection and visible runtime/prompt adaptations.
These are distinct practices, not evidence that one universal LLM client or
zero-change Agent wrapper is standard. No game runtime or Agent code was changed.

## 29. Framework compatibility audit and minimum-change integration priority

The [ten-framework compatibility report](agent_framework_protocol_compatibility_20261021.md)
contains pinned-source assessments of CrewAI, LangGraph, OpenAI Agents SDK,
Google ADK and smolagents, plus Mindcraft, Voyager, Cradle, Orak and MineStudio.
NitroGen is a separate recent policy case, not misclassified as an LLM framework.
Popularity and recency are reported separately; five equally recent and popular
game planning frameworks were not established.

The five general frameworks expose restricted tool-Agent construction paths;
this does not qualify every application built on them. Native game systems
have more substantial observation, action, code-execution, clock or policy
interface differences. No external runtime qualification was performed.

At 23:08 the user clarified the priority: make integration convenient, prefer a
pure Wrapper, and minimize upstream source edits when a Wrapper is insufficient.
Zero upstream modifications are not required. This updates earlier overly strict
readings of the support boundary; it does not authorize arbitrary game-state
access, world pausing, or changes to the fixed-model experimental condition.

Recommended boundary: small benchmark-facing lifecycle, public task/instructions,
controlled game capabilities, experiment-owned configuration and declared
adaptations. Prefer upstream configuration and extension points, then separate
adapters/bridges, then small pinned patches. Preserve an existing upstream
controller rather than requiring a particular class name or native SDK response
format. Method-changing adaptations and optional code/policy conditions need
explicit discussion. Production BaseAgent remains run(task, interface)/stop;
the richer typed lifecycle has not been implemented or frozen.

### 29.1 Benchmark-first correction and protocol reuse

At 23:12 the user explicitly redirected work away from Agent compatibility
surveys: study benchmark implementations across lifecycle, environment and
model boundaries, with minimal upstream edits as the objective.
Section 6 of the
[model integration report](model_client_fairness_followup_20261021.md)
records the focused follow-up.

Two concrete reuse mechanisms deserve examination before custom implementation:
Harbor's generic registry-backed ACP integration (session control, MCP server
delivery and advertised model selection), and Inspect's sandbox model proxy
plus host-tool MCP bridge. Neither is universally transparent or sufficient
for restricted real-time game evaluation. Harbor's native sandbox explains
much of its low-change environment integration; Inspect's default proposal-bound
tools need deliberate handling for programmatic observations.

The research found protocol-based low-change integration paths, not a perfect
adapter for arbitrary upstream code. Small explicit patches remain acceptable.
No decision to adopt ACP, MCP transport, Inspect dependencies or Harbor as the
LiveQuestBench runtime was made.

## 30. Consolidated Agent integration protocol: wrapper-first draft

Discussion update: 2026-10-21, after 23:16 UTC+08:00.
Status: consolidated proposal, not adopted under the user's conditional
requirement that all ten surveyed systems fit. No production code changes.
This section is the current reading entry for Agent integration; Sections
27-29 and the linked reports retain historical decisions and source evidence.

### 30.1 Objective and architectural boundary

Minimize integration work and upstream source edits. Preserve an existing
Agent's runtime, prompts, memory and model clients wherever the chosen
experimental condition permits. Prefer configuration and wrappers, then
documented adapters/bridges, then small pinned patches.

There is one benchmark-facing lifecycle abstraction, not three competing
architectures:

```text
Experiment configuration
        |
Benchmark Runner
        |
        | BaseAgent lifecycle
        v
AgentWrapper
        | native SDK / process launcher / reusable ACP client
        v
Existing Agent runtime
        |
        +-- environment calls --> callbacks / proxy / MCP --> game gate --> game
        |
        +-- model calls -------> native client / adapter / proxy --> model backend
```

The wrapper assembles these connections. It need not intercept each individual
message, and must not become the only location for game authorization.
The game gate owns permissions, validation, timestamps and action cutoff.
The model path owns request translation/routing, not game authorization.

ACP, MCP and model API compatibility are optional mechanisms used underneath
the wrapper, not alternatives to BaseAgent. The upstream Agent does not have
to import BaseAgent or AgentContext.

### 30.2 What "configuration-only" means

Distinguish three development costs:

- **Benchmark infrastructure:** a reusable ACP wrapper, MCP game service, or
  model gateway must exist or be integrated once. They are not currently
  implemented merely because this document describes them.
- **Per-Agent integration:** an Agent already matching those protocols may
  need only a launch/configuration entry. Other Agents require a small adapter.
- **Upstream source changes:** avoid where extension points suffice; carry a
  narrow, versioned patch if essential configuration or dependencies are hidden.

One reusable ACP wrapper may serve multiple conforming Agent executables.
There is no requirement for a new wrapper class or directory for each entry.
Conversely, an SDK-native Agent should not be forced through ACP or a model
proxy when direct injection is simpler and more faithful.

### 30.3 Upper boundary: lifecycle

Recommended minimal target signatures, conceptual rather than implemented:

```text
run(context) -> AgentExit
stop(reason) -> acknowledgement
close() -> cleanup
```

Construction/factory configuration supplies Agent options and model routes.
Optional task-blind preparation is a runner phase; it need not become another
mandatory abstract method until a concrete integration requires it.

- `run` owns one complete attempt by delegating to the existing upstream
  runtime, which may include its native controller/runner.
- The context supplies only episode identity, public task/instructions,
  permitted game capabilities and appropriate time information. It does not
  expose the private task configuration, evaluator, reset or unrestricted game.
- Native final answer, return, exit event and native limit are mapped explicitly.
  Distinguish `completed`, `gave_up`, `returned`, `native_limit`, and externally
  `stopped` as semantic categories; exact public enum names remain provisional.
  An intentional upstream void return can map to `returned`; an accidental
  missing wrapper result must not silently mean success.
- Errors remain errors. Native limits are not successful completion.
  The evaluator, not AgentExit, determines task success.
- `stop` requests retirement and is safe after normal return or failure.
  It is not proof that blocking code or remote inference has stopped.
- `close` releases only Agent-owned resources, after preserving final evidence.

At a deadline, the runner revokes game access before waiting for Agent cleanup,
handles accepted/active actions according to game cancellation semantics,
collects final evidence, and uses bounded worker/process retirement where
necessary. A queue, ACP cancel or cancelled Python task alone is insufficient.
The early-return-to-episode-cutoff policy must be declared; the proposed default
is to end control when the full Agent returns, subject to task requirements.

### 30.4 Middle boundary: environment communication

Reuse the existing profile vocabulary rather than imposing a universal game
state or skill set. Logically the Agent needs approved observations, available
action descriptions, and an action/result channel. Existing VM `observe/act`
and ST `observe/call_tool` can be exposed without renaming their domain actions.

Bindings may be native callbacks, an environment proxy or an MCP tool service.
All must reach the same permissioned per-episode game gate. MCP configuration
alone does not disable native shell, filesystem, network or direct game-client
paths. Isolate or disable bypasses as required by the chosen condition.

Programmatic observation is allowed: it need not be selected by an LLM.
Full fresh observations need not accompany every primitive action result.
Observation scheduling and any automatic refresh remain declared Agent
behavior. Preserve capture timestamps and do not claim atomic observation
freshness after a tool completes.

The restricted profile accepts permitted named actions whether selected using
native provider tool calls or safely parsed text. It does not execute arbitrary
model-generated programs under the label of one generic action tool.

If Inspect bridged tools are reused, their default proposal matching must be
reconciled with programmatic observations. Opting out of matching does not
opt out of game permission, deadline or logging checks.

### 30.5 Lower boundary: experiment-owned model configuration

An experiment declares the selected model/backend and required generation
settings, Agent-specific options and all enabled model roles. Public game
instructions and task content are benchmark inputs; Agent strategy prompts
remain declared Agent configuration.

Model implementation choices, in preferred order where suitable:

1. Configure the original client's model, provider and endpoint.
2. Inject an adapter implementing the upstream model contract.
3. Route a supported API through a compatible model gateway.
4. Apply a narrow upstream patch when no reliable extension point exists.

No common Python client class is mandatory. Configuration must actually take
effect: record requested and resolved settings, and inspect real requests
where available. Required settings that are unsupported, overwritten or
unverifiable cannot be silently certified as a fixed-model comparison.

Credentials remain out of recorded configuration. Native retries, fallbacks,
context trimming and additional model calls are recorded and controlled where
the experiment requires it. Embedding, grounding and vision components need
explicit policies; a chat model cannot simply replace an embedding model.
Private scoring models remain separate from Agent roles.

The primary budget remains wall-clock time. Optional per-request settings or
operator safety limits do not silently introduce an aggregate token/call cap.
Model proxy latency, hardware placement and concurrency are relevant to the
continuously running game and must be disclosed or controlled.

### 30.6 End-to-end examples and admission

For a conforming ACP/MCP Agent:

1. Resolve experiment configuration and verify declared capabilities.
2. Prepare the native executable and owned resources without revealing the
   episode-specific task.
3. Establish its session and MCP/model configuration when supported without
   premature game access; otherwise establish them during measured run.
4. Begin the game attempt, enable its restricted capability and deliver public
   instructions/task through the session prompt.
5. Native runtime calls the configured model and game tools. The benchmark
   does not author a new decision loop.
6. Map native completion or enforce external cutoff; preserve evidence and
   score independently.

An SDK-native wrapper follows the same logical sequence through direct calls
instead of ACP. Neither path inherently changes the Agent algorithm.

Admission applies to implementation + wrapper revision + model/roles +
game/profile, not just a repository name. Before claiming support, verify
public input delivery, a real observation/action/result round trip, explicit
invalid-call errors, model settings, normal/native-limit/error exits, cutoff
including held inputs, and final-evidence preservation.

### 30.7 Reassessment of the ten surveyed systems

These classifications use the pinned evidence in the
[compatibility report](agent_framework_protocol_compatibility_20261021.md).
They are source-level integration estimates, not passing runtime tests.

| System | Fit under this consolidated architecture | Work or remaining condition |
| --- | --- | --- |
| CrewAI | Suitable tool-Agent construction path | Native config/tools wrapper; audit auxiliary roles and choose correct async runtime |
| LangGraph | Suitable for an existing tool-Agent graph | Wrap existing loop; inspected prebuilt entry is deprecated, so select/version the actual implementation before integration |
| OpenAI Agents SDK | Suitable tool-Agent construction path | Async tool binding and model/run configuration; verify handoffs, cancellation and auxiliary calls |
| Google ADK | Suitable LlmAgent/runner path | Bind tools, session events and effective generation configuration |
| smolagents | Suitable ToolCallingAgent path | Sync/async bridge and stop handling; CodeAgent is not covered by this conclusion |
| Mindcraft | Conditional, not thin-wrapper compatibility | Rebind direct Mineflayer observations/actions and background behavior; preserve or disclose skill changes |
| Voyager | Native method outside current restricted profile | Generated programs, pause/reset semantics and native skill system; changing them is not neutral wrapping |
| Cradle | Requires a labeled game/timing adaptation | Pause control, UI access and skill curation conflict with current assumptions |
| Orak Minecraft | Native configuration outside restricted profile | Retain existing runner but native generated-code actions still need a different condition or method change |
| MineStudio | Policy integration is outside selected full-Agent scope | Existing inference/controller and native simulator differ; a policy route requires explicit additional scope |

The general frameworks are toolkits, while the game entries include concrete
systems and policy infrastructure. These rows cannot justify a combined
compatibility percentage or a claim that ten unchanged Agents can be run.

The user's conditional acceptance criterion (all ten fit) is not met.
Do not adopt or freeze the protocol on that basis. Recommend retaining the
small wrapper-based architecture while explicitly deciding which concrete
game methods and profiles must be supported. Accommodating all ten native
methods would require more than ACP/MCP/model routing and cannot be promised
without changing scope and comparison conditions.

## 31. Six-dimensional task design and native peer teams

**User-confirmed direction, 2026-10-26:** replace the five-level task organization
with spatial understanding/interaction, planning/resource management, real-time
decision/execution, information use/adaptation, multi-Agent cooperation, and
within-Episode learning/improvement. Retain the continuous-world, long-horizon
research question, native mechanics, VM/ST separation and existing lifecycle.

The [current English design](current_design_en_20261026.md) and
[Chinese design](current_design_zh_CN_20261026.md) supersede conflicting ladder
proposals. They retain useful diagnostic tasks, propose demand tags rather than
dimension directories, distinguish focused from integrated task scores, and
describe a small reuse-first redesign with explicit missing evidence. Candidate
families, metadata and axis aggregation are proposals, not newly executable tasks.
Historical task IDs, labels, budgets and results are not rewritten.

Peer teams are now implemented locally for both games and tracks: independent
instances of the same selected Agent/model share one world, task and deadline,
with role-specific initial states and native broadcast/private messages.
This is equal-player cooperation, not an internal subagent architecture.
See [protocol](native_peer_team_v1.md) and [evidence](native_peer_team_acceptance.json).
It does not yet supply a validated cooperation task family or learning measure.
Learning remains inside one continuous Episode; game character upgrades and
recipe unlocking alone are not Agent learning.
