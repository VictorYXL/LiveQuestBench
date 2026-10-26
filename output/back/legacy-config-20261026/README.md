# Archived runnable configuration catalog

**Archived:** 2026-10-26, at the user's request.

The entire repository `config/` directory was moved intact into this archive.
The original root-level directory is intentionally absent. No replacement
tasks or experiment configurations have been created.

| Game | Goal-level tasks | ST YAMLs | VM YAMLs | Experiment files | Fixture files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Minecraft | 31 | 31 | 31 | 24 | 228 |
| Veloren | 30 | 30 | 30 | 24 | 3 |
| Total | 61 | 61 | 61 | 48 | 231 |

All **401 original tracked files** were verified by SHA-256 before and after the
move. [manifest.json](manifest.json) records the source revision, paths, sizes
and hashes. Paths in the manifest are relative to this archive.

The preserved directory tree is:

```text
config/
  minecraft/
    experiments/
    fixtures/
    tasks/
      structured_tools/
      visual_motor/
  veloren/
    experiments/
    fixtures/
    tasks/
      structured_tools/
      visual_motor/
```

Task-relative fixture paths retain their original relationship. Code, runtime
installations and historical run results were not removed. This is a
configuration archive, not a self-contained runtime distribution.

Examples or checks expecting a root-level `config/` now reference retired
configurations; they are not silently redirected to this archive. To deliberately
restore the old layout, first ensure `config/` does not exist, then run from the
repository root:

```bash
cp -a output/back/legacy-config-20261026/config ./config
```

The separate seventy-candidate design is a draft, not these sixty-one executable
legacy objectives. Further task design will start from six substantive focused
anchors: former L2 as a minimum content reference, usually former L3, and an
uncalibrated intended completion range of 5-30 minutes. No new five-tier scheme
or demonstrated model/Agent separation is implied.
