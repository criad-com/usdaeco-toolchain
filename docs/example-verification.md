# Example harness verification

Version 0.3.5. Checks use Python 3.13.12, usd-core 26.8 and Pillow 12.3.0,
importing tools/ from source without installing the package or setuptools.
The [example contract](examples.md) describes the budget and normalization rules.

| Acceptance | Measured result |
|---|---|
| Full check.py gate | 67 checks, 0 failed, 4 not run; 63 PASS |
| Pytest within the gate | 391 passed in 335.17 seconds |
| Focused budget checks | 14 passed; default, override, boundary, invalid values and timeout |
| Focused prototype checks | 5 passed, including the existing prototype fallback regression |
| Generated template / toolchain structure | 28/28 each |
| Core v0.9.2 / axis v0.1.1 / CCTV v0.5.2 structure | 28/28 each |
| Core UsdValidation preflight | 8 validators explicitly imported and loaded; absence fails |
| Committed starter example | 12.188 seconds / 180 seconds; 4 plugin-free prims; 1 non-blank render |
| Historical family inventory | 16 repositories, 7 libraries; PASS with 1 unreleased seed and 4 incompatible requirements reported |
| Fixture versus current siblings | Expected FAIL: core version differs from the fixture tag |
| Nix flake check | One attempt; pinned toolchain input resolution failed before builds |
| Native build/runtime rows | 4 NOT RUN; required inputs could not be fetched |

The budget regression supplies controlled elapsed times: 200 seconds passes with
a declared 600-second budget, 601 seconds fails, and exactly 900 seconds passes
with the maximum budget. Subprocess timeout and invalid declarations are checked
separately. The publication integration test confirms that an explicit budget
survives in both the committed and fresh manifests. Real runner time is measured
by the starter row above; the boundary tests do not wait several minutes.

The prototype regression writes two USDC files with different prototype numbers
and root order. Their unrenamed USDA exports differ; canonical bytes match.
It covers nested instances, equal subtrees, self and cross-prototype relationships,
attribute connections, time samples and literal strings resembling paths. The
normalized stage composes, the input crates remain unchanged, and geometry edits
still differ. A comparison using a verified legacy normalization hash passes for
the reordered crate and reports ResultStale after a geometry change. Altered raw
inventory hashes still fail. Structure rule source and the family fixture remain
byte-identical to the previous release.

## Reproduction

For check.py, set PYTHON to the USD-enabled interpreter, USDAECO_CORE_DIR to the
frozen core v0.8.4 compatibility checkout and CORE_PLUGIN_DIR to its built
resources. Leave AECO_FAMILY_SIBLINGS unset for the historical inventory gate.
Use the available usdrecord/usdchecker wrappers and external Nix overrides.

```sh
export PYTHONDONTWRITEBYTECODE=1
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_example.py tests/test_example_result.py
```

Consumer lints use current core resources and an importable core checkout,
explicitly loading all eight core validators before checking the read-only
consumers. Follow the [consumer preflight instructions](dependency-verification.md#reproduction).

## Deviations

The single Nix attempt used offline, no-substituter and no-builder options. Input
resolution for the pinned aeco-toolchain revision returned HTTP 404, before any
build. The same unresolved input leaves all four native rows NOT RUN; native
builds and Linux execution are not proven. No second flake-check attempt ran.

The historical family fixture pins core v0.9.1 while the sibling is v0.9.2, so
explicit sibling comparison intentionally fails. Its four incompatible core
ranges and unreleased seed remain reported; the fixture was not repinned.

The full family train and the solid example under parallel load were not rerun.
This release proves the budget contract and canonical comparison with seeded
cases, the real starter example and unchanged consumer lints.
