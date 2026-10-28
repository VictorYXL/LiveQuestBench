"""Persist preparation receipts without delaying live encounter readiness."""

import hashlib
import json
from pathlib import Path


AUTHORING_FIELDS = ("construction", "blocks")


def write_fixture_record(output: Path, initialized: dict, world: dict, digest: str | None = None) -> None:
    record = {key: value for key, value in initialized.items() if key not in AUTHORING_FIELDS}
    record["world"] = world
    record["authoring_detail"] = {
        "path": "fixture-authoring.json",
        "fields": list(AUTHORING_FIELDS),
        "phase": "written" if digest is not None else "deferred_until_native_cleanup",
        "sha256": digest,
    }
    (output / "fixture.json").write_text(json.dumps(record, indent=2) + "\n")


def write_authoring_detail(output: Path, initialized: dict) -> str:
    path = output / "fixture-authoring.json"
    with path.open("x") as stream:
        stream.write(json.dumps(
            {key: initialized[key] for key in AUTHORING_FIELDS}, separators=(",", ":"),
        ))
        stream.write("\n")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
