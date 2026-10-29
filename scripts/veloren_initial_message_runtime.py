"""Bind isolated, fully rebuilt versioned Message binaries without changing shared runtimes."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-runtime", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", choices=("initial-message-v2", "initial-message-v3"),
                        default="initial-message-v2")
    args = parser.parse_args()
    build, output = args.build_root.resolve(), args.output.resolve()
    if read(build / "build-complete.json").get("returncode") != 0:
        raise ValueError("All isolated native builds and authorization tests must complete first")
    base = read(args.base_runtime)
    upstream_path = Path(base["upstream_runtime"])
    if digest(upstream_path) != base["upstream_sha256"]:
        raise ValueError("Pinned upstream runtime changed")
    upstream = read(upstream_path)
    original = upstream_path.parent
    content = read(original / upstream["content"]["path"])
    if digest(original / upstream["content"]["path"]) != upstream["content"]["sha256"]:
        raise ValueError("Pinned content changed")
    source = read(original / upstream["renderer"]["source_manifest"])
    files = set(source["files_sha256"]) | {
        "server/src/initial_message.rs", "rtsim/src/rule/npc_ai/initial_message.rs"}
    hashes = {name: digest(build / "source" / name) for name in sorted(files)}
    tree_hash = hashlib.sha256(
        json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    patches = Path(__file__).resolve().parents[1] / "game/veloren/patches"
    base_patch = patches / "0009-initial-message-v2.patch"
    patch = base_patch if args.protocol == "initial-message-v2" else patches / "0010-initial-message-v3.patch"
    source.update(files_sha256=hashes, source_tree_sha256=tree_hash,
                  state="Isolated initialization-only Message; not released or admitted",
                  initial_message_protocol=args.protocol,
                  initial_message_base_patch_sha256=digest(base_patch),
                  initial_message_patch_sha256=digest(patch))
    save(output / "source.json", source)
    binaries = {
        "server": build / "target/debug/veloren-server-cli",
        "renderer": build / "target/debug/veloren-voxygen",
        "helper": build / "target/debug/examples/agent_bridge",
    }
    commands = {
        "server": "cargo build --offline --locked -p veloren-server-cli -j 4",
        "helper": "cargo build --offline --locked -p veloren-client --features bin_bot --example agent_bridge -j 4",
        "renderer": "cargo build --offline --locked -p veloren-voxygen --bin veloren-voxygen "
                    "--no-default-features --features simd,shaderc-from-source -j 4",
    }
    manifest = read(original / upstream["native_interactions"]["build_manifest"])
    manifest.update(
        source_manifest_sha256=digest(output / "source.json"), source_tree_sha256=tree_hash,
        build_logs={key: digest(build / "logs" / f"{key}-build.log") for key in binaries},
        commands=list(commands.values()),
        build_provenance={
            "clean_machine_build": False, "compiler_artifacts_inherited": True,
            "compiler_cache": str(Path(base["source"]).parent),
            "initial_message_protocol": args.protocol,
            "native_unit_test_log_sha256": digest(build / "logs/native-tests.log"),
            "meaning": "All three selected native binaries rebuilt against this isolated source; "
                       "existing external toolchain, assets and dependency cache retained.",
        },
    )
    for key, name in (("server", "debug/veloren-server-cli"),
                      ("renderer", "debug/veloren-voxygen"),
                      ("helper", "debug/examples/agent_bridge")):
        manifest["binaries"][name] = {"path": str(binaries[key]), "sha256": digest(binaries[key])}
    save(output / "build.json", manifest)
    save(output / "renderer-build.json", {
        "architecture": manifest["architecture"], "source_tree_sha256": tree_hash,
        "assets_tree_sha256": manifest["assets_tree_sha256"],
        "upstream_build_manifest_sha256": digest(output / "build.json"),
        "scope": f"Source-matched {args.protocol} native build, no task admission inferred.",
    })
    save(output / "helper-build.json", {
        "schema": "rpg-renderer-fixture-helper/1", "source_tree_sha256": tree_hash,
        "executable_sha256": digest(binaries["helper"]), "source_modifications": [],
        "build_command": commands["helper"],
        "build_log_sha256": manifest["build_logs"]["helper"],
    })
    renderer = {key: str((original / value).resolve())
                for key, value in upstream["renderer"].items()}
    renderer.update(executable=str(binaries["renderer"]), server=str(binaries["server"]),
                    source_root=str(build / "source"), source_manifest=str(output / "source.json"),
                    build_receipt=str(output / "renderer-build.json"))
    upstream["renderer"] = renderer
    upstream["renderer_fixture_helper"] = {
        "executable": str(binaries["helper"]), "source_root": str(build / "source"),
        "build_receipt": str(output / "helper-build.json"),
    }
    upstream["native_interactions"] = {
        "contract": str((original / upstream["native_interactions"]["contract"]).resolve()),
        "build_manifest": str(output / "build.json"),
    }
    content["renderer"].update(source_tree_sha256=tree_hash)
    for key in ("executable", "server", "source_manifest", "build_receipt",
                "interface_contract", "assets_manifest"):
        content["renderer"][key + "_sha256"] = digest(renderer[key])
    content["renderer_fixture_helper"] = {
        "executable_sha256": digest(binaries["helper"]),
        "build_receipt_sha256": digest(output / "helper-build.json"),
        "source_tree_sha256": tree_hash,
    }
    content["native_interactions"]["build_manifest_sha256"] = digest(output / "build.json")
    save(output / "content.json", content)
    upstream["content"] = {"path": "content.json", "sha256": digest(output / "content.json")}
    upstream["output_root"] = str(output / "runs")
    save(output / "upstream-runtime.json", upstream)
    selected = deepcopy(base)
    selected.update(
        upstream_runtime=str(output / "upstream-runtime.json"),
        upstream_sha256=digest(output / "upstream-runtime.json"),
        renderer=str(binaries["renderer"]), source=str(build / "source"),
        source_manifest_sha256=digest(output / "source.json"),
        initial_message_protocol=args.protocol,
        initial_message_base_patch_sha256=digest(base_patch),
        initial_message_patch_sha256=digest(patch),
        qualification="Isolated authorized engineering version; no integration or admission",
    )
    for path in (*binaries.values(), output / "source.json", output / "build.json",
                 output / "content.json", output / "upstream-runtime.json", base_patch, patch):
        selected["sha256"][str(path)] = digest(path)
    save(output / "runtime.json", selected)
    print(output / "runtime.json")


if __name__ == "__main__":
    main()
