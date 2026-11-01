# Minecraft

Minecraft Java 1.20.4 supports native pixels and keyboard/mouse control (VM),
or permitted native state and fixed tools (ST). Both modes use an isolated
server and the controlled player's actual rendered view.

## Setup

On Linux x86_64, run from the repository root:

```bash
bash game/minecraft/setup.sh
```

Setup provisions Java 21, graphics dependencies and the native runtime.
Use `--skip-system` when system packages are already installed. An initial
installation requires internet access; neither local mode requires a launcher
login.

Read the [Minecraft EULA](https://aka.ms/MinecraftEULA). Only if you accept it:

```bash
export MINECRAFT_EULA_ACCEPTED=true
bash game/minecraft/setup.sh --check --verify-server
```

`--check` does not launch a game; `--verify-server` consults official metadata.
EULA consent and offline authentication do not grant redistribution rights.
Game binaries and assets are downloaded, not bundled.

| Variable | Purpose |
| --- | --- |
| `LIVEQUEST_MINECRAFT_HOME` | Dedicated runtime installation directory |
| `MINECRAFT_JAVA` | Java 21 executable |
| `MINECRAFT_SERVER_JAR` | Server JAR override |
| `LIVEQUEST_BREAK_SERVER_LAUNCH` | Optional prebuilt passive-observer launch descriptor |

Use the same settings for setup and evaluation. Do not rebuild an installation
while it is in use.

## Run

Select `config/minecraft/experiments/structured_tools.yaml` or
`config/minecraft/experiments/visual_motor.yaml`, then follow the
[experiment instructions](../../README.md#running-an-experiment).
Edit the task list for smaller runs.

Both modes require graphics support; headless mode uses Xvfb.
The server continues during model calls and actions. Task scoring is private;
inventory, event order, deaths and return conditions depend on the selected task.
