"""Pinned source metadata and non-destructive checkout preparation."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
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


def verify_checkout(source: SourceSpec, root: Path, directory: Path) -> None:
    pin = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if pin != source["commit"]:
        raise ValueError(f"Checkout {pin} differs from required {source['commit']}")
    with tempfile.TemporaryDirectory(prefix="livequest-source-") as temporary:
        env = os.environ | {"GIT_INDEX_FILE": str(Path(temporary) / "index")}
        subprocess.run(["git", "read-tree", "HEAD"], cwd=root, env=env, check=True)
        if source["patches"]:
            subprocess.run(
                ["git", "apply", "--cached", *[str((directory / name).resolve()) for name in source["patches"]]],
                cwd=root, env=env, check=True,
            )
        changed = subprocess.run(
            ["git", "diff", "--quiet", "--no-ext-diff"], cwd=root, env=env,
        )
        if changed.returncode == 1:
            raise ValueError("Checkout differs from pinned source plus declared patches")
        changed.check_returncode()


def prepare_checkout(source: SourceSpec, root: Path, directory: Path | None = None) -> None:
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
    if source["patches"]:
        if directory is None:
            raise ValueError("A patch-owning Agent directory is required")
        if not tracked_changes:
            patches = [str((directory / name).resolve()) for name in source["patches"]]
            run(["git", "apply", "--check", *patches], root)
            run(["git", "apply", *patches], root)
        verify_checkout(source, root, directory)
    elif tracked_changes:
        raise RuntimeError("Refusing to install over modified upstream source")
