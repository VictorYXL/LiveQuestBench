"""Prepare GamingAgent's pinned source, declared patch and isolated runtime."""

import argparse
from pathlib import Path

from agent_framework.utils.source import load_source, prepare_checkout, run


def main() -> None:
    directory = Path(__file__).parent
    source = load_source(directory)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root.resolve()
    prepare_checkout(source, root, directory)
    if not (root / ".venv/bin/python").is_file():
        run(["uv", "venv", "--python", "3.11", str(root / ".venv")])
    run(["uv", "pip", "sync", "--python", str(root / ".venv/bin/python"),
         str(directory / "requirements.lock")])
    print(f"Prepared GamingAgent at {source['commit']} plus declared patches")
    print(f"Set {source['environment']}={root}")


if __name__ == "__main__":
    main()
