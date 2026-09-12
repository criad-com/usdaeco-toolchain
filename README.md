# usdaeco-toolchain — the shared schema, validation and example kit

## Use case

Generate one familiar OpenUSD repository shape, check its contract, and reproduce
its example. The kit provides schema builds, plugin sets, structure lint,
validator adapters, rendering, example comparison and release-train validation.
The [repository conventions](docs/repo-conventions.md) define all 29 stable rules.

## The schema on an index card

| Tool | Contract |
|---|---|
| new-library | Generate any of six repository kinds from name, kind and tier |
| build.sh / build_schema.py | Codeless schema generation; flat committed source, separate install layout |
| usdaeco-pluginset | Dependency closure, supported versions, duplicates and cycle checks |
| usdaeco-check structure | S01–S29, including usdGenSchema validation and real plugin discovery |
| usdaeco_check.validation | Native UsdValidation registration, legacy adapters and registry execution |
| usdaeco-render | Embree stills, numbered frames, contact sheets and optional GIFs |
| usdaeco_check.example | Compose, derive, compare findings, render and record provenance |
| usdaeco-check family | Release-train schema and available sibling manifest comparison |
| usdaeco-family-readme | Generate and fresh-check the family index from an explicit train and tagged source cards |
| usdaeco-publish | Tagged orphan tree, licence/file inventory and publication sweep; report mode by default |
| usdaeco-check publication | Full candidate sweep including tracked published data and decoded USD crates |

The kit carries no schema of its own. Its [template](template/README.md) carries
one Imageable API with a driver and a derived value, plus two Python validators.
Use core identity and classification; keep geometry in USD geometry namespaces.

## The example

Use an existing Python 3.11+ environment with OpenUSD 26.8+, numpy, jinja2 and
packaging. Development checks also need pytest. usdrecord must provide Embree;
usdchecker is optional for the extra CLI discovery check. Pillow enables GIFs
and is required for publication image-metadata checks and their tests.

```sh
export PYTHON=python3
export TOOLCHAIN_DIR="$PWD"
env -u PYTHONPATH "$PYTHON" tools/new_library.py --kind usecase --name Example ../usdaeco-example
cd ../usdaeco-example
export CORE_PLUGIN_DIR="../usdaeco-core/out/plugins/usdAeco/resources"
env -u PYTHONPATH ./build.sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" examples/datacentre/run.py
```

The generated repository targets core v0.9.2. Its minimal example runs without
the published data-centre stage; the manifest records that as `minimal`.
Set AECO_DATACENTRE_ROOT to use the pinned release, or AECO_DATACENTRE_STAGE for
an explicit compatibility probe. The [example contract](docs/examples.md)
explains outputs and publishing. Expected findings are never overwritten.

Open the [committed starter result](template/examples/datacentre/result/README.md)
immediately with `usdview template/examples/datacentre/result/example.usdc`.
It includes the derived value and cameras, opens without family plugins or sibling
checkouts, and carries its own diffable layers plus a stock USD render in
`result/vanilla.png`. Results are capped at 10 MB total
and 2 MB per USDA layer. `--publish` updates them; the example gate rejects stale
committed results using canonical Sdf USDA serialization for the crate.

![Starter example](template/usdAecoExample/userDoc/usdAecoExampleExample.png)

## Build and check

For the toolchain tests, select a core v0.9.2 checkout with its existing
built resources. The fixture checks both source and plugin versions:

```sh
export PYTHON=python3
export PYTHONDONTWRITEBYTECODE=1
export USDAECO_CORE_DIR="$(cd ../usdaeco-core && pwd)"
export CORE_PLUGIN_DIR="$USDAECO_CORE_DIR/out/plugins/usdAeco/resources"
env -u PYTHONPATH "$PYTHON" check.py --without-native
env -u PYTHONPATH "$PYTHON" -m pytest -q
nix flake check
```

The checker prints `N checks, M failed, K not run`. `--without-native` runs
all source and core tests without attempting native Nix builds. Omit it to
include the four native build/runtime rows. Unavailable native prerequisites
produce NOT RUN rows with a cause; actual build and runtime defects fail.
The gate checks all 29 structure rules on this repository and a freshly
generated starter. Tests import tools/ through conftest.py; no installed kit
or setuptools is needed. Core validator tests explicitly import the selected
checkout and load all eight rules; missing imports or validators fail.

