"""Local account and runtime bindings for a single game session."""

import json
import hashlib
import re
from uuid import UUID
from game.minecraft.runtime.install import prism_root


def offline_identity(name: str = "LiveQuestBot") -> dict[str, str]:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,16}", name):
        raise ValueError("Offline player name must be 1-16 letters, digits or underscores")
    digest = hashlib.md5(f"OfflinePlayer:{name}".encode("utf-8"), usedforsecurity=False).digest()
    return {"player_name": name, "player_uuid": str(UUID(bytes=digest, version=3))}


def resolve_account(account: str | None = None) -> dict[str, str]:
    """Select public Minecraft profile identity; never return or copy credentials."""
    path = prism_root() / "accounts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = [
        entry["profile"] for entry in data["accounts"]
        if entry.get("type") == "MSA" and entry.get("profile")
    ]
    if account is not None:
        profiles = [profile for profile in profiles if profile["name"].casefold() == account.casefold()]
    if len(profiles) != 1:
        raise ValueError(
            "Select exactly one signed-in Minecraft account with runtime.account (profile name); "
            f"found {len(profiles)} matching profiles"
        )
    return {"player_name": profiles[0]["name"], "player_uuid": profiles[0]["id"]}
