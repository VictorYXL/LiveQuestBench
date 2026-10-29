import copy
import importlib.util
import json
from pathlib import Path

import pytest

from game.veloren.runtime.server_extension import digest, select_server
spec = importlib.util.spec_from_file_location(
    "server_extension_fixtures", Path(__file__).with_name("test_server_extension.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def composition(tmp_path):
    server, upstream, _ = fixtures.extension(tmp_path)
    upstream_manifest = tmp_path / "upstream-runtime.json"
    upstream_manifest.write_text(json.dumps({"renderer": {"server": str(upstream)}}))
    server.update(upstream_runtime=str(upstream_manifest),
                  upstream_sha256=digest(upstream_manifest))
    base_path = tmp_path / "base_runtime"
    base = json.loads(base_path.read_text())
    base["upstream_sha256"] = server["upstream_sha256"]
    base_path.write_text(json.dumps(base))
    receipt_path = tmp_path / "build_receipt"
    receipt = json.loads(receipt_path.read_text())
    receipt["base_runtime_sha256"] = digest(base_path)
    receipt_path.write_text(json.dumps(receipt))
    for path in (base_path, receipt_path):
        server["sha256"][str(path)] = digest(path)
    renderer = tmp_path / "renderer-v2"
    renderer.write_bytes(b"separately-built-client")
    client = {
        "renderer": str(renderer), "upstream_sha256": server["upstream_sha256"],
        "upstream_runtime": str(upstream_manifest),
        "route_evidence": "native-client-route/2",
        "sha256": {str(renderer): digest(renderer)},
    }
    manifests = {}
    for name, value in (("client_runtime", client), ("server_runtime", server)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value))
        manifests[name] = str(path)
    composed = copy.deepcopy(client)
    composed.update(pickup_evidence=server["pickup_evidence"],
                    server_extension=server["server_extension"], runtime_composition=manifests)
    composed["sha256"].update(server["sha256"])
    composed["sha256"].update({path: digest(Path(path))
                              for path in manifests.values()})
    return composed, upstream


def test_composition_binds_both_manifests_without_relabeling_server_build(tmp_path):
    composed, upstream = composition(tmp_path)
    assert select_server(composed, upstream) == tmp_path / "server"


@pytest.mark.parametrize("change", ["renderer", "manifest", "upstream", "receipt"])
def test_composition_rejects_artifact_or_provenance_substitution(tmp_path, change):
    composed, upstream = composition(tmp_path)
    if change == "renderer":
        composed["renderer"] = "unrelated-client"
    elif change == "manifest":
        (tmp_path / "client_runtime.json").write_text("{}")
    elif change == "upstream":
        upstream.write_bytes(b"changed")
    else:
        (tmp_path / "build_receipt").write_text("{}")
    with pytest.raises(ValueError):
        select_server(composed, upstream)
