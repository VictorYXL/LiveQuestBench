# Veloren

Veloren supports native pixels and bounded keyboard/mouse control (VM), or
permitted native state and fixed tools (ST). The server continues during model
calls, movement, crafting, combat and recovery.

## Setup

Prepare a matching [VelorenBench](https://github.com/wyaaaattwho/VelorenBench)
installation and native build cache first. LiveQuestBench's setup reuses that
installation; it is not a standalone game downloader.

Requirements: Linux/X11, Vulkan, Xvfb, FFmpeg, `patch`, `uv`, the upstream Rust
toolchain and its Python environment. On Ubuntu, install `x11-utils` and
`libxkbcommon-x11-0` for display inspection and rendering.

Set `VELOREN_INSTALLATION` to the upstream installation JSON,
`VELOREN_BUILD_CACHE` to its matching build cache, and `VELOREN_RUNTIME_DIR` to a
new dedicated destination:

```bash
bash game/veloren/setup.sh \
  --installation "$VELOREN_INSTALLATION" \
  --build-cache "$VELOREN_BUILD_CACHE" \
  --root "$VELOREN_RUNTIME_DIR"
export LIVEQUEST_VELOREN_RUNTIME="$VELOREN_RUNTIME_DIR/runtime.json"
```

Keep the upstream installation available. Never rebuild a runtime in use.
Automatic protection is disabled; ordinary native damage, enemy AI and
downed/death mechanics remain active. Game and asset licenses remain separate
from the benchmark.

## Runtime profiles

Some tasks require separately prepared, version-matched profiles:

| Task/profile | Runtime setting |
| --- | --- |
| Ordinary tasks | `LIVEQUEST_VELOREN_RUNTIME` |
| Local solid scene/camera | `LIVEQUEST_VELOREN_LOCAL_SOLID_RUNTIME` |
| Original contract settlement | `LIVEQUEST_VELOREN_NATIVE_CONTRACT_RUNTIME` |
| Original hostile recovery | `LIVEQUEST_VELOREN_HOSTILE_RECOVERY_RUNTIME` |
| Original self-funded expedition | `LIVEQUEST_VELOREN_SELF_FUNDED_RUNTIME` |
| Workstation directions | `LIVEQUEST_VELOREN_WORKSTATION_RUNTIME` |
| Initial-message v3 | `LIVEQUEST_VELOREN_INITIAL_MESSAGE_V3_RUNTIME` |
| Market reconciliation | `LIVEQUEST_VELOREN_MARKET_RUNTIME` |
| Combat-response family | `LIVEQUEST_VELOREN_COMBAT_RESPONSE_RUNTIME_ROOT` |

Settings point to prepared `runtime.json` manifests, except the combat-response
setting, which points to a directory containing its four versioned runtime
variants. Configure it explicitly; no developer-machine directory is assumed.
Both response variants are validated before sampling.

The default installer does not create every specialized profile. Versioned
Message builds can be packaged with `scripts/veloren_initial_message_runtime.py`.
Task-specific runtime and asset checks remain strict: a missing, relocated or
changed manifest is not automatically equivalent to a qualified runtime.
Do not edit hashes or silently substitute another profile to bypass admission.

## Run

Select `config/veloren/experiments/structured_tools.yaml` or
`config/veloren/experiments/visual_motor.yaml`, then follow the
[experiment instructions](../../README.md#running-an-experiment).
Select only tasks supported by the installed profiles.

VM receives actual game frames, not a transcription of hidden state. ST uses its
declared tools and field whitelist. Private native events supply scoring and
measurement checks, not agent guidance. A valid task failure remains a result;
unsupported profiles and invalid measurements are reported separately.
