"""Bounded observed GUI witness; no model Baseline or structured gameplay access.

The operator uses only the reference server's admitted VM keyboard/mouse actions
and returned public images. The native evaluator alone decides task success.
"""

from pathlib import Path
import sys
import time


DEV = Path("/home/msra/GameAgent/LiveQuestBench/output/temp/task_development")


def await_finish(finished, *, seconds=540, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + seconds
    while clock() < deadline:
        if finished():
            return
        sleep(.5)
    raise TimeoutError("Observed GUI reference reached its finite control deadline")


def main(key, label):
    if key != "VE-P05" or label != "observed-loadout-reference":
        raise ValueError("This bounded observer is only for the first P05 VM witness")
    out = DEV / "experiments" / f"{key}-{label}-vm"
    await_finish((out / "operator-finished").exists)


if __name__ == "__main__":
    main(*sys.argv[1:])
