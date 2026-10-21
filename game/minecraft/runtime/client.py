"""Provision and launch the pinned Fabric development client, without account files."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

from game.minecraft.runtime.install import check_java, data_root, download


GRADLE_VERSION = "8.6"
GRADLE_SHA256 = "9631d53cf3e74bfa726893aee1f8994fee4e060c401335946dba2156f440f24c"
BUILD_FILES = ("settings.gradle", "build.gradle", "gradle.properties")


def source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "client"


def source_digest() -> str:
    digest = hashlib.sha256()
    for name in BUILD_FILES:
        digest.update(name.encode())
        digest.update((source_root() / name).read_bytes())
    for path in sorted((source_root() / "src").rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(source_root())).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def client_root() -> Path:
    return data_root() / "client-1.20.4"


def check_client() -> dict:
    root = client_root()
    try:
        receipt = json.loads((root / "ready.json").read_text())
        launch = json.loads((root / "launch.json").read_text())
    except FileNotFoundError as exc:
        raise RuntimeError("Native client is not prepared; run game/minecraft/setup.sh --track visual_motor") from exc
    if receipt["source_sha256"] != source_digest() or receipt["root"] != str(root):
        raise RuntimeError("Native client setup has changed or moved; rerun game/minecraft/setup.sh")
    if receipt["launch_sha256"] != hashlib.sha256((root / "launch.json").read_bytes()).hexdigest():
        raise RuntimeError("Native client launch metadata changed; rerun game/minecraft/setup.sh")
    for entry in launch["classpath"]:
        if not Path(entry).exists():
            raise FileNotFoundError(f"Native client dependency is missing: {entry}; rerun setup")
    for name in ("launch.cfg", "remapClasspath.txt", "log4j.xml"):
        if not (root / ".gradle" / "loom-cache" / name).is_file():
            raise FileNotFoundError(f"Native client launch support is missing: {name}; rerun setup")
    return launch


def install_client() -> None:
    root = client_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        archive = data_root() / "downloads" / f"gradle-{GRADLE_VERSION}-bin.zip"
        download(
            f"https://downloads.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip",
            archive, algorithm="sha256", digest=GRADLE_SHA256, size=132788867,
            hosts={"downloads.gradle.org", "github.com", "release-assets.githubusercontent.com"},
        )
        tools = data_root() / "tools"
        executable = tools / f"gradle-{GRADLE_VERSION}" / "bin" / "gradle"
        if not executable.is_file():
            with ZipFile(archive) as package:
                package.extractall(tools)
            executable.chmod(0o755)
        for name in BUILD_FILES:
            shutil.copyfile(source_root() / name, root / name)
        for path in (root / "src").rglob("*"):
            if path.is_file() and not (source_root() / path.relative_to(root)).is_file():
                print(f"Removing obsolete managed client source: {path}", flush=True)
                path.unlink()
        shutil.copytree(source_root() / "src", root / "src", dirs_exist_ok=True)
        (root / "ready.json").unlink(missing_ok=True)
        java = shutil.which(check_java())
        assert java is not None
        modules = subprocess.run([java, "--list-modules"], capture_output=True, text=True, check=True, timeout=10).stdout
        if not any(line.startswith("jdk.compiler@") for line in modules.splitlines()):
            raise RuntimeError("Native client setup requires the Java 21 compiler module; install a JDK and set MINECRAFT_JAVA")
        subprocess.run(
            [str(executable), "--no-daemon", "--console=plain", "clean", "prepareClient"],
            cwd=root,
            env={**os.environ, "JAVA_HOME": str(Path(java).resolve().parents[1]),
                 "GRADLE_USER_HOME": str(data_root() / "gradle")},
            check=True, timeout=1800,
        )
        (root / "ready.json").write_text(json.dumps({
            "source_sha256": source_digest(), "root": str(root),
            "launch_sha256": hashlib.sha256((root / "launch.json").read_bytes()).hexdigest(),
        }, indent=2) + "\n")
        check_client()


def launch_command(
    *, java: str, directory: Path, player_name: str, port: int, memory_mb: int, structured: bool = False,
) -> tuple[list[str], dict[str, str]]:
    launch = check_client()
    directory.mkdir(exist_ok=False)
    (directory / "options.txt").write_text(
        "version:3700\nlang:en_us\npauseOnLostFocus:false\n"
        "onboardAccessibility:false\ntutorialStep:none\nskipMultiplayerWarning:true\n"
        "joinedFirstServer:true\nfullscreen:false\nrenderDistance:6\nsimulationDistance:6\n"
        "maxFps:30\nenableVsync:false\nrawMouseInput:false\nsoundCategory_master:0.0\n",
    )
    return [
        java, f"-Xmx{memory_mb}M", f"-Dlivequest.structured={str(structured).lower()}", *launch["jvm_args"],
        "-cp", os.pathsep.join(launch["classpath"]), launch["main_class"],
        *launch["program_args"], "--username", player_name, "--gameDir", str(directory),
        "--quickPlayMultiplayer", f"127.0.0.1:{port}", "--width", "854", "--height", "480",
    ], launch["environment"]
