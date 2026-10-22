"""Use the production Agent roster and benchmark-owned stop behavior in live tests."""

from benchmark.factory import NATIVE_AGENTS
from benchmark.runner import run_bounded

__all__ = ["NATIVE_AGENTS", "run_bounded"]
