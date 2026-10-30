"""Explicit, isolated installation of the pinned DeepSeek harness runtime."""

import argparse
from pathlib import Path
import subprocess

from agent_framework.utils.source import load_source, prepare_checkout, run


def main() -> None:
    source = load_source(Path(__file__).parent)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Dedicated external checkout, not this repository")
    parser.add_argument("--pnpm", type=Path, help="Prepared pnpm 11.28.5 JavaScript entrypoint")
    parser.add_argument("--offline-store", type=Path, help="Complete pinned dependency store; prohibit downloads")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.offline_store is not None and args.pnpm is None:
        parser.error("--offline-store requires --pnpm to avoid network bootstrapping")
    pnpm = ["node", str(args.pnpm.resolve())] if args.pnpm else ["npx", "--yes", "pnpm@11.28.5"]
    if args.pnpm and subprocess.check_output([*pnpm, "--version"], text=True).strip() != "11.28.5":
        raise RuntimeError("Prepared pnpm must match the pinned version 11.28.5")
    prepare_checkout(source, root)
    options = ["--offline", "--store-dir", str(args.offline_store.resolve())] if args.offline_store else []
    run([*pnpm, "install", "--frozen-lockfile", "--ignore-scripts", *options,
         "--filter", "@deepseek-ai/dsh-agent-loop...", "--filter", "@deepseek-ai/dsh-tools...",
         "--filter", "@deepseek-ai/dsh-typert-generator..."], root)
    run([*pnpm, "exec", "tsc", "-b", "packages/core/agent-loop/tsconfig.json",
         "packages/typert/generator/tsconfig.json"], root)
    entries = sorted([*root.glob("packages/*/*/lib/types/index.js"),
                      *root.glob("vendor/*/lib/types/index.js")])
    if not entries:
        raise RuntimeError("TypeScript build produced no package entrypoints")
    command = [str(root / "node_modules/.bin/tsdown"), "--config-loader", "native",
               "--env.DSH_BUILD_FACE", "host", "--logLevel", "error"]
    for entry in entries:
        command.extend(["--filter", str(entry.parents[2].relative_to(root))])
    run(command, root)
    print(f"Prepared DeepSeek harness at {source['commit']}")
    print(f"Set {source['environment']}={root}")


if __name__ == "__main__":
    main()
