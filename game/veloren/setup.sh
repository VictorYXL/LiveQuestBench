#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec uv run --locked python -m game.veloren.runtime.install "$@"
