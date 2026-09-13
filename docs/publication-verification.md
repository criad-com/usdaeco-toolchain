# Publication verification

Version 0.3.4. Source checks use Python 3.13.12, usd-core 26.8 and Pillow 12.3.0,
with tools imported directly from source and no package installation.

| Acceptance | Measured result |
|---|---|
| Full toolchain gate | 67 checks, 0 failed, 4 not run; 63 PASS |
| Pytest in the full gate | 370 passed in 275.82 seconds |
| Final focused publication and index regressions | 28 passed; includes three tests added after full-suite collection |
| Toolchain / generated-template structure | 28 checks, 0 failed each |
| Current core UsdValidation preflight | 8 validators explicitly imported and loaded; absence fails |
| Family README freshness | PASS, 21 rows against the selected train and source cards |
| Newer tagged family releases, report mode | 20/20 clean orphan repositories, 1 commit each; 0 public pushes |
| File inventory | 1,725 files; 68,824,721 bytes across 20 separate trees |
| Per-repository size limits | All files at most 10,000,000 bytes; every tree at most 50,000,000 bytes |
| Image metadata follow-up | 102 images inspected, 0 findings |
| Root licences at newer tags | 16 MIT, 4 Apache-2.0; source licence bytes unchanged |
| Selected aeco-0.4.0 train | 13 PASS, 2 FAIL, 5 NOT RUN, 1 private entry excluded |
| Board public export | Already shipped in v0.1.2; implementation unchanged; export not rerun |
| Nix flake check | One attempt; source resolution failed before builds |

## Tagged report set

Each row was prepared from a fresh clone at the exact tag below. The publisher
then made its own temporary tagged clone and created a separate orphan tree.
The latest available tags were checked separately because the selected train
still names older releases. This table does not claim a compatible release train.

| Repository | Tag | Files | Bytes | Root licence | Report |
|---|---|---:|---:|---|---|
| usdaeco-core | v0.9.2 | 149 | 2,799,718 | MIT | PASS |
| usdaeco-axis | v0.1.1 | 43 | 166,281 | Apache-2.0 | PASS |
| usdaeco-toolchain | v0.3.3 | 184 | 635,416 | MIT | PASS |
| usdaeco-buildup | v0.2.1 | 67 | 285,527 | MIT | PASS |
| usdaeco-wall | v0.2.1 | 64 | 2,892,396 | MIT | PASS |
| usdaeco-pipe | v0.2.1 | 70 | 6,073,877 | MIT | PASS |
| usdaeco-cctv | v0.5.2 | 138 | 10,166,722 | MIT | PASS |
| usdaeco-cctv-exec | v0.2.0 | 28 | 128,870 | Apache-2.0 | PASS |
| usdaeco-sync | v0.5.1 | 65 | 433,150 | Apache-2.0 | PASS |
| usdaeco-ifc | v0.2.0 | 106 | 7,011,559 | MIT | PASS |
| usdaeco-bonsai | v0.1.2 | 75 | 877,816 | MIT | PASS |
| usdaeco-revit | v0.1.2 | 71 | 534,073 | MIT | PASS |
| usdaeco-datacentre | v0.4.5 | 203 | 12,034,456 | MIT | PASS |
| usdaeco-scenarios | v0.4.0 | 84 | 1,362,424 | Apache-2.0 | PASS |
| usdaeco-board | v0.1.2 | 34 | 180,030 | MIT | PASS |
| usdaeco-plan | v0.1.0 | 101 | 7,137,738 | MIT | PASS |
| usdaeco-compliance | v0.1.0 | 61 | 4,095,037 | MIT | PASS |
| usdaeco-repeat | v0.1.0 | 60 | 1,024,546 | MIT | PASS |
| usdaeco-clash | v0.2.0 | 68 | 3,411,026 | MIT | PASS |
| usdaeco-solid | v0.1.0 | 54 | 7,574,059 | MIT | PASS |

Source commits, orphan commits, inventory hashes, licence hashes and the selected
train findings are in [the machine-readable record](publication-results.json).
The file inventory hash is SHA-256 of the report files array serialized as JSON
with sorted keys and compact separators. Source files, including every licence,
are copied byte for byte; executable bits and safe internal symlinks are retained.

## Reproduction

Follow [the publication commands](publishing.md) for each table row. Store the
fresh clones together, use their exact tags, and choose a new report output
directory each time. The script defaults to report mode. Full file inventories
and licence tables are written beside each prepared tree, outside its Git history.

For the toolchain gate, use the frozen core v0.8.4 compatibility resources as
described in [dependency verification](dependency-verification.md#reproduction).
Use current core v0.9.2 separately for the explicit eight-validator preflight.
The full suite collected 370 tests; three later CLI/image/archive regressions
were covered by the final 28-test focused run. The added metadata pass inspected
all 102 images in the 20 prepared trees without changing their bytes.

```sh
env -u PYTHONPATH "$PYTHON" check.py --family "$FAMILY_JSON" --family-repos "$RELEASE_SOURCES"
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_publish.py tests/test_family_readme.py
env -u PYTHONPATH "$PYTHON" tools/check_publication.py .
```

## Deviations

The selected train remains aeco-0.4.0. Its toolchain v0.2.3 has 21 private-reference
findings in nix/registry.json and a missing additional-licence disclosure.
Its scenarios v0.3.7 lacks library.json. Five use-case tags are null. These rows
retain FAIL or NOT RUN, and the private metadata entry is excluded. Refreshing
the train belongs to its owner; the family generator accepts the new path without
changing its contract. The source cards identify untagged checkout versions
explicitly, and the missing legacy manifest is visible in the index.

The selected newer axis v0.1.1, cctv-exec v0.2.0, sync v0.5.1 and scenarios
v0.4.0 roots still contain Apache-2.0 terms. The remaining 16 roots are MIT.
No licence was rewritten. The Bonsai Blender-side licence is retained and
listed separately; dependency exceptions are described in CONTRIBUTING.

The one Nix check used offline mode and local top-level overrides, but a
transitive public OpenUSD input was still requested and returned HTTP 404.
Offline mode did not prevent that source lookup. The native-build probe met the
same unresolved input; its four rows remain NOT RUN. No second flake-check
attempt was made. Nix builds, Linux execution and actual public pushes are not
proven. Only disposable local fixture remotes were used to test push behavior.

Board v0.1.2 already ships its static export. Its recorded acceptance is 22 pages,
7,778,613 bytes, 83 copied images and 24 vanilla previews, below the 50 MB cap.
That is upstream recorded evidence, not a new export run. No board files were
changed. Visible image labels remain subject to source artwork review; decoded
image metadata, text and USD crates are scanned mechanically.
