# Tag pin verification

Version 0.3.10 uses published family tags in the toolchain flake: build input
`aeco-toolchain` v0.4.0 and test-only core v0.9.2. The starter also selects
core v0.9.2. S05 rejects family hash refs for direct and declared fixture
inputs, even when the URL and dependency pin agree. Non-family upstream
hash refs remain accepted. Both replacement tags were independently resolved
using `git ls-remote --exit-code --tags` against their public GitHub URLs,
with credential helpers and user/system Git configuration disabled. The
offline lint itself checks syntax and agreement without network access.

| Input | Tag | Checked source revision |
|---|---|---|
| aeco-toolchain | v0.4.0 | 71c86d54aa1e4be180a301a089d9a40e727758cb |
| usdaeco-core fixture | v0.9.2 | 11000b2ca7a2f560bfcd1ffd439bf9b71a5f5c18 |

These revisions identify the source checkouts used for checks. Public orphan
trees have different commits; the flake URLs therefore use the tags.
The public build-toolchain tag resolves to afbea7ce2b012e55af54047311fad37339eb56df;
the core tag peels to 75282989be3fdecfa778465cb57a7f9530ce506e. These are
recorded separately as `publicRevision` in dependencies.json.

The upstream comparison from e190680d to v0.4.0 changes 13 files, with
449 insertions and 84 deletions. The `usd-dev` output and nixpkgs revision
afb4584a80bbf779ce0f691509ff902d188c2b3d are unchanged. The OpenUSD input
now names the public upstream repository at the same revision
47154dc7b5e28df623745495a7a508b69535ba24. The upstream lint check also
switches from one test module to unittest discovery. These changes preserve
the package and nixpkgs/Python interface consumed by this repository; they
do not establish that a fresh public build succeeds.

| Acceptance | Measured result |
|---|---|
| Public replacement tags | 2/2 resolve without credentials |
| check.py --without-native | 65 checks, 0 failed, 0 not run |
| Pytest within the source gate | 497 passed in 263.61 seconds |
| Generated starter / toolchain structure | 29/29 each, including S05 |
| S05 and fixture URL smoke | 29 passed |
| Clean-core build, plugin-set and validator smoke | 12 passed |
| Core validator registry | 8 loaded; duplicate identity detected |
| Starter build and check against core v0.9.2 | 36 checks, 0 failed |
| Committed starter result | Findings and result match; 4 plugin-free prims, 1 nonblank render |
| Publication sweep | 207 files, 0 findings |
| git diff --check | PASS |
| Offline Nix default-package build | One invocation; evaluated 0.3.10, planned 898 derivations; interrupted, exit 1 |

The old compatibility rewrite and probes of core's old source layout and
axis API are retired. Their current build, installed-resource, metadata,
plugin-set and range-rejection coverage runs against clean core. No core
v0.8 schema tree is retained. Small historical version strings in inventory
and rejection tests remain data and require no flake input.

## Reproduction

Follow the [README](../README.md#build-and-check) with a built v0.9.2 core
checkout. Set PYTHONDONTWRITEBYTECODE=1 for read-only dependencies. Tests
import tools/ directly and require no installed kit or setuptools. The core
registry probe adds the selected core checkout to PYTHONPATH, explicitly
imports usdAecoValidators, and fails if any of its eight validators is absent.
The measured source environment used Python 3.13.12, usd-core 26.8 and
Pillow 12.3.0. The gate invokes the complete pytest suite once; it was not
repeated separately. Final documentation and pin-evidence edits were checked
with structure lint, documentation links and the publication sweep.

For the offline package build, set AECO_HUB_CHECKOUT to an exact local
export of v0.4.0 and AECO_CORE_SOURCE to an export of v0.9.2. OPENUSD_SOURCE
selects a local export of the exact upstream revision above. Keep deployment
overrides and lockfiles outside the repository:

```sh
nix build .#default --offline --no-write-lock-file --no-link \
  --max-jobs 1 --option substituters '' --option builders '' \
  --override-input aeco-toolchain "path:$AECO_HUB_CHECKOUT" \
  --override-input core "path:$AECO_CORE_SOURCE" \
  --override-input aeco-toolchain/openusd "path:$OPENUSD_SOURCE"
```

## Consumers

Every family repository must re-pin the toolchain to v0.3.10 and select
tag-only family inputs. The release reviewer schedules those changes after
publication. No other repository is changed here. The starter retains its
already published toolchain v0.3.8 pin pending that scheduling.

## Deviations

- The source gate uses `--without-native` to avoid additional Nix build
  invocations. The four native build/runtime rows and Linux remain unproven.
- The single Nix invocation resolved exact local source exports and cached
  upstream inputs, and evaluated the 0.3.10 package. It planned 898 derivations
  including the compiler bootstrap; the run was deliberately interrupted
  after prerequisite work began, with exit 1. Package completion and public
  fetch/build reproduction remain unproven. No second Nix invocation or flake
  check was made, and no lockfile was written.
