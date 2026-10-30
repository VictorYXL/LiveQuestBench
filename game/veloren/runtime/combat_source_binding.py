"""Reconcile a retained baseline manifest with an explicitly pinned patch chain."""

from hashlib import file_digest, sha256
import json
from pathlib import Path
import subprocess


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def relative_path(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe source path: {name}")
    return path


def verify_composed_source(
    baseline: Path, actual: Path, baseline_hashes: dict[str, str],
    patches: list[tuple[Path, str]], output: Path,
) -> dict:
    """Reconstruct only patched files; verify every declared and extra source file."""
    baseline, actual, output = baseline.resolve(), actual.resolve(), output.resolve()
    if any(output == root or root in output.parents for root in (baseline, actual)):
        raise ValueError("Reconstruction must not write into either source tree")
    for name, expected in baseline_hashes.items():
        if digest(baseline / relative_path(name)) != expected:
            raise ValueError(f"Baseline source mismatch: {name}")
    touched = set()
    for patch, expected in patches:
        if digest(patch) != expected:
            raise ValueError(f"Patch digest mismatch: {patch.name}")
        for line in patch.read_text().splitlines():
            if line.startswith(("--- ", "+++ ")):
                name = line[4:].split("\t")[0]
                if name == "/dev/null":
                    raise ValueError("This bounded verifier supports modifications, not add/delete patches")
                if not name.startswith(("a/", "b/")):
                    raise ValueError("Patch source paths must have a/ or b/ prefixes")
                path = relative_path(name[2:])
                if path.as_posix() not in baseline_hashes:
                    raise ValueError(f"Unmanifested patch target: {path}")
                touched.add(path)
    output.mkdir(parents=True, exist_ok=False)
    for name in sorted(touched):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((baseline / name).read_bytes())
    logs = []
    for patch, _ in patches:
        result = subprocess.run(
            ["patch", "--batch", "--forward", "--fuzz=0", "--no-backup-if-mismatch",
             "-p1", "-i", str(patch.resolve())],
            cwd=output, text=True, capture_output=True, check=False,
        )
        logs.append(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError(f"Patch reconstruction failed: {patch.name}\n{logs[-1]}")
    expected_hashes = dict(baseline_hashes)
    for name in touched:
        expected_hashes[name.as_posix()] = digest(output / name)
    actual_paths = {path.relative_to(actual).as_posix()
                    for path in actual.rglob("*") if path.is_file()}
    mismatches = sorted(actual_paths ^ expected_hashes.keys())
    mismatches += [name for name in sorted(actual_paths & expected_hashes.keys())
                   if digest(actual / name) != expected_hashes[name]]
    if mismatches:
        raise ValueError(f"Unexplained composed-source mismatch: {mismatches}")
    return {
        "schema": "native-composed-source-verification/1",
        "source_files_verified": len(expected_hashes),
        "patched_files": sorted(path.as_posix() for path in touched),
        "composed_source_tree_sha256": sha256(
            json.dumps(expected_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "patched_file_sha256": {name.as_posix(): expected_hashes[name.as_posix()]
                                for name in sorted(touched)},
        "patch_logs": logs,
        "scope": "Source reconstruction only; not a new binary build, runtime test or learning result",
    }
