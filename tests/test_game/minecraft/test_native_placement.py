"""Exercise the actual Java producer with installed native types, without a game."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import pytest


def test_native_placement_confirmation():
    from game.minecraft.runtime.client import client_root, source_root

    launch = client_root() / "launch.json"
    if not launch.exists() or shutil.which("java") is None:
        pytest.skip("Requires the prepared Minecraft native client and JDK")
    root = Path(__file__).resolve().parents[3]
    output = root / "output/test/native-placement" / uuid4().hex
    classes, scratch = output / "classes", output / "jvm-cache"
    classes.mkdir(parents=True)
    scratch.mkdir()
    configuration = json.loads(launch.read_text())
    old_classes = next(p for p in configuration["classpath"] if p.endswith("/build/classes/java/main"))
    old_resources = next(p for p in configuration["classpath"] if p.endswith("/build/resources/main"))
    resources = output / "resources"
    shutil.copytree(old_classes, classes, dirs_exist_ok=True)
    shutil.copytree(old_resources, resources)
    metadata = resources / "fabric.mod.json"
    mod = json.loads(metadata.read_text())
    mod["entrypoints"]["preLaunch"] = ["org.livequestbench.NativePlacementTest"]
    metadata.write_text(json.dumps(mod))

    def replace_paths(value):
        return value.replace(old_classes, str(classes)).replace(old_resources, str(resources))

    classpath = os.pathsep.join(replace_paths(p) for p in configuration["classpath"])
    producer = source_root() / "src/main/java/org/livequestbench/NativeBridge.java"
    regression = root / "tests/fixtures/minecraft/NativePlacementTest.java"
    compile_result = subprocess.run(
        ["java", f"-Djava.io.tmpdir={scratch}", "-m", "jdk.compiler/com.sun.tools.javac.Main",
         "-proc:none", "-cp", classpath, "-d", str(classes),
         str(producer), str(regression)],
        capture_output=True, text=True, timeout=60,
    )
    (output / "compile.log").write_text(compile_result.stdout + compile_result.stderr)
    assert compile_result.returncode == 0, compile_result.stderr
    arguments = []
    for argument in configuration["jvm_args"]:
        if argument.startswith("-Dfabric.dli.config="):
            config = output / "launch.cfg"
            config.write_text(replace_paths(Path(argument.split("=", 1)[1]).read_text()))
            argument = "-Dfabric.dli.config=" + str(config)
        arguments.append(replace_paths(argument))
    # Yarn's package access changes require the ordinary Fabric classloader.
    # The test exits at preLaunch, before creating a client, display or world.
    result = subprocess.run(
        ["java", f"-Djava.io.tmpdir={scratch}", *arguments, "-cp", classpath,
         configuration["main_class"], *configuration["program_args"]],
        cwd=output, env={**os.environ, **configuration["environment"]},
        capture_output=True, text=True, timeout=60,
    )
    (output / "result.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "9 native placement confirmation cases passed" in result.stdout
