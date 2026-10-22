# Game Agent follow-up: GamingAgent native harness

Date: 2026-10-22, UTC+08:00.

## Scope and decision

The follow-up prioritizes recognizable game-playing systems, rather than adding
more general-purpose tool frameworks. Admission requires configurable actual
model calls, permitted game observations/actions, and benchmark-owned lifecycle.
Native task failure is allowed; communication/configuration/adapter failures
are not accepted as capability failures.

**Implemented: LM Games GamingAgent**, preserving its native episode runner and
perception-memory-reflection-reasoning harness as a declared fixed-tool game
extension. The earlier report deferred it pending qualification; this work
addresses those specific obstacles rather than treating that deferral as a
permanent incompatibility.

Only one new Agent is claimed in this batch. VM and ST profiles are not counted
as different Agents. The repository now contains six Agent integrations.

## Refreshed candidate evidence

Official GitHub repository APIs and primary source/README files were inspected.
Stars are observed attention signals, not quality, academic adoption, or task
performance. This is a bounded survey, not an exhaustive popularity ranking.
Web search was used for discovery; primary sources take precedence over search
summaries, which incorrectly failed to identify the publicly available STEVE-1
repository and overstated NitroGen's long-horizon capabilities.

| Candidate | Stars observed | License evidence | Decision for the current condition |
| --- | ---: | --- | --- |
| [Voyager](https://github.com/MineDojo/Voyager) | 7,275 | MIT | Generated programs and native pause/unpause/reset ownership require a different qualified condition, not a thin fixed-tool wrapper |
| [Mindcraft](https://github.com/mindcraft-bots/mindcraft) | 5,910 | MIT | Strong next candidate for a substantial adaptation; native Mineflayer bot state, commands and autonomous behaviors cannot simply be relabeled as the approved ST interface |
| [Cradle](https://github.com/BAAI-Agents/Cradle) | 2,594 | MIT | Native UI/game management, pause behavior and game-specific skills require separately reviewed VM adaptation |
| [NitroGen](https://github.com/MineDojo/NitroGen) | 2,216 | Custom NVIDIA license; API reports NOASSERTION | Dedicated vision-to-gamepad policy, not a configurable LLM scaffold; original game runner supports Windows, and a controller/permission profile is needed |
| [GamingAgent](https://github.com/lmgame-org/GamingAgent) | 994 | MIT | Implemented and qualified below |
| [GITM](https://github.com/OpenGVLab/GITM) | 644 | API license null in this check | No admission or runtime claim; explicit reuse/license and released implementation review still required |
| [Numen](https://github.com/Dwinovo/minecraft-numen) | 545 | LGPL-3.0 reported by GitHub | In-game Mod executing model-generated Lua over game APIs; not the current fixed-tool condition |
| [JARVIS-1](https://github.com/CraftJarvis/JARVIS-1) | 417 | No root license found; API null; inspected pyproject has no license declaration | Public implementation exists, but no reuse permission inferred from visibility; native controller stack also requires separate qualification |
| [Odyssey](https://github.com/zju-vipa/Odyssey) | 411 | MIT | Voyager-derived Mineflayer skill framework; native bridge still pauses between interactions |
| [STEVE-1](https://github.com/Shalev-Lifshitz/STEVE-1) | 230 | No root license found; API null | Released policy/training code exists; pretrained VPT/MineCLIP policy and MineRL environment are not an interchangeable LLM backend |

These are engineering boundaries, not claims that integration is impossible.
In particular, policy-model Agents are relevant future complete-system baselines,
but making them look like fixed-model LLM scaffolds would misrepresent them.
No third game, new action track, generated-program permission, or proprietary
game asset was added.

### Primary source anchors

- GamingAgent:
  [`BaseAgent`](https://github.com/lmgame-org/GamingAgent/blob/996d848ae5e3bf68433d663f38ef4da5bdfe5332/gamingagent/agents/base_agent.py),
  [`CoreModule` and Observation](https://github.com/lmgame-org/GamingAgent/blob/996d848ae5e3bf68433d663f38ef4da5bdfe5332/gamingagent/modules/core_module.py),
  [native runner](https://github.com/lmgame-org/GamingAgent/blob/996d848ae5e3bf68433d663f38ef4da5bdfe5332/lmgame-bench/single_agent_runner.py).
- Voyager: [bridge pause/unpause calls](https://github.com/MineDojo/Voyager/blob/55e45a880755d0c8c66ca7fb5fe7962ac8974f89/voyager/env/bridge.py).
- Mindcraft: [native bot/Agent ownership](https://github.com/mindcraft-bots/mindcraft/blob/f6a9556cf756e6bd88a75cc2fa0d5aed7599b101/src/agent/agent.js).
- Cradle: [RDR2 runner, including game pause](https://github.com/BAAI-Agents/Cradle/blob/d7752fccf890d8d3818cd1d435f3705f604a1339/cradle/runner/rdr2_runner.py).
- NitroGen: [README at inspected pin](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/README.md)
  explicitly describes a last-frame 500M DiT, not a long-horizon planner, and
  requires Windows for the original game runner.
  [License](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/LICENSE)
  must not be summarized as MIT/Apache or unrestricted open source.
- Odyssey: [README](https://github.com/zju-vipa/Odyssey/blob/260303c8c0c5afd86d8b50edffb5ffac0de01d4f/README.md)
  describes the Voyager basis and primitive/compositional skills;
  [bridge](https://github.com/zju-vipa/Odyssey/blob/260303c8c0c5afd86d8b50edffb5ffac0de01d4f/Odyssey/odyssey/env/bridge.py)
  confirms pause/unpause calls.
- Numen: [README](https://github.com/Dwinovo/minecraft-numen/blob/fc2e19c31ef9e5c7001217a5f31015b3e301c30b/README.md)
  describes the native Mod and model-generated Lua API interaction.
- JARVIS-1: [source tree](https://github.com/CraftJarvis/JARVIS-1/tree/aa9bd97debee045cb35b37564c71dee4c465b9ad),
  [dependency metadata](https://github.com/CraftJarvis/JARVIS-1/blob/aa9bd97debee045cb35b37564c71dee4c465b9ad/pyproject.toml).
- STEVE-1: [README](https://github.com/Shalev-Lifshitz/STEVE-1/blob/903b244796322f4d0073a8f62c05f51eac3aed52/README.md)
  describes VPT/MineCLIP weights, MineRL v1.0.1 and its training/evaluation tools.
- GITM: [inspected repository revision](https://github.com/OpenGVLab/GITM/tree/f7487801d8443c15e262c965f1bb6b720aa76cb0).

## Implementation and fidelity

The new package follows the existing layout:

```text
agent_framework/agents/gamingagent/
  agent.py
  worker.py
  source.json
  setup.py
  requirements.in
  requirements.lock
  patches/0001-injected-transport.patch
  patches/LICENSE.txt
  README.md
```

It reuses `ProcessAgent`, `WorkerBridge`, exact pin-plus-patch verification,
independent runtime setup, game-owned prompts/tools and the real acceptance test.
No parallel Agent framework, simulated game or replacement native decision loop
was introduced.

### Preserved native computation

`run_game_episode` calls native `BaseAgent.get_action`, which runs:

1. Native perception. VM retains image resizing and a visual-description model
   call; ST uses the native text path.
2. Native memory/reflection. The real configured model produces reflection,
   and the native bounded trajectory records observations.
3. Native reasoning prompt construction and `ReasoningModule.plan_action`.
4. Native action/thought memory update.
5. Native runner dispatch and trajectory transfer into the next observation.

The new game's parser is supplied through the native custom-module slot.
Actual provider tool calls become a JSON envelope. The default regex strips
quotes and therefore cannot safely parse arbitrary tool arguments; it is not
used for this extension. Full tool schemas, exact argument values and the
parent's pending-proposal checks remain authoritative.

Native episode defaults are explicitly set: harness enabled, perception enabled,
reflection enabled, summary disabled, 20 trajectory entries, no grid scaffolding,
1,000 native steps. All active model roles use the requested model, reasoning
effort and output ceiling. Generic task/role prompts are recorded per attempt;
no Minecraft strategy is embedded in the Agent wrapper.

### Declared upstream patch

Only two upstream files change:

- `CoreModule` gains a model-manager factory with a lazy original-provider
  default. Injected transport replaces provider selection/HTTP/cost utilities,
  not native perception, reflection or action planning.
- The runner defers unused game/emulator imports and preserves action-string
  case only when the new environment explicitly requests it. The default
  lowercasing behavior remains for upstream environments.

The upstream MIT notice accompanies the patch. A disposable pristine checkout
verified clean application, repeated preparation, exact admission and rejection
when the declared patch is removed. It was deleted afterward. No heavyweight
emulators, auxiliary provider services or generated-code executors were installed.

### Observation and lifecycle changes

The new Agent opts into native observation handling; existing process profiles
retain their latest-observation-at-model-call behavior.

For GamingAgent, the parent supplies only the permitted observation at native
environment boundaries. The worker saves/resizes the actual frame using native
code, and inline image bytes return through the shared model bridge. Reflection
remains text-only; action reasoning uses the captured native frame and memory.
The bridge does not silently add a newer image or hidden state. Capture/model
trace timestamps and frames are retained. The world continues to advance during
all three stages, so observation age and extra model cost remain meaningful
method differences.

`reset()` is a one-time attachment to a benchmark-initialized game; it cannot
reset that game. `render()` needs no extra action because the native client is
already continuously rendering. Tool execution uses the parent-approved public
interface. The benchmark gates access before terminating the worker.

Private reward, score and game success are never sent to the Agent. Native
runner numeric reward/performance accumulators receive NaN (unavailable), and
native persisted results record JSON null plus `score_status=not_exposed`.
These placeholders are not benchmark scores. Only private saved-world evaluation
produces the task outcome; the Agent's final text ends its own loop only.

The native model manager's provider-specific cost accounting and continuation
records are not reproduced. Actual usage/model identities are recorded by the
injected client. Native text memory is not provider reasoning-state replay.
Native `thinking` is an Anthropic-specific API-manager option; the admitted
profile uses the explicit shared reasoning setting, not an extra thinking model.

## Validation evidence

### First real acceptance

Command:

```bash
LIVEQUEST_MINECRAFT_TEST=1 LIVEQUEST_LIVE_COPILOT=1 \
LIVEQUEST_GAMINGAGENT_ROOT="$PWD/output/temp/gamingagent-20261022" \
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py -k gamingagent -q -s --headless --recording
```

The authorized Copilot token file was supplied separately through
`LIVEQUEST_COPILOT_TOKEN_FILE`. Credentials are not included in this report.

**3 passed, 12 deselected in 296.98 seconds.**

| Case | Integration | Independent task outcome | Real game tools | Native reasoning steps | World ticks |
| --- | --- | --- | ---: | ---: | ---: |
| GamingAgent VM | Passed | 3 logs; task_success | 10 | 11 | 3,333 |
| GamingAgent ST | Passed | 3 logs; task_success | 4 | 5 | 848 |
| GamingAgent ST intentional stop | Passed | task_failure | 1 | 1 | 184 |

All actual model identities were `gpt-6-astra`; reasoning `low`, output ceiling
4096, one transport attempt, 180-second episode budget. All workers exited zero
without forced termination. Native reflection was present in every recorded
reasoning step, VM visual descriptions were present, and videos decoded.
The stop retained its truthful task failure and returned
`benchmark_game_gate_closed`, not a fabricated successful task.

Evidence under `output/test/`:

- `gamingagent-visual_motor-b4e240b0d43e43ff96d22051a031c3a5`
- `gamingagent-structured_tool-5e31b5e718bd4595b77972734d48d31d`
- `gamingagent-structured_tool-4c462cb7e52d464890d84c92d15ca470`

### Final native-module and shared-bridge regression

With all three runtime roots and the same explicit real-game/model opt-in:

```bash
uv run --locked --extra minecraft --group test python -m pytest \
  tests/test_agent/test_agents.py \
  -k 'gamingagent or orak-structured_tool or smolagents-visual_motor' \
  -q -s --headless --recording
```

**5 passed, 10 deselected in 575.75 seconds. No selected case skipped.**
This is a targeted five-case run, not a rerun of all fifteen available cases.
The test now checks actual native reflection, action-memory entries and VM
visual descriptions, not just a worker return or one successful model request.

| Case | Integration | Task outcome | Game calls | Model attempts | Gate requested after |
| --- | --- | --- | ---: | ---: | ---: |
| Orak ST regression | Passed | task_success, 3 logs | 4 | 5 | 23.273 s |
| smolagents VM regression | Passed | task_failure, 2 logs; deadline | 40 | 41 | 180.001 s |
| GamingAgent VM | Passed | task_failure, 2 logs; deadline | 9 | 30 | 180.001 s |
| GamingAgent ST | Passed | task_success, 3 logs | 4 | 10 | 45.844 s |
| GamingAgent ST intentional stop | Passed | task_failure, 0 logs | 1 | 2 | 10.824 s |

All five actual model identities were `gpt-6-astra`, all workers exited zero,
none required forced termination, all videos decoded, and world time advanced.
GamingAgent's final VM had nine completed native reasoning steps, 19 memory
entries, reflection and visual descriptions. Its normal ST case had five native
reasoning steps and ten model calls; the operator-stop case had one step and two
model calls.
Each completed VM reasoning step's actual image bytes were checked against the
image-bearing model request; the resized native frame was not silently discarded
or replaced.

The two deadline cases were inspected beyond pytest's exit code: actual motor
commands completed, native inventory contained two logs, and the sole unsuccessful
model attempt in each was `CancelledError` at the intentional deadline. GamingAgent's
last perception/reflection correctly reported being one log short and planned to
continue. No provider/configuration/adapter exception was observed. These are
valid task failures under the budget, not justification to alter the fixture,
extend the limit, or rerun until the task score improves. The earlier successful
VM sample remains archived alongside this failure.

Final evidence directories under `output/test/`:

- `orak-structured_tool-7c1469cb87444eddabffcca1d20e4653`
- `smolagents-visual_motor-27bb491b6077426ba4e4a89f45bb39d8`
- `gamingagent-visual_motor-67f1d70e56f44fd6b0390073a2fd6e5b`
- `gamingagent-structured_tool-bbecc0b89984495582ea0f680f2a91fd`
- `gamingagent-structured_tool-bfc7b91d99e94ad0b787375940c3f0c6`

### Additional checks

- Lean offline Minecraft regression: **3 passed, 4 deselected in 0.31 seconds**.
- Native harness/runner imports succeed in the isolated environment without
  unused provider SDKs or emulators.
- Source patch apply/idempotence/removal-rejection check passed.
- Python compile checks passed. Pylance reported no diagnostics for the worker
  and test file, and only the existing unused `home` hint for `ProcessAgent`.
  Its separate syntax-file endpoint could not locate the new file; compilation
  and actual runtime tests supply syntax/execution evidence instead.
- Universal dependency resolution was deliberately not used: the upstream
  NumPy pin conflicts with OpenCV's Python 3.12 requirement. The checked-in lock
  is explicitly resolved for the validated Linux Python 3.11 runtime.

Fingerprints:

- Patch SHA256:
  `2debff4efe6af7b7e97d92ec86187af664b8a5a1de34ecb54731257d298b0cea`
- Dependency lock SHA256:
  `bfa6167dc743724b6cf2ff3e49445f1fe8d0f8a1c06f8104bd7f93df41bdb0aa`

## Limits and next candidates

These simple real-game cases prove engineering integration for a particular
pin/profile/model/game combination. They do not establish long-horizon competence,
comparative performance, broad model support or reproduction of GamingAgent's
published benchmark results. Process isolation is cooperative, not an OS sandbox.
Optional native games and default provider-manager paths were not runtime-tested.

Among the deferred popular LLM systems, Mindcraft is a useful next engineering
study, but requires an explicit decision about preserving its native skill and
autonomy model versus restricting it to benchmark tools. Cradle similarly needs
a qualified visual-control/skill profile. NitroGen and STEVE-1 belong in a
separate policy-controller integration study rather than a pretend LLM wrapper.
Those decisions should not be hidden inside an apparently thin adapter.
