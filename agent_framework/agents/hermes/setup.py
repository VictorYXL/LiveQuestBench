"""Explicit, isolated installation of the pinned Hermes runtime."""

import argparse
from pathlib import Path

from agent_framework.utils.source import load_source, prepare_checkout, run


def main() -> None:
    source = load_source(Path(__file__).parent)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Dedicated Hermes source checkout")
    root = parser.parse_args().root.resolve()
    prepare_checkout(source, root)
    run(["uv", "sync", "--project", str(root), "--python", "3.14", "--locked", "--no-default-groups"])
    print(f"Prepared Hermes at {source['commit']}")
    print(f"Set {source['environment']}={root}")


if __name__ == "__main__":
    main()
