"""Private, episode-fixed selection of the four audit93 C1 runtime bindings."""

import hashlib
import json
import os
from pathlib import Path
import secrets


PROFILE = "committed-second-strike-v1"
ENVIRONMENT = "LIVEQUEST_VELOREN_COMBAT_RESPONSE_RUNTIME_ROOT"
RUNTIMES = {
    "visual_motor": (
        ("native-runtime-parameter-a", "243e4a823839837cdc68388cc7a95639104f5f1b013086f9475fe3530f52be33"),
        ("native-runtime-parameter-b", "40e55d0af98a45c2c485c4725e7ed8b525609e0e8d0285c06e2002e06b0dcb92"),
    ),
    "structured_tool": (
        ("native-runtime-parameter-a-item-preflight-v1", "72490955c65c013e21ea3ffbe6a39ba9cdcd1a37a4c0e6de8b2874d9107b5cff"),
        ("native-runtime-parameter-b-item-preflight-v1", "625dd75da3d0ecbf2fed4ad5db1badb21eda648c71719a4f67baaeb17da19fb3"),
    ),
}


def validate_profile(fixture: dict) -> None:
    if fixture.get("experimental_combat_response") != PROFILE:
        raise ValueError("Unsupported C1 combat response profile")
    if {
        "runtime_profile", "message_contract", "market", "route_observation",
        "camera_observation", "scene_observation", "route_evidence", "pickup_evidence",
        "motion_evidence", "glide_evidence", "peer_group",
    } & fixture.keys():
        raise ValueError("C1 combat response cannot share another runtime/evidence profile")


def select_runtime(fixture: dict, track: str) -> tuple[Path, dict]:
    validate_profile(fixture)
    if track not in RUNTIMES:
        raise ValueError("C1 requires an explicit supported track")
    selected = os.environ.get(ENVIRONMENT)
    if not selected:
        raise RuntimeError(f"Set {ENVIRONMENT} to the directory containing the prepared runtime variants")
    root = Path(selected).expanduser().resolve()
    # Validate both options before drawing: unavailable A must never become B-only.
    choices = []
    for selection, (directory, expected) in enumerate(RUNTIMES[track]):
        path = root / directory / "runtime.json"
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != expected:
            raise ValueError("C1 requires both exact audit93 runtime files")
        runtime = json.loads(encoded)
        if runtime["experimental_combat_response_assets"]["selection"] != selection:
            raise ValueError("C1 runtime selection does not match the reviewed family")
        choices.append((path, runtime))
    return choices[secrets.randbelow(2)]


def bind_assets(config: dict, fixture: dict, paths: dict, output: Path) -> None:
    declared = "experimental_combat_response_assets" in config
    requested = "experimental_combat_response" in fixture
    if declared != requested:
        raise ValueError("Experimental response requires both explicit task and runtime bindings")
    if not requested:
        return
    validate_profile(fixture)
    from game.veloren.prototypes.combat_response_runtime import admit_response_assets
    admission = admit_response_assets(
        config["experimental_combat_response_assets"], Path(paths["assets"]),
        Path(paths["assets_manifest"]),
    )
    paths["assets"] = admission["assets"]
    (output / "experimental-assets-admission.json").write_text(json.dumps(admission, indent=2) + "\n")
