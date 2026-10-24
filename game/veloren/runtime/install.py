"""Prepare an isolated native renderer from a verified VelorenBench build cache."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installation", type=Path, required=True)
    parser.add_argument("--build-cache", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    root, cache = args.root.resolve(), args.build_cache.resolve()
    if root == cache or root.is_relative_to(cache) or cache.is_relative_to(root):
        raise ValueError("Use an independent output root, not the original build cache")
    root.parent.mkdir(parents=True, exist_ok=True)
    installation = json.loads(args.installation.read_text())
    upstream = Path(installation["runtime"])
    if digest(upstream) != installation["runtime_sha256"]:
        raise ValueError("VelorenBench runtime configuration changed")
    bindings = json.loads(upstream.read_text())
    source_manifest = upstream.parent / bindings["renderer"]["source_manifest"]
    original_source = upstream.parent / bindings["renderer"]["source_root"]
    hashes = json.loads(source_manifest.read_text())["files_sha256"]
    patch = Path(__file__).parents[1] / "patches/0001-physical-input.patch"
    protection_patch = patch.with_name("0002-disable-native-protection.patch")
    motion_patch = patch.with_name("0003-native-motion-evidence.patch")
    glide_patch = patch.with_name("0004-native-glide-evidence.patch")
    changed = ("voxygen/src/native_agent.rs", "voxygen/src/session/mod.rs",
               "client/src/agent_protocol/continuous_control.rs")
    with tempfile.TemporaryDirectory(prefix="veloren-patch-", dir=root.parent) as temporary:
        expected = Path(temporary)
        for name in changed:
            if digest(original_source / name) != hashes[name]:
                raise ValueError(f"Bound original source changed: {name}")
            target = expected / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_source / name, target)
        subprocess.run(["patch", "--batch", "-p1", "-i", str(patch.resolve())], cwd=expected, check=True)
        physical_only = hashes | {name: digest(expected / name) for name in changed}
        subprocess.run(["patch", "--batch", "-p1", "-i", str(protection_patch.resolve())], cwd=expected, check=True)
        without_motion = hashes | {name: digest(expected / name) for name in changed}
        subprocess.run(["patch", "--batch", "-p1", "-i", str(motion_patch.resolve())], cwd=expected, check=True)
        without_glide = hashes | {name: digest(expected / name) for name in changed}
        subprocess.run(["patch", "--batch", "-p1", "-i", str(glide_patch.resolve())], cwd=expected, check=True)
        patched = hashes | {name: digest(expected / name) for name in changed}
    if not root.exists():
        shutil.copytree(cache, root, symlinks=False)
    if any(not (root / "source" / name).resolve().is_relative_to(root / "source") for name in hashes):
        raise ValueError("Prepared source must not link outside its independent source directory")
    current = {name: digest(root / "source" / name) for name in hashes}
    if current == hashes:
        subprocess.run(["patch", "--batch", "-p1", "-i", str(patch.resolve())], cwd=root / "source", check=True)
        current = physical_only
    if current == physical_only:
        subprocess.run(["patch", "--batch", "-p1", "-i", str(protection_patch.resolve())],
                       cwd=root / "source", check=True)
        current = without_motion
    if current == without_motion:
        subprocess.run(["patch", "--batch", "-p1", "-i", str(motion_patch.resolve())],
                       cwd=root / "source", check=True)
        current = without_glide
    if current == without_glide:
        subprocess.run(["patch", "--batch", "-p1", "-i", str(glide_patch.resolve())],
                       cwd=root / "source", check=True)
    elif current != patched:
        raise ValueError("Build source differs from the selected source plus declared patch")
    if {name: digest(root / "source" / name) for name in hashes} != patched:
        raise ValueError("Applied patch does not match the declared source transformation")
    receipt = json.loads((cache / "receipt.json").read_text())
    environment = {**os.environ, **receipt["environment"]}
    for key, child in (("HOME", "home"), ("TMPDIR", "tmp"), ("CARGO_HOME", "cargo"),
                       ("CARGO_TARGET_DIR", "target")):
        environment[key] = str(root / child)
    cargo = Path(receipt["commands"][1]["argv"][0])
    with (root / "logs/livequest-build.log").open("ab") as log:
        subprocess.run([
            str(cargo), "build", "--offline", "--locked", "-p", "veloren-voxygen",
            "--bin", "veloren-voxygen", "--no-default-features", "--features", "simd,shaderc-from-source",
            "-j", str(args.jobs),
        ], cwd=root / "source", env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
    executable = root / "target/debug/veloren-voxygen"
    record = {
        "schema": "livequest-veloren-runtime/1", "python": installation["python"],
        "upstream_runtime": str(upstream), "upstream_sha256": digest(upstream),
        "renderer": str(executable), "source": str(root / "source"),
        "source_manifest_sha256": digest(source_manifest), "patch_sha256": digest(patch),
        "protection_patch_sha256": digest(protection_patch),
        "motion_patch_sha256": digest(motion_patch), "motion_evidence": "native-client-motion/1",
        "glide_patch_sha256": digest(glide_patch), "glide_evidence": "native-client-glide/1",
        "native_protection": "disabled by explicit renderer launch environment",
        "compiler_cache": str(cache), "qualification": "requires LiveQuestBench real-game checks",
        "sha256": {str(path.resolve()): digest(path)
                   for path in (executable, patch, protection_patch, motion_patch, glide_patch, source_manifest)},
    }
    pending = root / ".runtime.json.tmp"
    pending.write_text(json.dumps(record, indent=2) + "\n")
    pending.replace(root / "runtime.json")
    print(f"Set LIVEQUEST_VELOREN_RUNTIME={root / 'runtime.json'}")


if __name__ == "__main__":
    main()
