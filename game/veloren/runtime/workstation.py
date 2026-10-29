"""Exact original-workstation runtime; never a generic route/2 downgrade."""

import hashlib
import json


PROFILE = "directions-to-workstation/1"
ENVIRONMENT = "LIVEQUEST_VELOREN_WORKSTATION_RUNTIME"
RUNTIME_SHA256 = "387e3485fb1fa1edcfb810e36ed2f1cef4d07bfeb487f73d8be433fd82e653d7"
CONFIG_SHA256 = "82b8d789d6a3523e04a737623a5d595bedac3b004c576e42ece843a63725fe44"


def expected_route_schema(fixture: dict, config: dict) -> str:
    if fixture.get("runtime_profile") != PROFILE:
        return "native-client-route/2"
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(encoded).hexdigest() != CONFIG_SHA256:
        raise ValueError("Workstation requires its exact independently qualified runtime")
    return "native-client-route/1"
