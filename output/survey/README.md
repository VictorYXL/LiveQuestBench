# Survey Update: Open Game Benchmark Reassessment

**Current design: six capability dimensions (2026-10-26):**
[English design and task-redesign plan](current_design_en_20261026.md) /
[Chinese design and preserved task inventory](current_design_zh_CN_20261026.md).
Spatial interaction, planning/resources, real-time execution, information/adaptation,
peer cooperation, and within-Episode learning replace the five-level organizing
framework. Tasks stay in game/track directories with proposed demand metadata;
focused and integrated tasks have separate reporting. The documents propose a
reuse-first six-focused/two-integrated family development slice and explain radar
aggregation, matched controls, missing coverage, and the remaining cooperation/
learning measurement gaps. Proposed fields and six-axis scores are not implemented.

**Native peer-team substrate:**
[Implemented protocol](native_peer_team_v1.md) /
[Local Baseline and transport evidence](native_peer_team_acceptance.json).
Both games support same-world homogeneous same-track peers, different initial
states, native broadcast/private chat, independent histories and common deadlines.
ST task successes and VM task failures are preserved; transport checks are not
claims of measured causal cooperation.

**Historical entries below:** L1-L5 documents and their counts retain their
original time/version scope. Their former “accepted/current” ladder wording
does not override the six-dimension decision above.

**Reuse-first L1-L3 catalog review (2026-10-24, proposal only):**
[Complete 60-objective report](l1_l3_reuse_first_report_20261024.md)
reorganizes the target catalog around existing scenes, controls and endpoint
scoring: 22 retained objectives, 12 configuration-only candidates, 11 shared
scoring/evidence candidates, 8 scene-work candidates and 7 integration holds.
It records per-objective goals, reuse, remaining gaps, deduplication and approval
gates. No task, classification, runtime or evaluator was changed.

**Former mechanism-oriented ladder (2026-10-24; superseded):**
[Updated task-design and difficulty framework](difficulty_framework_and_catalog_20261024.md)
records L1 basic perception/action, L2 single-mechanism workflows, L3
dominant-mechanism planning, L4 long-horizon adaptive planning, and L5 long-term
autonomous role-based activity. It includes an open L1-L3 mechanism coverage
matrix, game-specific applicability, expansion priorities and paper-writing
guidance. The mechanism list is illustrative, not an exhaustive RPG taxonomy.
Historical task labels remain provisional; this update neither reclassifies
the catalog automatically nor implements the proposed mechanisms.

**Exploratory Minecraft L4 (2026-10-24, development task; difficulty uncalibrated):**
[Lost-expedition development receipt](lost_expedition_qualification_20261024.json)
tracks the approved paired goal-level task, discoverable native field notes,
resource/tool development, optional trading/construction and native combat.
The current revision has valid, audited Baseline ST/VM failures. Actual native
resource/clue/geometry inspection, a prepared-state archive interaction and
pixel-only station-clue readability support feasibility; they are not a full
successful trajectory. Earlier Baseline and controller failures remain intact.
The 60-minute cap is not a measured completion time; approximately 30-minute
successful play and stable L4 difficulty/adaptation remain uncalibrated.
Per the user's acceptance clarification, full Agent/reference success is
optional stronger evidence, not a mandatory publication gate.
The earlier short reconnaissance prototypes are not admitted mature L4 tasks.
Current counting uses one independently executable task YAML per task;
historical paired-objective counts below retain their original snapshot scope.

**100 candidate task slots (2026-10-24, design only):**
[Two-game, five-level candidate matrix](candidate_task_slots_20261024.md)
provides ten slots per level per game, retaining all 31 current task definitions
and proposing 69 additional slots. Each row names its family, native mechanism,
initial conditions, dependencies, score evidence, implementation gaps and ST/VM
admission. Related condition variants are not claimed as independent mechanisms.
Both modes are targets, not 200 qualified combinations. L4/L5 and upstream
dialogue/contract/support integrations remain explicitly unqualified; no code,
task configuration or model run was changed by this design.

