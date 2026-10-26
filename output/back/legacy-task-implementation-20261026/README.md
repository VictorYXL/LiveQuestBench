# Archived legacy fixture and evaluator implementations

The sections below describe the original archival snapshot. For the subsequent
MC-S publication, shared Minecraft scorers and Veloren fixture/endpoint helpers
were selectively restored, and active task configuration was reintroduced.
The published archive includes the 18 tracked Python sources and their manifest,
not historical cache files. Retired task-specific implementations and their
dependent tests remain unavailable until selectively restored; this publication
does not claim that the legacy test suite passes.

The user requested that all old fixture/evaluator implementations be backed up
under `output/` and removed from active source, for selective restoration later.
This archive preserves their original repository-relative paths.

| Original source root | Tracked Python files |
| --- | ---: |
| `game/minecraft/fixtures/` | 5 |
| `game/minecraft/evaluators/` | 7 |
| `game/veloren/fixture.py` | 1 |
| `game/veloren/evaluators/` | 5 |
| Total | 18 |

The directories were moved intact, including 21 existing Python cache files.
All 39 files (477,505 bytes) were verified against their pre-move SHA-256 hashes.
`manifest.json` records the source revision, original paths, sizes, hashes and
tracked-source inventory. Cache files are historical byproducts, not required
restoration inputs.

## Availability and scope

The four original source roots are intentionally absent. Remaining bindings,
runtime helpers and tests still reference the archived modules. In particular,
Veloren's `fixture.py` also provided shared initialization helpers. Legacy game
imports, task initialization, scoring and dependent test collection may fail
until their required components are restored or replaced. This is an archival
pause, not a runnable replacement or a completed dependency refactor.

No fallback, automatic import from this archive, or replacement evaluator was
introduced. General runtime/binding code, external game installations, prior
results and the twelve design-only difficulty anchors were not removed. No game,
model or task evaluation was started.

The previously published configuration and scene archive remains unchanged at
`../legacy-config-20261026/config/`. Root `config/` remains absent.

## Restoration

Select the useful source files and their dependencies, then copy them from this
archive back to the matching repository-relative paths. Check destination files
first; do not overwrite newer implementations. The manifest can verify original
content before restoration. Do not restore Python cache files.

This is not a standalone runnable package: imports refer to the remaining
repository, game runtimes and former configuration assets. Restoring one scorer
alone does not necessarily restore its fixture, native evidence or binding
dependencies. Qualify restored components against the new task requirements
before admitting them to evaluation.

This archive is currently local under the ignored `output/` tree; no commit or
push was requested for this cleanup. A future publication must explicitly include
the archived source, this document and the manifest, not only the live deletions.
