import json

import pytest

from game.veloren.runtime.server_extension import PICKUP_SOURCES, digest, package_server, select_server


def extension(tmp_path):
    original, modified = tmp_path / "original", tmp_path / "modified"
    for root, value in ((original, "original"), (modified, "modified")):
        for name in (*PICKUP_SOURCES, "Cargo.lock"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("unchanged" if name == "Cargo.lock" else value)
    upstream = tmp_path / "upstream"
    upstream.write_bytes(b"upstream-binary")
    paths = {name: tmp_path / name for name in (
        "server", "source_manifest", "build_receipt", "base_runtime")}
    paths["server"].write_bytes(b"extended-binary")
    paths["server"].chmod(0o755)
    paths["base_runtime"].write_text(json.dumps({
        "source": str(original), "upstream_sha256": "pinned-upstream", "renderer": "unchanged-renderer"}))
    paths["source_manifest"].write_text(json.dumps({
        "source_root": str(modified),
        "base_files_sha256": {name: digest(original / name) for name in (*PICKUP_SOURCES, "Cargo.lock")},
        "files_sha256": {name: digest(modified / name) for name in (*PICKUP_SOURCES, "Cargo.lock")},
    }))
    paths["build_receipt"].write_text(json.dumps({
        "schema": "livequest-native-server-extension/1",
        "base_runtime_sha256": digest(paths["base_runtime"]),
        "base_server_sha256": digest(upstream),
        "server_sha256": digest(paths["server"]),
        "source_manifest_sha256": digest(paths["source_manifest"]),
        "capability": "native-server-pickups/1",
        "build_command": ["cargo", "build", "--offline", "--locked", "-p", "veloren-server-cli", "-j", "2"],
    }))
    return {
        "server_extension": {name: str(path) for name, path in paths.items()},
        "sha256": {str(path): digest(path) for path in paths.values()},
        "pickup_evidence": "native-server-pickups/1",
        "upstream_sha256": "pinned-upstream", "renderer": "unchanged-renderer",
    }, upstream, modified


def test_unextended_runtime_preserves_upstream_server(tmp_path):
    assert select_server({}, tmp_path / "server") == tmp_path / "server"
    with pytest.raises(ValueError, match="requires"):
        select_server({"pickup_evidence": "native-server-pickups/1"}, tmp_path / "server")


def test_extension_preserves_client_and_exact_source_scope(tmp_path):
    config, upstream, _ = extension(tmp_path)
    assert select_server(config, upstream) == tmp_path / "server"
    config["renderer"] = "unrelated-renderer"
    with pytest.raises(ValueError, match="provenance"):
        select_server(config, upstream)


@pytest.mark.parametrize("change", ["server", "source", "extra_source", "upstream"])
def test_extension_rejects_changed_artifacts_and_unmanifested_source(tmp_path, change):
    config, upstream, modified = extension(tmp_path)
    path = {
        "server": tmp_path / "server", "source": modified / "Cargo.lock",
        "extra_source": modified / "extra.rs", "upstream": upstream,
    }[change]
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        select_server(config, upstream)


def test_packaging_retains_base_provenance_and_refuses_existing_destination(tmp_path):
    _, upstream, modified = extension(tmp_path)
    upstream_manifest = tmp_path / "upstream-runtime.json"
    upstream_manifest.write_text(json.dumps({"renderer": {"server": str(upstream)}}))
    base_path = tmp_path / "base_runtime"
    base = json.loads(base_path.read_text())
    base.update(upstream_runtime=str(upstream_manifest),
                upstream_sha256=digest(upstream_manifest), sha256={})
    base_path.write_text(json.dumps(base))
    original_bytes = base_path.read_bytes()
    log = tmp_path / "build.log"
    log.write_text("test build log, not native evidence")
    output = tmp_path / "packaged"
    arguments = (base_path, modified, tmp_path / "server", log, output)
    runtime = package_server(*arguments, jobs=2, toolchain="test-toolchain")
    config = json.loads(runtime.read_text())
    assert select_server(config, upstream) == tmp_path / "server"
    assert config["renderer"] == base["renderer"]
    assert base_path.read_bytes() == original_bytes
    with pytest.raises(FileExistsError):
        package_server(*arguments, jobs=2, toolchain="test-toolchain")
    assert select_server(json.loads(runtime.read_text()), upstream) == tmp_path / "server"


def test_packaging_rejects_shared_source_before_writing(tmp_path):
    _, _, _ = extension(tmp_path)
    output = tmp_path / "never-created"
    with pytest.raises(ValueError, match="independent source"):
        package_server(tmp_path / "base_runtime", tmp_path / "original",
                       tmp_path / "server", tmp_path / "unused.log", output,
                       jobs=2, toolchain="test-toolchain")
    assert not output.exists()
