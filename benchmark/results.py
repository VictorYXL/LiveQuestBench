"""Persistent private evidence and summaries, separate from Agent inputs."""

from collections import Counter
from dataclasses import asdict, is_dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from agent_framework.llm_client.base_client import Message, RequestEvent


def write_json(path: Path, value: object) -> None:
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    pending.replace(path)


class EpisodeLog:
    def __init__(self, root: Path):
        self.root = root
        self.requests: list[RequestEvent] = []
        self.tool_calls = 0
        self.observations = 0

    def encode(self, value: object) -> object:
        if isinstance(value, bytes):
            digest = hashlib.sha256(value).hexdigest()
            suffix = ".png" if value.startswith(b"\x89PNG") else ".bin"
            path = self.root / "images" / (digest + suffix)
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                path.write_bytes(value)
            return {"path": str(path.relative_to(self.root)), "sha256": digest, "bytes": len(value)}
        if is_dataclass(value) and not isinstance(value, type):
            return self.encode(asdict(value))
        if isinstance(value, dict):
            return {key: self.encode(child) for key, child in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.encode(child) for child in value]
        return value

    def event(self, kind: str, **data: object) -> None:
        row = self.encode({"event": kind, "at_ns": time.monotonic_ns(), **data})
        with (self.root / "trace.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")

    def message(self, message: Message) -> None:
        self.event("message", message=message)

    def request(self, event: RequestEvent) -> None:
        self.requests.append(event)
        self.event("model_request", request=event)

    def accounting(self) -> dict:
        known: Counter[str] = Counter()
        missing: Counter[str] = Counter()
        aliases = {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens", "total_tokens": "total_tokens"}
        for event in self.requests:
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = event.usage.get(key, event.usage.get(aliases[key])) if event.usage is not None else None
                if type(value) is int and value >= 0:
                    known[key] += value
                else:
                    missing[key] += 1
        return {
            "request_attempts": len(self.requests),
            "successful_attempts": sum(event.success for event in self.requests),
            "request_wall_seconds": sum(event.elapsed_seconds for event in self.requests),
            "usage": {
                key: {"reported_sum": known[key] if missing[key] < len(self.requests) else None,
                      "unknown_attempts": missing[key]}
                for key in ("input_tokens", "output_tokens", "total_tokens")
            },
            "cost_usd": None, "tool_calls": self.tool_calls, "observations": self.observations,
        }


def provenance() -> dict:
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.run(
        ["git", "--no-pager", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "--no-pager", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout
    files = [root / name for name in ("run_benchmark.py", "pyproject.toml", "uv.lock")]
    for directory in ("benchmark", "game", "agent_framework"):
        files.extend(path for path in (root / directory).rglob("*")
                     if path.is_file() and path.suffix in (".py", ".mjs", ".json", ".patch")
                     and "node_modules" not in path.parts and ".venv" not in path.parts)
    return {
        "revision": revision, "worktree_status": status,
        "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(files)},
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in ("httpx", "pyyaml")},
    }


def summarize(episodes: list[dict]) -> dict:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in episodes:
        groups.setdefault((row["game"], row["task_id"], row["task_type"]), []).append(row)
    summaries = []
    for (game, task, mode), rows in groups.items():
        valid = [row for row in rows if row["status"] == "completed" and row.get("measurement") == "valid"]
        successes = sum(row.get("task_outcome") == "success" for row in valid)
        summaries.append({
            "game": game, "task_id": task, "task_type": mode, "scheduled": len(rows),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "valid_completed": len(valid), "successes": successes,
            "success_rate_valid_completed": successes / len(valid) if valid else None,
        })
    return {"groups": summaries, "episodes": episodes}