`dependencies.json.repos` records the sole direct build input, `aeco-toolchain`,
at published tag v0.4.0 plus its checked revision. `fixtures.core` records
published core v0.9.2 and its checked revision. Its `flakeInput: true` declares
a separate test input for S04/S05; fixture pins cannot satisfy a library's
requirements. The starter pins core v0.9.2, data centre v0.4.6 and toolchain
v0.3.8 as direct inputs. No core v0.8 schema/layout fixture is needed.

Install the kit into a suitable environment with
`env -u PYTHONPATH "$PYTHON" -m pip install -e .`, or invoke the source scripts.
The installed package provides `new-library`, `usdaeco-check`,
`usdaeco-pluginset`, `usdaeco-render`, `usdaeco-publish` and
`usdaeco-family-readme`. With tools/ on sys.path,
`python -m usdaeco_check structure <repo>` is equivalent to the console command.

The builder writes generatedSchema.usda and plugInfo.json beside schema.usda
when no output directory is supplied. `--install-root out/install` emits
plugins/<lib>/resources/ and python/<lib>Validators/. The old positional resource
output and older schemas/<lib>/ source layout remain supported. Repeat --dep
for dependencies; repository roots, flat modules and install roots are accepted.
`--generate-only` compiles for inspection without claiming version compatibility.

Nix sources use public `github:criad-com/<repo>?ref=v<semver>` inputs. S05
rejects family commit-hash pins, including test-only inputs. Use tags published
on the public copy; orphan release commits differ from source commits.
Non-family upstream inputs such as nixpkgs and OpenUSD may keep hashes.
All exact refs are recorded in dependencies.json under repos or fixtures;
template requirements are ranges
in library.json.

The committed [registry template](nix/registry.json) contains public URLs.
Copy it outside the checkout to `$HOME/.config/usdaeco/registry.json`, then
replace its destination URLs with your local Git service URLs. Keep local
addresses out of repository files. To select your private mapping:

```sh
export AECO_REGISTRY="$HOME/.config/usdaeco/registry.json"
export NIX_CONFIG="flake-registry = $AECO_REGISTRY"
nix flake check --no-write-lock-file
```

Registry rewriting of direct inputs depends on the Nix version; explicit
`--override-input` is the dependable route. Derive an override without copying
deployment addresses into documentation or lockfiles:

```sh
export CORE_OVERRIDE="$(env -u PYTHONPATH "$PYTHON" -c 'import json, os; d=json.load(open(os.environ["AECO_REGISTRY"])); print("git+"+next(e["to"]["url"] for e in d["flakes"] if e["from"]["repo"]=="usdaeco-core"))')"
nix flake check --no-write-lock-file --override-input core "$CORE_OVERRIDE?ref=v0.9.2"
```

In a generated repository use its core pin (v0.9.2). Repeat --override-input for
other direct/transitive inputs if necessary. A Git override uses `?ref=<tag>`
for a release tag, including processing-toolchain v0.4.0; upstream commit
overrides use `?rev=<full-revision>`. The toolchain follows the processing
toolchain's nixpkgs/Python ABI. Consumer core inputs follow the same toolchain
and nixpkgs. Local lockfiles remain uncommitted. The current Nix result is in
[tag pin verification](docs/tag-pin-verification.md); earlier native results
are in [native verification](docs/native-verification.md).

### Native plugins

`lib.buildCodefulSchema` generates C++ and Python, then builds and installs a
shared schema plugin. `lib.buildNativePlugin` builds shared Tf and other native
plugins. Both use the out-of-tree CMake scaffold and the two-level lib/resources
layout. Plugin sets accept native installs alongside codeless resources.
See [native plugins](docs/native.md) and the [templates](template-native/README.md)
for build, ctest, installed Python and local Nix override commands.

## Family

Start with the generated [family index](docs/family/README.md) and the five
paragraphs in [CONTRIBUTING](CONTRIBUTING.md). The index records the selected
train's actual versions, purposes, examples, licences and source status; it
does not promote untagged work to a release. [Publication commands](docs/publishing.md)
explain source freshness checks, report preparation and the existing board export.
Nothing is pushed without an explicit `--push` and destination after approval.

