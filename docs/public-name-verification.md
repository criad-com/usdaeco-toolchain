# Public repository name verification

Version 0.3.8 names the public GitHub org `criad-com`. S05 retains exact URL
and pin matching, with one owner constant shared by the family index and
publication report. S25 and the publication sweep exempt only the exact org
slug; the bare company term, adjacent terms and custom patterns remain checked.

All 21 registry entries use the public owner and matching Git destinations.
Deployment overrides remain external, following the [README](../README.md#build-and-check).
Starter toolchain refs advance to v0.3.8. Core v0.9.3, data centre v0.4.6,
the frozen core v0.8.4 test fixture and the upstream build revision stay pinned.
The example manifest changes only its toolchain pin. No result file or image
was changed or republished. The family index retains its train and source cards.

## Acceptance

| Check | Measured result |
|---|---|
| Full check.py, including the native prerequisite attempt | 69 checks, 0 failed, 4 not run: 65 PASS |
| Full pytest suite within that gate | 469 passed in 260.68 seconds |
| Final focused public-name and hostname regressions | 25 passed in 2.52 seconds |
| Generated template / toolchain structure | 29/29 each |
| Family index freshness | 21 rows, committed source cards |
| Publication sweep | 0 findings |
| Registry entries | 21 public owner/Git URL pairs |
| Tracked old-org references | 0 |
| Changed result files / republished results | 0 / 0 |
| Core UsdValidation preflight | 8/8 imported and loaded |
| Consumer structures before their own rewrites | 84 PASS, 3 FAIL: S05 only |
| Nix flake check | One invocation; transitive input resolution failed |

The full gate ran once. Final review then hardened the org exception to preserve
hostname syntax, so private suffixes and single-label URLs still fail. The
25-test focused run verifies that change and includes three regressions added
after full-suite collection. Structure, publication and documentation checks
were repeated on the final tree; the full gate was not repeated.

## Consumer checks

The available consumer checkouts have not yet changed their public names.
Each full structure lint fails S05 only. All eight core validators were
explicitly imported and loaded through UsdValidation before the comparison;
a missing import or validator would fail the probe. Consumer checkouts were
read without builds, edits or checkouts, and their Git status stayed unchanged.

| Consumer | Revision | Structure result |
|---|---|---|
| Core v0.9.3 | 169db75dd57d080171de23fff3006d3bf590910e | 28 PASS, 1 FAIL: S05 |
| Axis v0.1.3 | 6700d456435cc6bf5a3a3f26ff7c102e9a17f0e5 | 28 PASS, 1 FAIL: S05 |
| CCTV v0.5.4 | b80bdbf84b64ad58ee05a4916dea43477546e4f1 | 28 PASS, 1 FAIL: S05 |

These are 87 measured rule results: 84 PASS and three expected S05 failures.
Consumer lint after each repository's own rewrite remains not proven.

## Reproduction

Use the Python environment and frozen core resources described in the README.
Tests import `tools/` through conftest and require no installed package or
setuptools. Set PYTHONDONTWRITEBYTECODE=1 for read-only dependencies.

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_structure.py tests/test_publish.py \
  -k 'public_org or public_owner or registry_maps or custom_term or public_url or report_is_deterministic or host_and_path'
```

For consumer checks use the current core's built resources, make that checkout
importable with `env -u PYTHONPATH PYTHONPATH="$CORE_CHECKOUT"`, explicitly
import usdAecoValidators, and require all eight keyword entries to load.
The [fixture verification](fixture-pin-verification.md#reproduction) describes
the shared lint comparison procedure.

## Deviations

- The single Nix flake check stopped during resolution of the pinned upstream
  toolchain's transitive OpenUSD source. It used an exact local upstream export,
  the frozen core override, offline mode, no builders or substituters, and
  blocked outbound IP networking. The unavailable input was not repinned.
  Native builds/runtime and Nix reproduction remain not proven.
- Consumer rewrites are not available yet. Their S05 failures are retained;
  checks after their own rewrites remain a release follow-up.
- The existing family inventory fixture still has one unreleased seed and
  four incompatible requirements. Its informational PASS row does not prove
  a compatible train; the fixture was not changed.
- The publisher previously had no public URL column. This version adds that
  column and the JSON public_url field with the intended repository location;
  it does not verify availability or perform a public push.
- The starter's v0.3.8 toolchain tag awaits merge and release. Its example
  retains source mode `minimal`; no data-centre result was republished.
