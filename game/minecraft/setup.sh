#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: game/minecraft/setup.sh [--track all|visual_motor|structured_tool]
                               [--check] [--verify-server] [--skip-system]

Prepare dependencies for local Minecraft VM/ST tests with one shared runtime.
The default is both modes. Neither local mode needs Prism or a Microsoft login.
Run as your normal user, not with sudo. The script requests
sudo only for system packages.

Supported package managers: apt-get, dnf, pacman.
--skip-system  Skip system packages when they are already provisioned.

--check        Read-only inspection; never install or launch anything.
--verify-server  With --check, verify against official online Mojang metadata.

Local tests default to an offline server bound only to 127.0.0.1.
VM/ST: One native Minecraft client, launched through a pinned Fabric development
       environment. No Node.js, Mineflayer, spectator or launcher login required.
Both: read the Minecraft EULA and explicitly accept it before running a game.
      MINECRAFT_EULA_ACCEPTED=true is consent, not account authentication.

Setup needs internet access and can take several minutes on a fresh machine.
Prepared tests run on an isolated Xvfb display, including from SSH.
Use run_benchmark.py --no-headless to show the game on an existing desktop DISPLAY.
Offline authentication does not waive Minecraft's usage/distribution terms.
Existing accounts and worlds are kept. No game or LLM test runs automatically.
See game/minecraft/README.md for setup and experiment commands.
EOF
}

fail() {
    printf 'Setup error: %s\n' "$*" >&2
    exit 1
}

skip_system=false
check_only=false
verify=false
track=all
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --skip-system) skip_system=true ;;
        --check) check_only=true ;;
        --verify-server) verify=true ;;
        --track)
            [[ $# -ge 2 ]] || fail "--track requires all, visual_motor or structured_tool"
            track="$2"
            shift
            ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done
case "$track" in all|visual_motor|structured_tool) ;; *) fail "Unknown track: $track" ;; esac
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] ||
    fail "Only Linux x86_64 is supported."
[[ $EUID -ne 0 ]] || fail "Run game/minecraft/setup.sh as your normal user, without sudo."

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd -- "$root"
trap 'printf "Setup failed at line %s. Resolve the reported error and rerun game/minecraft/setup.sh.\n" "$LINENO" >&2' ERR

if "$check_only"; then
    [[ -x "$root/.venv/bin/python" ]] || fail "Run uv sync --locked --extra minecraft first."
    options=(--track "$track")
    if "$verify"; then options+=(--verify-server); fi
    exec "$root/.venv/bin/python" -m game.minecraft.runtime.install check "${options[@]}"
fi
"$verify" && fail "--verify-server is only valid with --check"

java21() {
    "$1" -version 2>&1 | grep -Eq 'version "21([."])'
}

jdk21() {
    java21 "$1" && "$1" --list-modules 2>/dev/null | grep -q '^jdk.compiler@'
}

if [[ -n "${MINECRAFT_JAVA:-}" ]]; then
    java21 "$MINECRAFT_JAVA" ||
        fail "MINECRAFT_JAVA must point to a working Java 21 executable."
fi

need_java=true
if jdk21 "${MINECRAFT_JAVA:-java}"; then
    need_java=false
fi

if ! "$skip_system"; then
    command -v sudo >/dev/null || fail "Install sudo or provision packages manually, then use --skip-system."
    sudo -v
    printf '\nInstalling system packages...\n'
    if command -v apt-get >/dev/null; then
        packages=(ca-certificates curl tar)
        packages+=(xvfb xauth ffmpeg libgl1-mesa-dri libglx-mesa0 libxcursor1 libxrandr2 libxi6 libxinerama1)
        if "$need_java"; then packages+=(openjdk-21-jdk-headless); fi
        sudo apt-get update
        sudo apt-get install -y "${packages[@]}"
    elif command -v dnf >/dev/null; then
        packages=(ca-certificates curl tar)
        packages+=(xorg-x11-server-Xvfb xorg-x11-xauth ffmpeg-free mesa-dri-drivers mesa-libGL libXcursor libXrandr libXi libXinerama)
        if "$need_java"; then packages+=(java-21-openjdk-devel); fi
        sudo dnf install -y "${packages[@]}"
    elif command -v pacman >/dev/null; then
        packages=(ca-certificates curl tar)
        packages+=(xorg-server-xvfb xorg-xauth ffmpeg mesa libglvnd libxcursor libxrandr libxi libxinerama)
        if "$need_java"; then packages+=(jdk21-openjdk); fi
        sudo pacman -S --needed --noconfirm "${packages[@]}"
    else
        fail "No supported package manager found. Install the README requirements and use --skip-system."
    fi
