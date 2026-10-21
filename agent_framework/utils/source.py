"""Pinned source metadata and non-destructive checkout preparation."""

import json
from pathlib import Path
import subprocess
from typing import TypedDict


class SourceSpec(TypedDict):
    repository: str
    commit: str
    license: str
    environment: str
    patches: list[str]


def load_source(directory: Path) -> SourceSpec:
    return json.loads((directory / "source.json").read_text(encoding="utf-8"))


def run(arguments: list[str], root: Path | None = None) -> None:
    subprocess.run(arguments, cwd=root, check=True)


def prepare_checkout(source: SourceSpec, root: Path) -> None:
    if not root.exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", source["repository"], str(root)])
        run(["git", "checkout", "--detach", source["commit"]], root)
    pin = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if pin != source["commit"]:
        raise RuntimeError("Existing checkout has a different commit; choose a new dedicated root")
    tracked_changes = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True,
    )
    if tracked_changes:
        raise RuntimeError("Refusing to install over modified upstream source")
    if source["patches"]:
        raise RuntimeError("This integration version expects unmodified upstream source")
