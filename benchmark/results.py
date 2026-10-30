"""Persistent private evidence and summaries, separate from Agent inputs."""

from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
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
    def __init__(self, root: Path, *, record_chat: bool = True, storage_profile: str = "legacy"):
        if storage_profile not in {"legacy", "compact"}:
            raise ValueError("Unknown storage profile")
        if storage_profile == "compact" and not record_chat:
            raise ValueError("Compact evidence requires chat recording")
        self.directory = root / "recording" / "chat"
        self.record_chat = record_chat
        self.storage_profile = storage_profile
        from benchmark.compact import CompactLog
        self.compact = CompactLog(self.directory) if storage_profile == "compact" else None
        self.requests: list[RequestEvent] = []
        self.tool_calls = 0
        self.observations = 0
        if record_chat:
            self.directory.mkdir(parents=True)
            names = (("agent.compact.jsonl", "query.compact.jsonl") if self.compact else
                     ("agent.jsonl", "agent.log", "query.jsonl", "query.log"))
            for name in names:
                (self.directory / name).touch()

    def encode(self, value: object) -> object:
        if isinstance(value, bytes):
            digest = hashlib.sha256(value).hexdigest()
            suffix = (".png" if value.startswith(b"\x89PNG") else
                      ".jpg" if value.startswith(b"\xff\xd8") else
                      ".webp" if value.startswith(b"RIFF") and value[8:12] == b"WEBP" else ".bin")
            path = self.directory / "images" / (digest + suffix)
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                path.write_bytes(value)
            return "{image: " + path.relative_to(self.directory).as_posix() + "}"
        if is_dataclass(value) and not isinstance(value, type):
            return self.encode(asdict(value))
        if isinstance(value, dict):
            return {key: self.encode(child) for key, child in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.encode(child) for child in value]
        return value

    @staticmethod
    def render_message(message: dict) -> str:
        content = message.get("content")
        if isinstance(content, list):
            text = "\n\n".join(
                str(block.get("text", block.get("data", ""))) for block in content
            )
        else:
            text = content or ""
        if message.get("tool_call_id"):
            text = f"Tool call ID: {message['tool_call_id']}\n{text}"
        for call in message.get("tool_calls", []):
            text += "\n\nTool call:\n" + json.dumps(call, ensure_ascii=False, indent=2)
        return f"--- [{message.get('role', 'assistant').upper()}] ---\n{text}\n"

    def write(self, name: str, kind: str, data: dict[str, object]) -> None:
        if not self.record_chat:
            return
        row = {
            "event": kind, "at_ns": time.monotonic_ns(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **{key: self.encode(value) for key, value in data.items()},
        }
        if self.compact is not None:
            self.compact.write(name, row)
            return
        with (self.directory / f"{name}.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        text = f"--- [{kind.upper()}] {row['timestamp']} at_ns={row['at_ns']} ---\n"
        rendered = {"event", "timestamp", "at_ns"}
        for key, expected in (("message", dict), ("messages", list), ("response", dict)):
            if isinstance(row.get(key), expected):
                rendered.add(key)
        details = {key: value for key, value in row.items() if key not in rendered}
        if details:
            text += json.dumps(details, ensure_ascii=False, indent=2) + "\n"
        message = row.get("message")
        if isinstance(message, dict):
            text += self.render_message(message)
        messages = row.get("messages")
        if isinstance(messages, list):
            text += "\n".join(self.render_message(message) for message in messages)
        response = row.get("response")
        if isinstance(response, dict):
            text += self.render_message(response)
            text += json.dumps({key: value for key, value in response.items()
                                if key not in ("content", "tool_calls")}, ensure_ascii=False, indent=2) + "\n"
        with (self.directory / f"{name}.log").open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")

    def event(self, kind: str, **data: object) -> None:
        self.write("agent", kind, data)

    def query(self, kind: str, data: dict[str, object]) -> None:
        self.write("query", kind, data)

    def message(self, message: Message) -> None:
        self.event("message", message=message)

    def request(self, event: RequestEvent) -> None:
        self.requests.append(event)

    def native_request(self, row: dict) -> None:
        if self.compact is None:
            raise ValueError("Native request redirection requires compact evidence")
        self.compact.write("native", row)

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
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for row in episodes:
        groups.setdefault((row["agent_id"], row["game"], row["task_id"], row["task_type"]), []).append(row)
    summaries = []
    for (agent_id, game, task, mode), rows in groups.items():
        valid = [row for row in rows if row["status"] == "completed" and row.get("measurement") == "valid"]
        successes = sum(row.get("task_outcome") == "success" for row in valid)
        summaries.append({
            "agent_id": agent_id, "game": game, "task_id": task, "task_type": mode, "scheduled": len(rows),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "valid_completed": len(valid), "successes": successes,
            "success_rate_valid_completed": successes / len(valid) if valid else None,
        })
    return {"groups": summaries, "episodes": episodes}
