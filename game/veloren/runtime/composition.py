"""Explicit composition of separately pinned client and passive server builds.

Artifact admission preserves both original manifests; native protocol compatibility
and task feasibility still require an actual episode with this composition.
"""

import copy
import json
from pathlib import Path

from .server_extension import digest


def compose(client_path: Path, server_path: Path) -> dict:
    client_path, server_path = client_path.resolve(), server_path.resolve()
    client, server = (json.loads(path.read_text()) for path in (client_path, server_path))
    for manifest in (client, server):
        if "runtime_composition" in manifest:
            raise ValueError("Nested runtime composition is not supported")
        for path, expected in manifest["sha256"].items():
            if digest(Path(path)) != expected:
                raise ValueError(f"Runtime composition artifact changed: {path}")
    if "server_extension" in client or client.get("pickup_evidence"):
        raise ValueError("Client manifest must not already select a server extension")
    if (client["upstream_runtime"] != server["upstream_runtime"]
            or client["upstream_sha256"] != server["upstream_sha256"]
            or digest(Path(client["upstream_runtime"])) != client["upstream_sha256"]
            or client["sha256"].get(client["renderer"]) != digest(Path(client["renderer"]))):
        raise ValueError("Runtime composition client/upstream provenance mismatch")
    result = copy.deepcopy(client)
    for name in ("pickup_evidence", "server_extension"):
        result[name] = server[name]
    for path, expected in server["sha256"].items():
        if path in result["sha256"] and result["sha256"][path] != expected:
            raise ValueError("Runtime composition artifact pins conflict")
        result["sha256"][path] = expected
    result["runtime_composition"] = {
        "client_runtime": str(client_path), "server_runtime": str(server_path)}
    for path in (client_path, server_path):
        result["sha256"][str(path)] = digest(path)
    return result


def select_composed_server(config: dict, upstream: Path) -> Path:
    from .server_extension import select_server

    manifests = config["runtime_composition"]
    if set(manifests) != {"client_runtime", "server_runtime"}:
        raise ValueError("Incomplete runtime composition binding")
    for path in manifests.values():
        if config["sha256"].get(path) != digest(Path(path)):
            raise ValueError("Runtime composition manifest changed")
    expected = compose(Path(manifests["client_runtime"]), Path(manifests["server_runtime"]))
    if expected != config:
        raise ValueError("Runtime composition does not match its immutable inputs")
    # Validate the original server manifest, including its unchanged renderer
    # equality guard and complete source scope, rather than relabel its build.
    server = json.loads(Path(manifests["server_runtime"]).read_text())
    return select_server(server, upstream)
