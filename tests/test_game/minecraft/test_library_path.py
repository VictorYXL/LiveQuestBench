"""Opt-in native loader-lock regression using the prepared Minecraft dependencies."""

import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.game
@pytest.mark.skipif(os.environ.get("LIVEQUEST_MINECRAFT_TEST") != "1", reason="Requires native Minecraft runtime")
def test_library_path_does_not_deadlock_concurrent_loads(tmp_path):
    from game.minecraft.runtime.client import check_client
    from game.minecraft.runtime.install import check_java

    java = check_java()
    classpath = os.pathsep.join(check_client()["classpath"])
    library = tmp_path / "loader-probe.so"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-x", "c", "-", "-o", str(library)],
        input="int livequest_loader_probe(void) { return 1; }\n",
        text=True, capture_output=True, check=True, timeout=30,
    )
    subprocess.run(
        [java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-proc:none",
         "-cp", classpath, "-d", str(tmp_path), str(Path(__file__).with_name("LibraryPathRace.java"))],
        capture_output=True, text=True, check=True, timeout=30,
    )
    result = subprocess.run(
        [java, "-cp", str(tmp_path) + os.pathsep + classpath, "LibraryPathRace", str(library)],
        capture_output=True, text=True, check=True, timeout=20,
    )
    assert "PASS: 20000 concurrent library loads and path resolutions" in result.stdout
