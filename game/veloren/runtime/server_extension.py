"""Admit an isolated passive server extension without relabeling client/helper provenance.

To prepare pickup evidence, copy the base runtime's source and compiler caches to
an independent directory, apply patches/0007-native-pickups.patch there, and build
only veloren-server-cli with ``cargo build --offline --locked -p
veloren-server-cli -j JOBS``. Keep CARGO_HOME, CARGO_TARGET_DIR and TMPDIR private.
This module's CLI packages that build and its log; it does not rebuild or modify
the base renderer, helper, server or source. Compilation/metadata admission alone
does not certify native compatibility or task feasibility.
"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path


PICKUP_SOURCES = frozenset({
    "server/src/events/inventory_manip.rs", "server/src/sys/object.rs",
    "server/src/sys/item.rs", "server/src/state_ext.rs",
})


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_server(config: dict, upstream: Path) -> Path:
    if "runtime_composition" in config:
        from .composition import select_composed_server
        return select_composed_server(config, upstream)
    extension = config.get("server_extension")
    if extension is None:
        if config.get("pickup_evidence"):
            raise ValueError("Pickup evidence requires a pinned native server extension")
        return upstream
    if config.get("pickup_evidence") != "native-server-pickups/1":
        raise ValueError("Unknown native server extension capability")
    if set(extension) != {"server", "source_manifest", "build_receipt", "base_runtime"}:
        raise ValueError("Incomplete native server extension binding")
    paths = {name: Path(value).resolve() for name, value in extension.items()}
    for path in paths.values():
        if config["sha256"].get(str(path)) != digest(path):
            raise ValueError(f"Unpinned native server extension file: {path}")
    base = json.loads(paths["base_runtime"].read_text())
    receipt = json.loads(paths["build_receipt"].read_text())
    manifest = json.loads(paths["source_manifest"].read_text())
    command = receipt.get("build_command")
    valid_command = (
        isinstance(command, list) and len(command) == 8
        and command[:7] == ["cargo", "build", "--offline", "--locked", "-p", "veloren-server-cli", "-j"]
        and isinstance(command[7], str) and command[7].isascii() and command[7].isdecimal()
        and int(command[7]) > 0
    )
    if (base["upstream_sha256"] != config["upstream_sha256"]
            or base["renderer"] != config["renderer"]
            or receipt.get("schema") != "livequest-native-server-extension/1"
            or receipt.get("base_runtime_sha256") != digest(paths["base_runtime"])
            or receipt.get("base_server_sha256") != digest(upstream)
            or receipt.get("server_sha256") != digest(paths["server"])
            or receipt.get("source_manifest_sha256") != digest(paths["source_manifest"])
            or receipt.get("capability") != config["pickup_evidence"] or not valid_command
            or not os.access(paths["server"], os.X_OK)):
        raise ValueError("Native server extension provenance mismatch")
    original, modified = manifest["base_files_sha256"], manifest["files_sha256"]
    if (original.keys() != modified.keys()
            or {name for name in original if original[name] != modified[name]} != PICKUP_SOURCES):
        raise ValueError("Server extension changes files outside its passive pickup scope")
    for root, files in ((Path(base["source"]), original), (Path(manifest["source_root"]), modified)):
        actual = {
            str(path.relative_to(root)) for path in root.rglob("*")
            if ".git" not in path.relative_to(root).parts and path.is_file()
        }
        if actual != set(files):
            raise ValueError("Incomplete native server extension source manifest")
        for name, expected in files.items():
            path = root / name
            if Path(name).is_absolute() or ".." in Path(name).parts or digest(path) != expected:
                raise ValueError(f"Server extension source changed: {name}")
    return paths["server"]


def package_server(base_path: Path, source: Path, server: Path, build_log: Path,
                   output: Path, *, jobs: int, toolchain: str) -> Path:
    if jobs < 1 or not toolchain.strip():
        raise ValueError("A positive build job count and recorded toolchain are required")
    base_path, source, server, build_log, output = (
        path.resolve() for path in (base_path, source, server, build_log, output))
    base = json.loads(base_path.read_text())
    base_source = Path(base["source"]).resolve()
    if source == base_source or source.is_relative_to(base_source) or base_source.is_relative_to(source):
        raise ValueError("Use an independent source directory")
    if output == base_path.parent or output.is_relative_to(base_source) or output.is_relative_to(source):
        raise ValueError("Do not package into the base runtime or source")
    upstream_path = Path(base["upstream_runtime"])
    if digest(upstream_path) != base["upstream_sha256"]:
        raise ValueError("Base upstream runtime changed")
    bindings = json.loads(upstream_path.read_text())
    upstream = Path(bindings["renderer"]["server"])
    if not upstream.is_absolute():
        upstream = upstream_path.parent / upstream
    if server == upstream.resolve() or server == Path(base["renderer"]).resolve():
        raise ValueError("The extension must not replace an admitted upstream binary")

    def files(root):
        return {str(path.relative_to(root)): digest(path)
                for path in sorted(root.rglob("*"))
                if path.is_file() and ".git" not in path.relative_to(root).parts}

    original, modified = files(base_source), files(source)
    if (original.keys() != modified.keys()
            or {name for name in original if original[name] != modified[name]} != PICKUP_SOURCES):
        raise ValueError("Server extension changes files outside its passive pickup scope")
    # Do not silently overwrite metadata that an allocated episode may be reading.
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "source-manifest.json"
    manifest.write_text(json.dumps({
        "source_root": str(source), "base_files_sha256": original, "files_sha256": modified,
    }, indent=2) + "\n")
    receipt = output / "build-receipt.json"
    receipt.write_text(json.dumps({
        "schema": "livequest-native-server-extension/1",
        "base_runtime_sha256": digest(base_path), "base_server_sha256": digest(upstream),
        "server_sha256": digest(server), "source_manifest_sha256": digest(manifest),
        "capability": "native-server-pickups/1",
        "build_command": ["cargo", "build", "--offline", "--locked", "-p",
                          "veloren-server-cli", "-j", str(jobs)],
        "build_log_sha256": digest(build_log), "toolchain": toolchain,
        "qualification": "Metadata packaging is not native runtime or gameplay qualification.",
    }, indent=2) + "\n")
    config = copy.deepcopy(base)
    config["pickup_evidence"] = "native-server-pickups/1"
    config["server_extension"] = {
        "server": str(server), "source_manifest": str(manifest),
        "build_receipt": str(receipt), "base_runtime": str(base_path),
    }
    config["sha256"].update({str(path): digest(path) for path in
                            (server, manifest, receipt, base_path)})
    select_server(config, upstream)
    runtime = output / "runtime.json"
    runtime.write_text(json.dumps(config, indent=2) + "\n")
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-runtime", "source", "server", "build-log", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--toolchain", required=True)
    args = parser.parse_args()
    runtime = package_server(args.base_runtime, args.source, args.server, args.build_log,
                             args.output, jobs=args.jobs, toolchain=args.toolchain)
    print(f"Metadata admitted; native qualification still required. LIVEQUEST_VELOREN_RUNTIME={runtime}")


if __name__ == "__main__":
    main()
