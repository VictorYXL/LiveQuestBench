"""Launch an explicit experiment without changing its scientific configuration."""

import argparse
import asyncio
from pathlib import Path
import sys

from benchmark.runner import run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Output root; reuse completed Episodes and retry incomplete ones")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--recording", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--recording-fps", type=int, default=10)
    parser.add_argument("--record-chat", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--storage-profile", choices=("legacy", "compact"), default="legacy")
    args = parser.parse_args()
    try:
        summary = asyncio.run(run_experiment(
            args.config, args.output, headless=args.headless,
            recording=args.recording, recording_fps=args.recording_fps, record_chat=args.record_chat,
            storage_profile=args.storage_profile,
        ))
    except KeyboardInterrupt:
        print("Benchmark interrupted; completed evidence and cancellation status were preserved.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Benchmark failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Benchmark {summary['status']}; results: {args.output.resolve() / 'summary.json'}")
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
