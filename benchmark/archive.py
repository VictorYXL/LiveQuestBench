"""Verified lossless archiving of closed-episode verbose logs, never live files."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil

from benchmark.results import write_json


NAMES = {"native.jsonl", "private-native-oracle.ndjson", "fixture-authoring.json",
         "query.jsonl", "query.log", "agent.jsonl", "agent.log", "requests.jsonl"}


def write_record(path: Path, value: dict) -> None:
    write_json(path, value)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def digest(path: Path, *, compressed: bool = False) -> str:
    value = hashlib.sha256()
    opener = gzip.open if compressed else open
    with opener(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def identity(path: Path) -> tuple[int, int, int, int]:
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def seal_episode(root: Path) -> None:
    result = root / "results/result.json"
    value = json.loads(result.read_text())
    if value["status"] not in {"completed", "error", "cancelled"} or not value.get("finished_at_ns"):
        raise ValueError("Episode has not terminated")
    if any(error["stage"] in {"end", "agent_cleanup", "game_cleanup", "client_cleanup"}
           for error in value["errors"]):
        raise ValueError("Episode cleanup was not acknowledged")
    write_record(root / "evidence-sealed.json", {
        "schema": "livequest.evidence-seal/1", "result_sha256": digest(result),
        "finished_at_ns": value["finished_at_ns"],
    })


def archive_episode(root: Path) -> dict:
    root = root.resolve()
    seal = json.loads((root / "evidence-sealed.json").read_text())
    if seal["schema"] != "livequest.evidence-seal/1" or (
        seal["result_sha256"] != digest(root / "results/result.json")
    ):
        raise ValueError("Episode seal does not match final result")
    manifest = root / "archive.json"
    if manifest.exists():
        raise FileExistsError("Archive manifest already exists; verify/restore it instead")
    files = sorted(path for path in root.rglob("*") if
                   path.name in NAMES or path.name.endswith(".compact.jsonl"))
    report = {"schema": "livequest.lossless-archive/1", "status": "writing",
              "result_sha256": seal["result_sha256"], "files": []}
    write_record(manifest, report)
    for path in files:
        if path.resolve() != path or not path.is_file():
            raise ValueError(f"Archive target is not an episode-local regular file: {path}")
        before = identity(path)
        compressed = path.with_name(path.name + ".gz")
        pending = compressed.with_name(compressed.name + ".tmp")
        if compressed.exists() or pending.exists():
            raise FileExistsError(f"Archive output already exists: {compressed}")
        original_hash = digest(path)
        with path.open("rb") as source, pending.open("xb") as destination:
            with gzip.GzipFile(filename="", mode="wb", fileobj=destination,
                               compresslevel=3, mtime=0) as stream:
                shutil.copyfileobj(source, stream, length=1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())
        if digest(pending, compressed=True) != original_hash or identity(path) != before:
            raise ValueError(f"Archive verification failed or source changed: {path}")
        pending.replace(compressed)
        report["files"].append({
            "path": path.relative_to(root).as_posix(), "sha256": original_hash,
            "bytes": before[2], "compressed_bytes": compressed.stat().st_size,
            "identity": list(before),
        })
        with compressed.open("rb") as stream:
            os.fsync(stream.fileno())
        descriptor = os.open(compressed.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        write_record(manifest, report)
    report["status"] = "verified_originals_retained"
    write_record(manifest, report)
    return report


def verify_archive(root: Path) -> dict:
    root = root.resolve()
    report = json.loads((root / "archive.json").read_text())
    if report.get("schema") != "livequest.lossless-archive/1" or report["status"] not in {
        "verified_originals_retained", "originals_retired", "retiring",
    }:
        raise ValueError("Archive is incomplete")
    for row in report["files"]:
        path = root / row["path"]
        if path.resolve() != path or not path.is_relative_to(root):
            raise ValueError("Archive path escapes episode")
        if digest(path.with_name(path.name + ".gz"), compressed=True) != row["sha256"]:
            raise ValueError(f"Corrupt archive: {path}")
    return report


def retire_originals(root: Path) -> None:
    """Explicitly retire only byte-verified sources, preserving every archive."""
    root = root.resolve()
    report = verify_archive(root)
    if report["result_sha256"] != digest(root / "results/result.json"):
        raise ValueError("Final result changed since archiving")
    for row in report["files"]:
        path = root / row["path"]
        if path.exists() and digest(path) != row["sha256"]:
            raise ValueError(f"Evidence changed since archiving: {path}")
    report["status"] = "retiring"
    write_record(root / "archive.json", report)
    for row in report["files"]:
        path = root / row["path"]
        if path.exists():
            before = identity(path)
            if digest(path) != row["sha256"] or identity(path) != before:
                raise ValueError(f"Evidence changed during retirement: {path}")
            path.unlink()
    report["status"] = "originals_retired"
    write_record(root / "archive.json", report)


def restore_episode(root: Path) -> None:
    report = verify_archive(root)
    for row in report["files"]:
        path = root / row["path"]
        if path.exists():
            if digest(path) != row["sha256"]:
                raise ValueError(f"Refusing to replace changed evidence: {path}")
            continue
        pending = path.with_name(path.name + ".restore.tmp")
        with gzip.open(path.with_name(path.name + ".gz"), "rb") as source, pending.open("xb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        if digest(pending) != row["sha256"]:
            raise ValueError(f"Restore verification failed: {path}")
        pending.replace(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "verify", "restore", "retire"))
    parser.add_argument("episode", type=Path)
    arguments = parser.parse_args()
    if arguments.operation == "create":
        print(json.dumps(archive_episode(arguments.episode), indent=2))
    elif arguments.operation == "verify":
        print(json.dumps(verify_archive(arguments.episode), indent=2))
    elif arguments.operation == "restore":
        restore_episode(arguments.episode)
    else:
        retire_originals(arguments.episode)