**Difficulty framework and current catalog (2026-10-24):**
[Five-level capability ladder and all-task classification](difficulty_framework_and_catalog_20261024.md)
records the accepted L1-L5 design framework and provisional assignments for all
31 tasks at `5bfa959`: L1 = 4, L2 = 15, L3 = 12, L4/L5 = 0.
The updated progression is operation, composition, planning, experience-informed
online adaptation, and long-term autonomous role-based play. L5 replaces the
earlier "complex expedition composition" definition: it emphasizes self-directed
exploration and cumulative development within an open but evaluable mission,
not a longer L4 checklist. The document includes L4 readiness/admission, native
role limitations, and a layered L5 evaluator with optional evidence-grounded
AI judging; these future tasks and evaluators are not implemented or qualified.
Capability level, mode-specific empirical difficulty and core-task eligibility
are distinct. High combat failure rates do not establish L4, and no current
task is promoted merely for its length. These design labels supersede earlier
informal difficulty wording, not historical outcomes. Scoring recommendations
remain proposals; no production task, budget, evaluator or catalog was changed.

**Native trade-linked expedition (2026-10-24):**
[Native trading qualification](native_trade_qualification_20261024.json)
records a paired Minecraft task with real villager payment, purchased-weapon
combat, optional food exchange and cargo return. Baseline ST succeeded; VM
completed the actual purchase but failed in combat. Both runs passed native
score, video, transcript and cleanup audits. One earlier renderer-initialization
failure is retained outside Agent outcomes. A public ST reference succeeds;
124 offline tests and three native regression cases pass. The actual server
binary matches Mojang's official 1.20.4 artifact, while the client bridge,
passive event datapack and fixture are explicitly customized. This does not
complete resident defense, free-form dialogue, Veloren contracts or the full
proposed MC-C3 family.

**Coupled expansion and calibration (2026-10-24):**
[Native expansion qualification](coupled_expansion_qualification_20261024.json)
records revised entry variants and two paired multi-encounter tasks:
Minecraft crafting/two-outpost/cargo return and Veloren gathering/preparation/
two-enemy return. Entry Baselines succeeded in Minecraft ST and Veloren VM;
Minecraft's new task also has an ST success. Veloren's new task remains a
challenging development candidate after Baseline failures, not a calibrated
medium tier. Public ST references succeed for both new tasks, including native
chest transfer and combined-strike cancellation. A targeted Hermes ST run also
completed Veloren's new task. The 11 audited episodes comprise 10 Baseline
runs (3 successes) and one Hermes run (success); the report retains tool-version
retries and superseded prototypes separately, with native evidence/score replay,
video and cleanup checks. Validation includes 122 offline regressions and two
native Minecraft legacy/food/cutoff tests. NPC/merchant/contracts and Boss tiers
remain deferred; the eight-family design is not complete.

**Entry coupled tasks (qualified 2026-10-24):**
[Native entry-task qualification](coupled_entry_qualification_20261024.json)
records Minecraft forge/hunt/return and Veloren prepare/hunt/return in both
tracks. All four recorded Baseline episodes completed with valid measurements
and task failures, with decoded videos, replayed scores, matched native
evidence and cleanup checks. Both public ST reference trajectories succeeded.
Includes 121 offline regressions and two native Minecraft ST/tool checks.
Production experiments remain `all`-only; temporary subsets/controllers are
under `output/temp`. This historical entry gate did not implement or qualify
the larger multi-site/NPC task ladder or difficulty calibration; see the newer
expansion receipt above for subsequent work.

**Coupled task design (2026-10-24, proposal only):**
[Minecraft/Veloren long-horizon and real-time task ladder](coupled_task_design_20261024.md)
proposes four graded families per game, persistent preparation/combat/resupply
dependencies, NPC-linked progression, VM/ST admission and explicit tool,
evaluator, fixture and calibration gaps. It distinguishes source-backed reuse
from unimplemented proposals and recommends Level 1/2 before NPC/Boss expansion.
No game or model runs, production task changes or new experiment configs were
made for this design.

**Veloren combat/task expansion (completed 2026-10-24):**
[Encounter expansion and runtime repairs](veloren_encounter_expansion_20261023.json)
records four paired encounter/resource goals, explicit non-autoaim combat tools,
native death/contribution scoring and twelve valid Baseline-first recorded runs
(three task successes, nine failures), plus 100 offline and two legacy-mode
native regressions. The runtime disables upstream automatic protection and
retires the setup helper before public play; earlier cohorts remain separate.
Composite and dual-enemy public-control references pass. Wolf reference success,
difficulty calibration and NPC dialogue/contracts remain unqualified.

