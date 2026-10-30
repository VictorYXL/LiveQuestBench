"""Lossless, private content references for repeated evidence payloads."""

import hashlib
import json
from pathlib import Path
import re
from typing import Iterator


SCHEMA = "livequest.compact-log/1"
REF = "$lqb_ref"
LITERAL = "$lqb_literal"


def encoded(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")


class CompactLog:
    def __init__(self, directory: Path):
        self.directory = directory
        self.objects = directory / "objects"
        self.verified: set[str] = set()

    def _object(self, value: object) -> dict:
        data = encoded(value)
        digest = hashlib.sha256(data).hexdigest()
        if digest in self.verified:
            return {REF: digest}
        self.objects.mkdir(parents=True, exist_ok=True)
        path = self.objects / (digest + ".json")
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError(f"Content object mismatch: {digest}")
        else:
            pending = path.with_suffix(".tmp")
            with pending.open("xb") as stream:
                stream.write(data)
            pending.replace(path)
        self.verified.add(digest)
        return {REF: digest}

    def _pack(self, value: object, key: str = "") -> object:
        if isinstance(value, str) and len(value) >= 1024:
            return self._object(value)
        if isinstance(value, list):
            values = [self._pack(child) for child in value]
            return [self._object(child) for child in values] if key in {"messages", "tools"} else values
        if isinstance(value, dict):
            packed = {name: self._pack(child, name) for name, child in value.items()}
            return {LITERAL: packed} if REF in value or LITERAL in value else packed
        return value

    def write(self, name: str, row: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"schema": SCHEMA, "record": self._pack(row)}
        with (self.directory / f"{name}.compact.jsonl").open("ab") as stream:
            stream.write(encoded(payload) + b"\n")

    def _unpack(self, value: object, visiting: frozenset[str] = frozenset()) -> object:
        if isinstance(value, list):
            return [self._unpack(child, visiting) for child in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {LITERAL}:
            literal = value[LITERAL]
            if not isinstance(literal, dict):
                raise ValueError("Invalid escaped compact object")
            return {key: self._unpack(child, visiting) for key, child in literal.items()}
        if set(value) == {REF}:
            digest = value[REF]
            if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
                raise ValueError("Invalid content reference")
            if digest in visiting:
                raise ValueError("Cyclic content reference")
            data = (self.objects / (digest + ".json")).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Content object mismatch: {digest}")
            return self._unpack(json.loads(data), visiting | {digest})
        return {key: self._unpack(child, visiting) for key, child in value.items()}

    def read(self, path: Path) -> Iterator[dict]:
        with path.open("rb") as stream:
            for line in stream:
                if not line.endswith(b"\n"):
                    raise ValueError(f"Incomplete compact record: {path}")
                row = json.loads(line)
                if row.get("schema") != SCHEMA or set(row) != {"schema", "record"}:
                    raise ValueError("Unsupported compact log schema")
                result = self._unpack(row["record"])
                if not isinstance(result, dict):
                    raise ValueError("Compact record must be an object")
                yield result


def read_records(path: Path) -> Iterator[dict]:
    if path.name.endswith(".compact.jsonl"):
        yield from CompactLog(path.parent).read(path)
    else:
        with path.open() as stream:
            for line in stream:
                yield json.loads(line)
