"""Provision the task-specific passive Fabric server alongside the native client."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from game.minecraft.runtime.client import GRADLE_VERSION
from game.minecraft.runtime.install import check_java, data_root


BUILD_FILES = ("settings.gradle", "build.gradle")
OBSERVER_CLASS = "org/livequestbench/observer/SuccessfulBreakMixin.class"


def source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "server_observer"


def source_digest() -> str:
    digest = hashlib.sha256()
    root = source_root()
    paths = [root / name for name in BUILD_FILES]
    paths.extend(path for path in sorted((root / "src").rglob("*")) if path.is_file())
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def observer_root() -> Path:
    return data_root() / "server-observer-1.20.4"


def launch_path() -> Path:
    return Path(os.environ.get(
        "LIVEQUEST_BREAK_SERVER_LAUNCH", str(observer_root() / "launch.json"),
    )).expanduser().resolve()


def check_observer() -> dict:
    path = launch_path()
    try:
        launch = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise RuntimeError("Passive observer is not prepared; run game/minecraft/setup.sh") from error
    if "LIVEQUEST_BREAK_SERVER_LAUNCH" not in os.environ:
        receipt = json.loads((path.parent / "ready.json").read_text())
        if (receipt["source_sha256"] != source_digest() or receipt["root"] != str(path.parent)
                or receipt["launch_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()):
            raise RuntimeError("Passive observer setup changed or moved; rerun setup in an unused runtime")
    for entry in launch["classpath"]:
        if not Path(entry).exists():
            raise FileNotFoundError(f"Passive observer dependency is missing: {entry}")
    classes = [Path(entry) / OBSERVER_CLASS for entry in launch["classpath"]
               if (Path(entry) / OBSERVER_CLASS).is_file()]
    if len(classes) != 1:
        raise RuntimeError("Expected exactly one compiled passive break observer")
    for name in ("launch.cfg", "remapClasspath.txt", "log4j.xml"):
        if not (path.parent / ".gradle/loom-cache" / name).is_file():
            raise FileNotFoundError(f"Passive observer launch support is missing: {name}")
    return launch


def install_observer() -> None:
    if "LIVEQUEST_BREAK_SERVER_LAUNCH" in os.environ:
        check_observer()
        return
    root = observer_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (root / "ready.json").exists():
            check_observer()
            return
        executable = data_root() / "tools" / f"gradle-{GRADLE_VERSION}" / "bin/gradle"
        if not executable.is_file():
            raise RuntimeError("Prepare the native client toolchain before installing the passive observer")
        for name in BUILD_FILES:
            shutil.copyfile(source_root() / name, root / name)
        shutil.copytree(source_root() / "src", root / "src", dirs_exist_ok=True)
        java = shutil.which(check_java())
        if java is None:
            raise RuntimeError("Java 21 executable is unavailable")
        subprocess.run(
            [str(executable), "--no-daemon", "--console=plain", "clean", "prepareServer"],
            cwd=root, env={**os.environ, "JAVA_HOME": str(Path(java).resolve().parents[1]),
                           "GRADLE_USER_HOME": str(data_root() / "gradle")},
            check=True, timeout=900,
        )
        (root / "ready.json").write_text(json.dumps({
            "source_sha256": source_digest(), "root": str(root),
            "launch_sha256": hashlib.sha256((root / "launch.json").read_bytes()).hexdigest(),
        }, indent=2) + "\n")
        check_observer()
