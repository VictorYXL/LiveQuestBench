"""Narrow, noncanonical asset admission for the approved L03 response experiment."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import shutil

from game.veloren.runtime.combat_response_assets import ABILITY_PATH, build_candidate, render_response
from game.veloren.runtime.combat_source_binding import digest, relative_path


SCHEMA = "veloren-experimental-combat-response-assets/1"


def tree_digest(files: dict) -> str:
    return sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def admit_response_assets(declaration: dict, baseline_assets: Path, baseline_manifest: Path) -> dict:
    if set(declaration) != {"schema", "assets", "manifest", "manifest_sha256", "selection"}:
        raise ValueError("Experimental response assets require the exact narrow declaration")
    if declaration["schema"] != SCHEMA:
        raise ValueError("Unsupported experimental response asset schema")
    root = Path(declaration["assets"])
    manifest_path = Path(declaration["manifest"])
    for path in (root, manifest_path):
        if (not path.is_absolute() or ".." in path.parts
                or any(part.is_symlink() for part in (path, *path.parents))):
            raise ValueError("Experimental asset bindings must be absolute and not symlinks")
    if root.name != "assets" or root == baseline_assets.resolve() or baseline_assets.resolve() in root.parents:
        raise ValueError("Experimental assets need a separate private assets root")
    if digest(manifest_path) != declaration["manifest_sha256"]:
        raise ValueError("Experimental asset manifest changed")
    stock = json.loads(baseline_manifest.read_text())
    candidate = json.loads(manifest_path.read_text())
    expected = dict(stock["files_sha256"])
    ability = render_response((baseline_assets / ABILITY_PATH).read_bytes(), declaration["selection"])
    expected[ABILITY_PATH.as_posix()] = sha256(ability).hexdigest()
    if candidate != {"files_sha256": expected, "tree_sha256": tree_digest(expected)}:
        raise ValueError("Experimental manifest changes more than the reviewed response ability")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Experimental assets may not alias writable shared files")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            relative_path(name)
            files[name] = digest(path)
    if files != expected:
        raise ValueError("Experimental asset bytes differ from the pinned complete inventory")
    return {
        "schema": SCHEMA, "assets": str(root), "manifest_sha256": declaration["manifest_sha256"],
        "assets_tree_sha256": candidate["tree_sha256"], "ability_sha256": expected[ABILITY_PATH.as_posix()],
        "baseline_assets": str(baseline_assets), "selection": declaration["selection"],
        "scope": "Private configured-input admission, not observed native response or learning evidence",
    }


def prepare_runtime(source_runtime: Path, output: Path, seed: int) -> dict:
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("The authoring seed must be a u64")
    original = json.loads(source_runtime.read_text())
    upstream_path = Path(original["upstream_runtime"])
    if digest(upstream_path) != original["upstream_sha256"]:
        raise ValueError("Upstream runtime changed")
    upstream = json.loads(upstream_path.read_text())

    def bound(value):
        path = Path(value)
        return path if path.is_absolute() else upstream_path.parent / path

    baseline_assets = bound(upstream["renderer"]["assets"])
    baseline_manifest = bound(upstream["renderer"]["assets_manifest"])
    output = output.resolve()
    if output == baseline_assets or baseline_assets in output.parents:
        raise ValueError("Never prepare a runtime inside shared assets")
    output.mkdir(parents=True, exist_ok=False)
    candidate = build_candidate(baseline_assets, output / "candidate", seed)
    assets = output / "assets"
    shutil.copytree(baseline_assets, assets)
    (assets / ABILITY_PATH).write_bytes((output / "candidate" / candidate["overlay_asset"]).read_bytes())
    files = dict(json.loads(baseline_manifest.read_text())["files_sha256"])
    files[ABILITY_PATH.as_posix()] = candidate["candidate_sha256"]
    manifest = output / "assets-manifest.json"
    manifest.write_text(json.dumps({"files_sha256": files, "tree_sha256": tree_digest(files)}, indent=2) + "\n")
    declaration = {
        "schema": SCHEMA, "assets": str(assets), "manifest": str(manifest),
        "manifest_sha256": digest(manifest),
        "selection": random.Random(seed).randrange(2),
    }
    admission = admit_response_assets(declaration, baseline_assets, baseline_manifest)
    configured = deepcopy(original)
    configured["experimental_combat_response_assets"] = declaration
    configured["sha256"][str(manifest)] = digest(manifest)
    runtime = output / "runtime.json"
    runtime.write_text(json.dumps(configured, indent=2) + "\n")
    receipt = {
        "schema": "noncanonical-combat-response-runtime/1",
        "source_runtime": str(source_runtime.resolve()), "source_runtime_sha256": digest(source_runtime),
        "runtime": str(runtime), "runtime_sha256": digest(runtime),
        "assets": admission, "private_authoring_seed": seed,
        "binary_changes": False, "native_execution": "not_run",
        "scope": "New asset distribution only; original binary/build receipts remain unchanged",
    }
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
