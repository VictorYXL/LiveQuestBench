# Minecraft integration

This directory reserves the Minecraft implementation boundary. It does not yet
launch Minecraft, install game components, capture frames, or expose tools.

The next increment is a concrete `MinecraftGame` in `game.py`, implementing
[`BaseGame`](../base_game.py) by adapting existing code rather than rebuilding it.

Reuse sources in the current development workspace:

- `/home/msra/GameAgent/GameAgentVisual`, branch `xianya/init_mincraft`: visual
  capture, keyboard/mouse input, recording, managed sessions and snapshot scoring.
  The initialization `main` branch does not represent that implementation.
- `/home/msra/GameAgent/GameAgentResearch`: structured tools, session management
  and Agent/model integrations.

These paths are development references, not required absolute installation paths
for future users. No code has been copied from either project in this directory.

## Directory responsibilities

- `setup/`: explicit Linux provisioning scripts, to be added with the integration.
  Python dependencies belong in the root project configuration. Setup must not run
  implicitly when importing a module or starting an Episode.
- `guide/`: public game/control documentation, not hidden task solutions.
- `evaluators/`: scoring implementations that consume private evidence.
- `structured_tools/actions/`: reusable action implementations, when needed.
- `structured_tools/observations/`: allowed state acquisition and projection.
- `structured_tools/tools/`: public tools, each with implementation and description;
  the parameter schema should have one authoritative definition.

Add a game-specific `visual_motor/` directory or `evidence.py` only when there is
actual code to place there. Shared display/input mechanisms belong in `core/`,
not in a copied backend for every game.

Task definitions, experiment settings and immutable fixture assets/references
belong under [`config/minecraft/`](../../config/minecraft/). A fixture must not be
used as the writable live world. Do not redistribute proprietary game binaries
or third-party assets without the applicable permission.
