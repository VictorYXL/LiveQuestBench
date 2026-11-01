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
Game and asset licenses remain separate from the benchmark.

## Runtime profiles

The default installer does not prepare every task-specific profile. If
initialization requests another runtime setting, point it to the matching
prepared profile. Do not substitute an incompatible runtime.

Runtime settings take a `runtime.json` manifest, except
`LIVEQUEST_VELOREN_COMBAT_RESPONSE_RUNTIME_ROOT`, which takes the directory
containing the prepared combat-response profiles.

For separately built Message runtimes, see
`python -m game.veloren.runtime.initial_message --help`.

Glide-distance tasks require a `native-client-glide/2` runtime; rerun setup into a
new directory if yours is older.

## Run

Select `config/veloren/experiments/structured_tools.yaml` or
`config/veloren/experiments/visual_motor.yaml`, then follow the
[experiment instructions](../../README.md#running-an-experiment).
Select only tasks supported by the installed profiles.
