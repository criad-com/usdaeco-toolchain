# Dependency and licence verification

Version 0.3.3 uses Python 3.13.12, usd-core 26.8 and Pillow 12.3.0. Tests
import tools/ from source through conftest.py; no installation or setuptools
is required. The changes are limited to S01 README wording, S04 dependency
names and the corresponding family-manifest name check.

| Acceptance | Measured result |
|---|---|
| Full check.py gate | 65 checks, 0 failed, 4 not run; 61 PASS |
| Pytest within the gate | 345 passed in 242.62 seconds |
| Focused licence, family, repository-name and pin checks | 94 passed |
| Generated template / toolchain structure | 28/28 each |
| Use-case fixture with kit/upstream pins | 28/28 without adapters |
| Integration fixture with kit/upstream pins | 28/28 without adapters |
| Core v0.9.2 | 28/28, every row identical to the v0.3.2 baseline |
| Axis v0.1.1 | 28/28, every row identical to the v0.3.2 baseline |
| CCTV v0.5.2 | 28/28, every row identical to the v0.3.2 baseline |
| Core UsdValidation preflight for each consumer | 8 validators explicitly imported and loaded; absence fails |
| Historical family fixture | 16 repositories, 7 libraries; inventory PASS; bytes unchanged |
| Fixture versus current siblings | Expected FAIL: usdaeco-core version differs from tag |
| Nix flake check | One attempt; input resolution failed before builds |
| Native build/runtime rows | 4 NOT RUN; cached source inputs unavailable |

S04 uses an explicit, case-sensitive allowlist: usdSolid, usdSolidOcct,
hdOcct, aeco-toolchain and OpenUSD. It also accepts usdAeco / usdAeco<X>
and retains the previously accepted lowercase slugs. Unknown mixed-case
names fail with the input key, offending name and accepted forms.
The family checker uses that same function and identifies the array entry.
Library identifiers such as usdSolid remain valid; family kinds and tag
rules are unchanged. Upstream revision pins remain in dependencies.json.

The seeded use-case and integration fixtures contain all five allowlisted
names, including a full OpenUSD revision and a usdSolid library pin. Their
flake URLs and example manifests carry the same pins. Both call the shared
check_structure directly. Separate defects still reject non-exact refs,
schema revision pins without versions, out-of-range requirements, missing
family targets and cycles.

S01 fixtures cover both licence spellings for all three licences, declared
and inferred metadata, both spellings together, and rejection of mismatched,
ambiguous and partial names. Full names in library.json remain invalid:
that field uses SPDX identifiers. The complete-terms, root-agreement and
additional-directory disclosure checks remain in force.

## Reproduction

For check.py, set PYTHON to the USD-enabled interpreter, USDAECO_CORE_DIR to
the frozen core v0.8.4 compatibility checkout and CORE_PLUGIN_DIR to its
built resources. Set PYTHONDONTWRITEBYTECODE=1 for read-only dependencies.
Use the existing usdrecord/usdchecker wrappers. Supply private Nix overrides
externally as described in [native verification](native-verification.md).
Leave AECO_FAMILY_SIBLINGS unset for the historical fixture's document gate.

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_licences.py tests/test_family.py
```

For consumer lint, use current core v0.9.2 resources and make its checkout
importable via `env -u PYTHONPATH PYTHONPATH="$CORE_CHECKOUT"`. Import this
kit's structure module before usdAecoValidators and assert the module path;
plugin imports may add another toolchain to sys.path. Register the core
resources, explicitly import usdAecoValidators and require all eight metadata
entries to load through UsdValidation before running all 28 structure rules.
Consumer checkouts are read without builds or edits.

## Deviations

The one Nix attempt used local source and cached store overrides, with
network fetching, substitution and builders disabled. The cached flake-utils
source was missing, so input resolution failed. The same prerequisites leave
four native rows NOT RUN in check.py. Nix/native builds and Linux execution
are not proven; there was no second flake-check attempt.

The historical fixture intentionally retains core v0.9.1 and toolchain
v0.2.2. Current siblings are core v0.9.2 and toolchain v0.3.2, so explicit
sibling comparison fails at core's version check. The document-only inventory
still reports one unreleased seed and four incompatible requirements. Neither
the fixture nor that expected mismatch was relaxed for name compatibility.

Legacy runtime probes remain on frozen core v0.8.4. Current consumers were
checked separately with core v0.9.2. The generated examples prove the starter
contract with representative kit pins; they do not build those native kits
or establish a pinned data-centre integration.