**Recorded engineering acceptance (2026-10-23):**
[64-Episode acceptance receipt](engineering_acceptance_20261023.json)
records the full baseline catalog and five external Agents across both games and
tracks: 48 task successes, 16 task failures, all independently re-scored with
verified recordings/transcripts. Includes 91 offline regressions, 30 native
framework probes, repaired input/cutoff failures, preserved provider incidents,
and the remaining target-platform pilot gate. These are development results,
not frozen model rankings or a no-bugs guarantee. This predates the explicit
native-protection opt-out and does not qualify that rebuilt Veloren runtime.

**Native benchmark parallelism source review (2026-10-22):**
[Game/general benchmark concurrency and defaults](benchmark_parallelism_source_review_20261022.md)
checks six game/game-containing benchmarks plus Inspect, SWE-bench and OSWorld.
It distinguishes supported concurrency, actual defaults and separate-job lanes;
the evidence is source inspection, not executed reproduction or a population survey.

**Benchmark ownership cleanup and publication acceptance:**
[Final organization and regression checks](benchmark_organization_acceptance.md)
records game-owned X11/bindings, the simplified benchmark factory, removal of
empty preparation hooks and fresh four-Episode plus lifecycle validation.

**Explicit world fixtures and composite Veloren initialization:**
[Fixture implementation and real acceptance](explicit_fixtures_acceptance.md)
supersedes implicit generated-world/named-scene initialization. Minecraft now
ships an immutable native task world; Veloren accepts explicit map, scene and
player fields through a game-owned initialization interface. Includes
configuration-change/readback checks and four new production-CLI Episodes.

**Serial Benchmark implementation and real CLI acceptance:**
[Configuration, runner and result acceptance](benchmark_runner_implementation.md)
records the executable file-based configuration layer, four built-in real-game
Episodes, native-Agent/deadline/SIGINT checks, error preservation and explicit
remaining scope. This supersedes the earlier "runner not implemented" status,
without claiming a frozen long-horizon task distribution.

**Fresh game/Agent readiness audit (2026-10-22, evening):**
[Runtime and structural consistency audit](game_agent_readiness_audit_20261022.md)
records the combined game suite, complete real-Agent matrix and focused DeepSeek
stop regression. It fixes cross-game pytest collection and expected-cancellation
classification, while distinguishing consistent architecture from remaining
style/type differences. No benchmark runner or new integration was added.

**Additional game candidates, deferred by user choice (2026-10-22):**
[Open-game screening and installation/licensing caveats](additional_game_candidates_20261022.md)
records Luanti + VoxeLibre and Luanti + Exile as future VM/ST candidates,
with Terasology, SuperTuxKart and ViZDoom/Freedoom as secondary directions.
The user selected research only: no third game was installed or integrated.

**Expanded tool-calling and game-Agent survey (2026-10-22):**
[Candidate landscape and ranked integration recommendations](tool_calling_agent_landscape_20261022.md)
checks LangChain/LangGraph, PydanticAI, CrewAI, Deep Agents, OpenAI Agents SDK,
AgentScope, Agno and further frameworks against the current contract. It verifies
GITM's missing executable release, distinguishes OpenGame game creation from
gameplay, tracks SIMA 2 access limits, and checks actual OpenHA/NitroGen HF
checkpoint listings. The [source snapshot](agent_candidate_snapshot_20261022.json)
records exact revisions, popularity, license evidence and access limitations.
This is research only; no additional integration or runtime qualification is claimed.

**Game Agent follow-up (2026-10-22, after the additional-Agent batch):**
[GamingAgent native harness and refreshed candidate study](game_agent_followup_20261022.md)
records the pinned native perception/memory/reflection/reasoning integration,
declared transport patch, native-image timing profile and real VM/ST/stop
acceptance. It revisits the earlier GamingAgent deferral and adds primary-source
checks for NitroGen, Odyssey, Numen, JARVIS-1, STEVE-1 and GITM.