The [family manifest schema](docs/family-schema.md) and
[released-set fixture](tests/fixtures/family.json) distinguish supported ranges
from exact releases. Older checkouts without root library.json are explicitly
reported as unavailable for comparison. See the
[family board](https://github.com/criad-com/usdaeco-board).

Sibling comparison is opt-in via AECO_FAMILY_SIBLINGS or `family --siblings`;
the checkout's parent is never inferred. Use `family --inventory` for the
released-set fixture: one entry is an unreleased documentation seed, and sync
plus the three integrations still exclude core v0.9. Strict train validation
continues to fail on that drift. The historical fixture records core v0.9.1
and toolchain v0.2.2; the earlier inventory verification used core v0.9.2
and toolchain v0.3.2.
Explicit comparison therefore fails with `usdaeco-core: version differs from tag`.
The normal gate validates the unchanged inventory without sibling comparison;
it reports 16 repositories, 7 libraries, one unreleased seed and four incompatible
requirements. This fixture does not establish a current compatible release train.

Dependency pins and family manifests accept `usdSolid`, `usdSolidOcct`,
`hdOcct`, `aeco-toolchain` and `OpenUSD`, alongside family names and existing
lowercase slugs. S04 still checks exact refs and declared ranges. See the
[name conventions](docs/repo-conventions.md#consumers-notes).

Register core before schema parsing: it defines the aecoDerived property
metadatum. Register all schema plugins before the process-global schema registry
is constructed. Every example must still compose without family plugins.
Derived opinions belong in their own layers; editors author drivers only.

## Layout

| Path | Contents |
|---|---|
| template/ | Complete generated starter, including committed schema, image and manifest |
| tools/ | Builder, generator, plugin sets and Python check/render packages |
| tests/ | Unit and integration checks; one seeded fixture per structure rule |
| docs/ | [Conventions](docs/repo-conventions.md), [validation](docs/validation.md), [rendering](docs/rendering.md), [examples](docs/examples.md), [family schema](docs/family-schema.md) |
| nix/registry.json | Public template for an external, private input mapping |

## Status

Version 0.3.10 selects published build-toolchain v0.4.0 and core fixture
v0.9.2, with S05 enforcing matching release tags for every family flake input.
Build and runtime tests use the clean-core layout and the starter's unchanged
`>=0.9,<1.0` range. The source gate passes **65 checks, 0 failed**, with
**497 tests passed** and **29/29 structure rules** on both the kit and generated
starter. Both replacement tags resolve publicly without credentials. The
single offline Nix build evaluated 0.3.10 but was interrupted after planning
898 prerequisite derivations; package completion and native runtime remain
unproven. See [tag pin verification](docs/tag-pin-verification.md) for evidence
and the four explicitly excluded native gate rows.

Earlier evidence remains in [public-name verification](docs/public-name-verification.md),
[fixture pin verification](docs/fixture-pin-verification.md) and
[relocation verification](docs/relocation-verification.md).

The v0.3.4 publication verification recorded **20 newer tagged repositories**:
**1,725 files**,
**68,824,721 bytes** across separate trees, zero sweep findings and no public
pushes. The older selected train retains **13 PASS, 2 FAIL and 5 NOT RUN**;
its private metadata entry is excluded. The family README fresh-check passes
against that explicit train. See [publication verification](docs/publication-verification.md)
for every tag, licence, source hash and remaining limitation.

The earlier v0.3.8 Nix flake check stopped resolving the upstream OpenUSD source
with outbound networking blocked; its four native rows were NOT RUN.
Earlier dependency and licence checks are recorded in
[dependency verification](docs/dependency-verification.md).

The committed starter result totals **78,991 bytes**, including its stock USD
render proof. See [example publication](docs/examples.md) for the file contract,
normalization, caps and named failures. Earlier evidence remains in
[result verification](docs/result-verification.md) and
[native verification](docs/native-verification.md).

The full gate includes the Pillow-enabled GIF path and guide-purpose regression.
Pixel hashes
record actual renders; cross-platform identical Embree pixels are not promised.
The Python UsdValidation API is supported directly; no shim is used. Source
usdchecker invocations must run from the repository root so its Python plugin
can be imported. The supported Python run helper adds registered source module
parents to sys.path automatically.

## Licence

[MIT](LICENSE).

Runtime dependencies retain their own licences. The family runtime inventory
below includes optional integrations; each repository declares the subset it uses.

| Dependency | Licence | Use |
|---|---|---|
| OpenUSD | Apache-2.0-style | USD runtime |
| numpy | BSD-3-Clause | Numeric arrays |
| jinja2 | BSD-3-Clause | Templates |
| PyYAML | MIT | YAML inputs |
| pydantic | MIT | Data validation |
| Pillow | HPND | Images |
| embreex | Apache-2.0 | Ray tracing |
| IfcOpenShell | LGPL-3.0 | Imported only |
| OCCT | LGPL-2.1 | Dynamic linking only |

The generated starter carries its own [MIT licence](template/LICENSE).