fi

programs=(curl tar Xvfb ffmpeg)
for program in "${programs[@]}"; do
    command -v "$program" >/dev/null || fail "Required program not found: $program"
done

java_export=false
if ! jdk21 "${MINECRAFT_JAVA:-java}"; then
    # Keep the system Java selection unchanged if another application needs it.
    for candidate in /usr/lib/jvm/*/bin/java; do
        if [[ -x "$candidate" ]] && jdk21 "$candidate"; then
            export MINECRAFT_JAVA="$candidate"
            java_export=true
            break
        fi
    done
fi
jdk21 "${MINECRAFT_JAVA:-java}" ||
    fail "A Java 21 compiler/runtime was not found. Install a JDK and set MINECRAFT_JAVA to its java executable."

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
    printf '\nInstalling uv from the official Astral installer...\n'
    installer="$(mktemp)"
    trap 'rm -f -- "$installer"' EXIT
    curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
        --tlsv1.2 --retry 3 --connect-timeout 30 --max-time 180 \
        https://astral.sh/uv/install.sh --output "$installer"
    UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$installer"
    rm -f -- "$installer"
    trap - EXIT
fi
command -v uv >/dev/null || fail "uv installation did not produce an executable."

printf '\nInstalling project Python and dependencies...\n'
uv python install
uv sync --locked --extra minecraft --group test

printf '\nPreparing native Minecraft dependencies and verifying the server...\n'
uv run --no-sync python -m game.minecraft.runtime.install install --track "$track"

cat <<'EOF'

Dependencies are ready. No game was started, no account was signed in,
no EULA was accepted, and no LLM request was made.

Remaining steps:
  1. Read https://aka.ms/MinecraftEULA and, only if you accept it, set:
       export MINECRAFT_EULA_ACCEPTED=true
     This is EULA consent, NOT account authentication.
     Then check the installation:
       game/minecraft/setup.sh --check --verify-server
     For an ST-only installation, also pass --track structured_tool.
     This check does not launch Minecraft. No Prism/account preparation is needed.

  2. No map download is needed for smoke tests: they create a flat test world.
     MINECRAFT_TEST_FIXTURE optionally selects your own pristine 1.20.4 save.

  3. Run the offline checks:
       uv run --locked --extra minecraft --group test python -m pytest tests/test_game/minecraft -q
     Enable real-game checks with LIVEQUEST_MINECRAFT_TEST=1 and add -s to see
     artifact paths. Each case creates a unique directory under output/test/.
     MINECRAFT_TEST_OUTPUT optionally selects a different output root.
     test_game.py checks game basics; test_vm.py checks images and motor input;
     test_st.py checks local state, crafting, digging, movement and cancellation.
     VM/ST tests record 10 FPS video by default; MINECRAFT_TEST_RECORDING=0 disables it.
     --headless (default) uses an owned virtual display. --no-headless uses
     your existing desktop DISPLAY, showing the same controlled player's window.
     Both tracks use the same native installation even with recording disabled.
     No LLM credentials are needed for this scripted environment test.

  4. Inspect pytest results and, if needed, the game recording and native
     snapshots under the printed output paths. Images are checked in memory;
     tests do not write screenshot dumps or summary reports by default.
     Optional LLM client checks and future Agent integration are described in
     game/minecraft/README.md. There is no end-to-end Agent launcher yet.

If uv is not on your terminal's PATH, run:
  export PATH="$HOME/.local/bin:$PATH"
EOF
if "$java_export"; then
    printf '\nThis setup used Java 21 without changing your system default.\n'
    printf 'Before launching experiments in your terminal, run:\n  export MINECRAFT_JAVA=%q\n' "$MINECRAFT_JAVA"
fi