**Additional native Agents (2026-10-22):**
[Orak/smolagents selection, integration and live acceptance](additional_agent_integrations_20261022.md)
records the new pinned Wrappers, declared Orak patch, popularity/compatibility
screening and final twelve-case real Minecraft/model run. All twelve integrations
passed; the two deliberate stops retain task-failure scores. It also documents
the Responses assistant-history fix and typed game-gate cancellation race.

**Native endpoint evaluators (2026-10-22):**
[Structure evaluator and endpoint-evaluator study](endpoint_evaluators_20261022.md)
records the implemented Minecraft blueprint scorer, real native placement and
counterexample validation, the unpadded live-region reader fix, and source-verified
recommendations for player state, container delivery, statistics and advancements.
Only inventory and name-level construction scoring are implemented; the other
families are proposals.

**Consolidated integration proposal (2026-10-21, after 23:16 UTC+08:00):**
Read [design.md, Section 30](design.md#30-consolidated-agent-integration-protocol-wrapper-first-draft)
for the unified lifecycle, environment and model contract. Wrapper remains the
outer boundary; ACP, MCP and model proxies are optional mechanisms underneath.
It distinguishes one-time infrastructure from per-Agent code and upstream
patches. The ten-system reassessment does not meet an all-ten-compatible
acceptance condition, so the proposal is not adopted or runtime-qualified.

**Ten-framework compatibility audit (2026-10-21, completed after 23:08 UTC+08:00):**
[Agent framework protocol compatibility](agent_framework_protocol_compatibility_20261021.md)
checks five general frameworks and five game systems, with NitroGen as an
additional recent policy example. It separates extension support from native
method/profile compatibility. The user's clarified priority is wrapper-first,
minimum-source-change integration, not an absolute zero-patch rule. No external
Agent has been runtime-qualified.

**Prominent benchmark integration reading list (2026-10-21, after 22:49 UTC+08:00):**
[Prominent Agent Benchmarks: what to study for integration](prominent_agent_benchmark_integration_20261021.md)
screens public attention separately from benchmark maturity and inspects
Terminal-Bench/Harbor, SWE-bench/Pro V2, OSWorld, tau2, WebArena/BrowserGym,
SkillsBench and CommerceAgentBench. It includes pinned execution/configuration
paths, current-version caveats and an ordered reading guide.

**Model-client fairness follow-up (2026-10-21, after 22:38 UTC+08:00):**
[Model clients, external Agent adapters, and comparison fairness](model_client_fairness_followup_20261021.md)
rechecks official source revisions for Inspect, Harbor, AgentLab, tau2-bench,
SWE-agent and BALROG. It distinguishes shared native clients, external-process
configuration, SDK/HTTP bridges and behavioral modifications, and separates
fixed-model method comparisons from native full-system comparisons. No external
Agent or model was run.

**Agent integration research (2026-10-21, after 19:57 UTC+08:00):**
[Agent integration research and BaseAgent design](agent_integration_research_and_design_20261021.md)
compares pinned official contracts from Inspect, BrowserGym/AgentLab, Harbor,
SWE-agent/SWE-bench, tau2-bench and game baselines with the existing local
implementations. It proposes an autonomous typed run/stop/close contract,
optional task-blind preparation, native termination adapters, model routing,
observation/prompt permissions and authoritative real-time cutoff. This is a
proposal, not a BaseAgent implementation or runtime qualification.

**Canonical design archive (2026-10-21):** [design.md](design.md) preserves the complete design discussion, with user requirements, recommendations, unresolved decisions, game-selection context and a continuation guide. Future design updates belong here. The former numbered framework document is retained as a pointer. Local persistence does not imply Git tracking or remote backup.

**Latest consolidation (12:29, UTC+08:00):** read Sections 24-25 and the revised Section 4.3 first. They consolidate the simplified BaseGame/concrete-game layout, game-first configuration and task fixtures, autonomous VM/ST Agents, fresh Agent initialization, Linux/reuse-first scope, on-demand capture versus independent recording, and the confirmed snapshot boundary: game implements, core invokes, evaluator scores. Section 25 adds the public-repository testing observations and the lean layered testing policy: a few core behavior/regression checks, explicit opt-in real-game smoke tests, and no per-edit or coverage quota. Earlier mandatory adapter/runtime/manifest and universal single-action proposals are superseded or explicitly scoped. Bottom-up implementation is the next phase; none was started in this update.

**Step-2 framework proposal (2026-10-21):** [design.md](design.md) assesses the proposed task/run/launcher structure, answers all ten architecture questions in their original order, and specifies proposed boundaries for lifecycle, agent interfaces, private evidence, evaluators, clocks, reset, budgets and results. Includes a concrete per-game directory layout, repetition/instance semantics, illustrative YAML and representative episode walkthroughs. This is a design draft grounded in current code, not an implemented or approved protocol.

**Baseline integration follow-up:** Section 20 of the framework proposal recommends same-repository reference agents and thin adapters, externally pinned third-party implementations, and explicit adaptation/reimplementation labels. It separates model providers from full agents and explains when a separate agents repository is justified.

**Configuration layout follow-up:** the latest working layout is `config/<game>/{tasks,experiments,fixtures}`, with optional profiles/variants; game implementation remains in `game/`, model clients under `agents/llm/`, and orchestration/shared backends in `core/`. Sections 22-23 retain the earlier layout discussion with historical labels. User-owned configuration may live outside the repository; strict reference resolution and frozen-condition checks preserve reproducibility. No implementation files were moved.

**Game-selection follow-up (2026-10-21, UTC+08:00):** [13_game_selection_and_free_access.md](13_game_selection_and_free_access.md) recommends retaining Veloren and Minecraft, proposing a free Veloren entry path rather than adding a third game by default. It screens Luanti + VoxeLibre and Luanti + Exile, distinguishes open benchmark code from free game access, and records unresolved distribution/runtime checks. This is a recommendation, not an approved scope change.

**Game selection and access strategy (2026-10-20):** [13_game_selection_and_free_access_strategy.md](13_game_selection_and_free_access_strategy.md) recommends retaining Veloren and Minecraft for research, considering a substantive no-purchase Veloren core with optional Minecraft, and deferring a third game. It checks Minecraft terms, corrects the Zelda hardware assumption, identifies Veloren asset-license and installation caveats, and screens Luanti/VoxeLibre, Mineclonia, Craftium, and Terasology. This is a proposal, not an approved scope change.

**Latest interaction and influence audit (2026-10-20):** start with [11_scope_influence_and_interaction_audit.md](11_scope_influence_and_interaction_audit.md), with [12_influence_release_snapshot.json](12_influence_release_snapshot.json). It distinguishes recorded-video questions from actual gameplay, corrects GameHorizon's 21-game offline versus Minecraft-only online coverage, adds GameVerse's real GUI interaction and default scoring gap, and separates attention from external reuse. No runtime reproduction was performed.

**Focused follow-up:** [10_reactive_long_horizon_intersection.md](10_reactive_long_horizon_intersection.md) answers whether fast reaction and long-horizon planning coexist in a non-RTS open benchmark. It verifies VideoGameBench's 2D Zelda setting, examines the stricter 3D RPG intersection, and adds Lumine and concrete Cradle pause semantics. Read it before interpreting the broader overlap assessment as coverage of the full conjunction.

**Latest review: 2026-10-20.** Start with [09_core_value_and_overlap_update.md](09_core_value_and_overlap_update.md) for the renewed core/value assessment, freshly checked sources, stronger Solo Craft variant overlap, additional RTS neighbors, and unresolved questions. For the earlier process analysis, read [08_core_hypothesis_and_research_process.md](08_core_hypothesis_and_research_process.md). For the broader competitor review, read [06_open_benchmark_reassessment.md](06_open_benchmark_reassessment.md); [07_public_source_snapshot.json](07_public_source_snapshot.json) records the earlier public repository snapshot.

**Current process:** core -> framework/protocol design -> games/tasks -> model/agent evaluation -> analysis and iteration -> frozen evidence, paper, and release. This user-confirmed ordering supersedes historical step numbering below and in earlier reports. The latest assessment recommends proceeding to protocol design, not claiming novelty or launching a large evaluation campaign.

The new review distinguishes licensed releases, public code with unresolved licensing, partial environment/test releases, and method-only precedents. It also verifies OmniGameArena's source-level `realtime` mode, locates MC-EvoBench's public implementation, adds StarDojo/AgentWorld/LMGame/MineLand comparisons, and identifies ROAR's current repository as a placeholder.

**Priority:** use report 11 for the latest interaction, release, and influence qualifications, reports 09-10 for the core/intersection assessment, and report 06 for the broader release survey subject to those updates. The documents below remain historical research notes, not proof of an unoccupied research area or certified runtime reproducibility.

**Working conventions:** new code, comments, documentation and research deliverables use English; user-facing discussion uses Chinese. Temporary scripts belong under `output/temp`; survey outputs belong under `output/survey`. Existing historical documents are preserved.

---

# 即时 3D 游戏 Game Agent Benchmark：前期调研资料

调研日期：2026-10-20。按“RPG”理解需求中的“PRG”。本目录是讨论前的资料包，不是最终 Benchmark 设计，也不是模型评测结果。

**当前比较范围**：以第三方能实际接入模型/Agent 的开放 Benchmark 为核心对象。SIMA 2 等未确认公开可用评测套件的系统只列相关工作，不作为直接竞品。开放内容与待核验边界见 [贡献报告第 0 节](05_contribution_options.md#0-比较范围修订以开放可复用的-benchmark-为核心)。主线暂定为“开放可复用的实时 3D 游戏长程任务评测”；中断恢复是候选任务轴，不是已决定的唯一重点。

**同日更正**：首次调研只检查了 GameAgentVisual 当前检出的初始化 `main`，漏查 `xianya/init_mincraft` 开发分支和已有运行结果，错误判断视觉功能未实现。现已确认自动截图、键鼠、Agent 循环、评测与历史产物均存在；下面已同步修正。详细证据见 [代码调研第 3 节](01_code_review.md#3-minecraft-视觉开发分支已有自动闭环与历史运行结果)。

## 阅读顺序

**快速了解论文核心工作**：先读 [贡献报告第 0.3 节](05_contribution_options.md#03-最新讨论整理论文核心亮点与三条贡献)，其中汇总了推荐亮点、三条拟议贡献、标题与摘要草案，以及“尚未确认完全一致的开放项目”这一结论的证据边界。

| 文件 | 内容 |
| --- | --- |
| [01_code_review.md](01_code_review.md) | 三个项目的实现现状、关键代码证据、任务与接口差异 |
| [02_literature.md](02_literature.md) | 30 项论文/研究条目，区分 Benchmark、平台、数据集与 Agent |
| [03_benchmark_comparison.md](03_benchmark_comparison.md) | 最接近的已有 Benchmark 对照；实时性、输入、动作与评分边界 |
| [04_discussion_brief.md](04_discussion_brief.md) | 核心侧重点、新游戏、任务与 Agent 框架的讨论底稿 |
| [05_contribution_options.md](05_contribution_options.md) | 最新定位：三个核心贡献方案、直接竞品补查、推荐主线与反推任务/游戏的决策依据 |
| [references.json](references.json) | 核验后的题名、作者、日期、原始来源与核验层级 |
| [references.bib](references.bib) | 可导入文献管理器的 30 条引用；键为 `P01` 至 `P30` |
| [task_inventory.csv](task_inventory.csv) | 50 个任务实现记录：Minecraft 结构化 11、视觉 10、Veloren 29；两种 Minecraft 实现有同名目标，不是 50 个独立目标 |
| [code_snapshot.json](code_snapshot.json) | 调研时的 Git HEAD、工作树状态、关键证据文件 SHA-256 |

任务索引中的空白预算/配置字段表示未从该任务定义中取得，不能解释为零或无限；目录成员也不代表所有模态下都已准入。文献 JSON 的“已核验”不是复现实验成功。

## 先看这六点

1. **Minecraft 视觉项目已有自动评测闭环。** 实现在 `xianya/init_mincraft` 分支，当前检出的 `main` 仍是初始化版本；历史目录中有四组各 100 次尝试的汇总，以及截图、动作记录、视频与评分产物。不是“尚未实现”。
2. **Minecraft 结构化项目已经有实质性 Benchmark 和 Agent 实现。** 当前有 11 个任务定义，默认 Vega suite 选 10 个；27 个共享游戏工具；库存/建筑判定；模型调用、耗时与成本统计。
3. **Veloren 更接近 RPG 能力评测的主体。** 有 29 个任务定义、37 个任务×地形组合，覆盖战斗、支援、成长、交易与 NPC 合同。但 125 条工程 qualification 不是 125 个任务，也不是 125 次模型成功。
4. **两条赛道不是只改变观测模态。** 图像+键鼠与结构化状态+宏动作同时改变信息量、动作能力与控制时序；分数差不能直接解释为视觉能力差。
5. **“即时”需要协议定义。** 游戏属于即时类型，不等于评测在 LLM 思考时持续推进。现有 Minecraft 任务还冻结昼夜、天气、自然刷怪及随机 tick；这些设置适合稳定制造任务，却不足以支撑强实时决策结论。
6. **需要区分开放竞品与方法先例。** VideoGameBench、Orak、GameWorld、OmniGameArena 等应按开放内容核验；SIMA 系列只作方法参照，不能代替社区可用的 Benchmark。当前定位是：**开放可复用的实时 3D 游戏长程任务评测**，再通过任务设计体现规划与实时执行的协调。

## 调研方法和证据边界

- **代码**：静态阅读项目说明、任务定义、核心接口、运行器、评分器与部分 Agent/provider 实现；同日补查 GameAgentVisual 开发分支与代表性历史运行产物，未穷尽所有 Python/Rust 文件。
- **文献**：网络检索发现候选，再用 arXiv 原始元数据和摘要、会议页面、官方项目 README 核验。不是对全部论文 PDF 的逐页精读，也不是穷尽性系统综述。
- **日期**：以 2026-10-20 为资料截止日。区分首发日期、当前页面的更新日期与会议年份；引用可能对应更新后的题名/摘要。
- **未执行**：游戏启动、原生构建、模型推理、付费请求、基准任务、完整测试套件。已核对部分既有视觉运行产物，但没有重新生成成绩，也没有认证全部历史试验有效性或模型后端身份。
- **未修改**：三个原项目的代码和已有工作树改动；本次仅创建资料包。Veloren 的未提交改动被视为本次阅读快照的一部分。
- **隐私与版权**：公开检索只使用通用研究主题/公开项目名，没有向检索服务上传本地代码、日志或凭据。这里保留原创摘要、书目信息与原文链接，不打包论文全文、游戏资产、商业游戏或权重。
- **事实与建议**：文档中的“已核验”指代码/来源证据；“建议”“候选”“待验证”不是已实现能力。

## 最优先阅读的相关工作

- [SIMA](https://arxiv.org/abs/2404.10179) / [SIMA 2](https://arxiv.org/abs/2512.04797)：跨 3D 游戏、视觉与人类式控制的方法相关工作；不作为已确认可用的开放 Benchmark。
- [VideoGameBench](https://arxiv.org/abs/2505.18134)：真实时间与思考暂停模式的关键对照。
- [GameWorld](https://arxiv.org/abs/2604.07429)：双动作接口及状态可验证评分；其语义接口不能直接等同于本项目的内部状态观测。
- [OmniGameArena](https://arxiv.org/abs/2606.09826)：实时 UE5 多游戏、两种时钟协议、反思改进与迁移。
- [MCU](https://arxiv.org/abs/2310.08367) / [MC-EvoBench](https://arxiv.org/abs/2610.13829)：任务组合，以及控制经验迁移混杂因素。
- [Orak](https://arxiv.org/abs/2506.03610)：跨游戏统一接入和 Agent 模块消融。

推荐先讨论 [讨论底稿的研究问题](04_discussion_brief.md#1-建议先固定研究问题)，再决定是否扩展第三款游戏。

**后续讨论更新**：当前优先以 [贡献候选与竞品判断](05_contribution_options.md) 第 0 节为定位依据：采用“实时 3D 游戏”而非强行将 Minecraft 归类为 RPG；以开放可复用的长程任务评测为主线，中断恢复和接口/时序诊断为候选设计。相关工作展示过一种能力，不等于提供了社区可运行的 Benchmark；但也不能在未经开放竞品核验时宣称“首次”。原 30 项文献目录不是穷尽性查新。
