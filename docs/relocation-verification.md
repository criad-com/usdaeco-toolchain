# Portable example source verification

Version 0.3.6 introduces S29. The source gate uses the existing frozen core
v0.8.4 compatibility resources, the USD-enabled Python interpreter and source
imports through tests/conftest.py. Consumer gates use exact tag exports of
core v0.9.2, axis v0.1.2, build-up v0.2.1 (wall), IFC v0.2.0 and data centre
v0.4.5. No dependency checkout was changed or built.

| Acceptance | Verified result |
|---|---|
| check.py --without-native | 65 checks, 0 failed |
| Pytest, including compatibility tests | 442 passed |
| New source-path smoke selection | 51 passed |
| Structure, generated template and toolchain | 29/29 each |
| Wall v0.2.3, original and relocated layouts | 87 checks, 0 failed in each |
| Pipe v0.2.3, original and relocated layouts | 82 checks, 0 failed in each |
| Wall / pipe pytest | 24 / 20 passed |
| Consumer S29 | 2 wall / 9 pipe asset paths; PASS in each layout |
| Consumer core UsdValidation preflight | 8/8 rules loaded; absence is fatal |
| Fresh versus committed result | PASS in both layouts for both consumers |
| Archived review-layer composition | 12,354 wall / 12,356 pipe prims; no family plugins; zero errors |
| Committed consumer crates and PNGs | Byte-identical to v0.2.2 |
| Nix flake check | One attempt; public source resolution failed before builds |

The named S29 defective fixture seeds a source sublayer that escapes above the
example. Further cases cover sublayers, references, payloads and sampled asset
values; absolute paths, parent escapes, undeclared schemes and documented
resolver tokens. The relocation test creates two differently nested consumers
and source releases, opens both archived layers, and compares their bytes.
Real input directories are protected from replacement. Comments and string
values resembling asset tokens are preserved. Every published source asset is
rebased relative to the final result location; symlink targets never enter the
manifest. See the [example contract](examples.md) for the API and path spelling.

## Consumer relocation proof

Both consumer snapshots started without transient out/ files or inputs/source
links. The second layout placed consumers below consumers/deep/ and independently
copied dependency releases below dependencies/releases/. Gates supplied explicit
AECO_*_ROOT and *_PLUGIN_DIR values, plus an importable core checkout. Each runner
created its own source link. Both complete gates passed, including S27/S28 and
the ResultStale comparison. Original and relocated wall gates took 30.218 and
29.990 seconds; pipe took 40.799 and 40.905 seconds on this runtime.

Wall's review layers change one source-reference line and two package producer
version fields. Pipe's review layers change only one source-reference line.
Both manifests update the toolchain pin and affected layer hashes/byte totals;
source hashes, findings and geometry are unchanged. Original images were
retained after verifying fresh renders, since Embree pixel bytes can vary.

## Other examples surveyed

The [read-only survey](source-path-survey.json) covered 19 committed result trees
in 14 repositories.
Only wall v0.2.2 and pipe v0.2.2 carried the checkout-location defect addressed
here. Two additional unresolved archive references were found and left unchanged:

| Repository | Archived reference | Finding |
|---|---|---|
| CCTV v0.5.3 | result/layers/out/source.usda → source-data/dc.usda | Source excluded from the archive; route through inputs/source in a later release |
| Bonsai v0.1.3 | result/layers/out/source/dc.usda → dc.geometry.usdc | Archive contains dc.geometry.usda; source path does not resolve |

The other 15 trees pass the path check: six core v0.9.3 examples, axis v0.1.3,
build-up v0.2.2, IFC v0.2.1, Revit v0.1.3, clash v0.2.1, solid v0.1.2,
plan v0.1.1, compliance v0.1.1 and typical v0.1.1. References to the archived
standalone crate, used by plan, are legitimate links among own results.
This is a source-path survey, not complete validation of those repositories.

## Reproduction

Select the frozen core compatibility resources as described in
[example verification](example-verification.md#reproduction), leave data-centre
overrides unset for the starter, and use an available stock usdrecord wrapper:

```sh
export PYTHONDONTWRITEBYTECODE=1
env -u PYTHONPATH "$PYTHON" check.py --without-native
```

For the consumers, export each proposed commit into another directory using
`git archive`, copy the pinned data-centre source beneath a different directory,
and set AECO_DATACENTRE_ROOT accordingly. Set the other dependency roots and
plugin directories to their exact exports, and run:

```sh
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$PYTHON" check.py
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" "$PYTHON" -m pytest -q
```

## Deviations

- S29 extends 28 existing rules, yielding 29/0 rather than the requested
  “28/0 including S29”. The generated-library gate consequently grows to 36.
- Wall's patch version also updates two producer metadata fields; these are
  disclosed in addition to the source-reference and manifest changes.
- The single offline, no-substituter Nix attempt could not resolve the pinned
  public aeco-toolchain revision (HTTP 404). Wall and pipe each made one attempt
  and failed resolving public axis v0.1.2. No attempt was repeated. Native
  builds/runtime and Linux execution are not proven; the measured toolchain
  gate explicitly used --without-native and did not invoke a second Nix build.
- The toolchain v0.3.6 source is tested before a release tag exists. Merge and
  tag the toolchain before resolving the consumers' v0.3.6 flake pins.
- Two early consumer publication attempts hit stock renderer exit 104. Direct
  isolated probes and later sequential publication/gates passed. The transient
  failure's cause was not established; it is not claimed to be fixed here.
