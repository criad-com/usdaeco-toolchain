# Fixture pin verification

Version 0.3.7 separates the core v0.8.4 compatibility checkout from direct
build dependencies. The test suite still uses its frozen schema/resource
layout through USDAECO_CORE_DIR and CORE_PLUGIN_DIR. The sole direct input
is aeco-toolchain at revision e190680d3f94eb76e06abe77574fda1308af2c85;
the family drift checker classifies this as an external build input.

| Acceptance | Measured result |
|---|---|
| check.py --without-native | 65 checks, 0 failed |
| Pytest within the final gate, including legacy core probes | 454 passed in 288.98 seconds |
| Focused fixture-input and historical-evidence tests | 12 passed |
| Generated template / toolchain structure | 29/29 each |
| Generated starter built and checked against core v0.9.3 | 36 checks, 0 failed |
| Family direct-pin audit, aeco-0.7.0 | One below-floor pin before; zero after; one fixture and one external build input retained |
| Core v0.9.3 | 29/29, identical to the v0.3.6 lint |
| Axis v0.1.3 | 29/29, identical to the v0.3.6 lint |
| CCTV v0.5.4 | 29/29, identical to the v0.3.6 lint |
| Wall v0.2.3 | 29/29, identical to the v0.3.6 lint |
| Pipe v0.2.3 | 29/29, identical to the v0.3.6 lint |
| Scenarios v0.7.0 | 29/29, identical to the v0.3.6 lint |
| Core UsdValidation preflight for consumer comparisons | 8/8 explicitly imported and loaded in each process; absence is fatal |
| Starter dependency, flake and example pins | core v0.9.3 / data centre v0.4.6 / toolchain v0.3.7 |
| Nix flake check | One invocation; failed resolving the local source override before evaluation |

The before/after comparison uses the source at ab9baaa990157152d4c01548751e05ec48237aa7
and this version of the kit. All 174 consumer rule results match, including
their diagnostic text. Dependencies are read without building, editing or
checking out their repositories. Consumer versions above reflect the available
merged releases at verification time.

`fixtures.core.flakeInput: true` declares the compatibility core as an exact
flake input for S04/S05. Such inputs require a nonblank reason and distinct
input names; their refs cannot satisfy library requirements or enter example
runtime pins. Unmarked historical records may contain nested evidence,
synthetic rejection cases or released schema snapshots. Those records retain
their existing meaning and do not require flake URLs. The regression tests
exercise both forms and keep rejection of missing direct dependencies,
inexact fixture refs, missing reasons and mismatched URLs.

The family audit calls the existing Scenarios drift checker on this repository
with the aeco-0.7.0 bounds. The original core v0.8.4 direct pin fails the
inclusive v0.9.2–v0.9.3 interval. The revised declaration has no direct semantic
train dependency; the audit explicitly finds its one fixture and one external
build input. This proves the toolchain's drift finding is resolved, not the
entire family's gate.

## Reproduction

Use the USD-enabled Python interpreter with pytest, jinja2, numpy and Pillow.
No package installation or setuptools is needed. Select the frozen core v0.8.4
checkout and its built resources as described in the [README](../README.md#build-and-check).
Set PYTHONDONTWRITEBYTECODE=1 for read-only dependencies. Leave data-centre
and family-sibling overrides unset for the starter and historical inventory.

```sh
env -u PYTHONPATH "$PYTHON" check.py --without-native
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_structure.py \
  -k 'fixture_pin or fixture_declarations or fixture_flake or historical_fixture'
```

For consumer comparisons, export the baseline kit using git archive to a
separate temporary directory. Run check_structure from each kit on the same
six checkouts, with the current core, axis and build-up resource directories
passed as deps. Make the core checkout importable using
`env -u PYTHONPATH PYTHONPATH="$CORE_CHECKOUT"`. Import the selected kit first
and assert its module path; register the core resources, explicitly import
usdAecoValidators, and require all eight keyword metadata entries to load via
UsdValidation before comparing every result and diagnostic.

## Deviations

- The source gate explicitly excludes four native build/runtime rows. Nix
  and native reproduction, including Linux execution, remain not proven.
  The one Nix invocation used an exact local export of the upstream revision,
  the frozen core checkout, offline mode, no builders or substituters, and
  blocked outbound IP networking. Nix rejected the source override because
  the temporary-directory prefix was a symlink. No second invocation was
  made; a future attempt should use a physically resolved override path.
- The starter's published example retains source mode `minimal`. Its updated
  manifest records the target data-centre pin; it does not claim a run against
  that release. The core v0.9.3 starter build/check is a separate minimal probe.
- The v0.3.7 starter toolchain tag awaits merge and release. Updating the family
  inventory and rerunning the complete train belong to the release process;
  neither the inventory nor other repositories were modified here.
