# Repository conventions

Version 3. Rules are reported as `Snn PASS|FAIL detail`; inapplicable rules
report `PASS not applicable (kind)`. Paths below are relative to the repository.

```text
README.md · LICENSE · CHANGELOG.md · library.json · dependencies.json
flake.nix · check.py · pyproject.toml
usdAeco<X>/
  schema.usda · generatedSchema.usda · plugInfo.json
  userDoc/overview.md · schemaUserDoc.usda · usdAeco<X>Example.png
  examples/minimal.usda
usdAeco<X>Validators/plugInfo.json · __init__.py · validatorTokens.py
tools/usdaeco_<x>/__init__.py · cli.py
testenv/testUsdAeco<X>Schema.py · testUsdAeco<X>Validators.py
conformance/profiles/<x>.json
docs/usecase.md
examples/datacentre/
  README.md · run.py · manifest.json
  inputs/cameras.usda · inputs/.keep
  expected/findings.json · renders/*.png
  result/example.usdc · result/README.md · result/vanilla.png · result/layers/**/*.usda
```

| Scope | Applies to |
|---|---|
| All | `library`, `usecase`, `integration`, `data`, `gate`, `board` |
| Schema | Any kind whose `library.json.name` begins `usdAeco`; schema-free repos use `usdaeco-<name>` |
| Story | `usecase`, `integration` |
| Example | Story; integration uses `examples/roundtrip/` instead of `examples/datacentre/` |
| Reduced | `data`, `gate`, `board`, schema-free libraries: All rules only |

| Id | Scope | Required contract |
|---|---|---|
| S01 | All | Root files exist; LICENSE contains full MIT (default), Apache-2.0 or BSD-3-Clause terms. library.json licence and the README Licence opening paragraph agree; README accepts the SPDX identifier or full name listed under Licences; absent metadata is inferred. Additional per-directory licences are informational and must be mentioned by path in README Licence. |
| S02 | All | One H1 `<name> — <one line>` and the eight H2 headings below, in order. |
| S03 | All | `library.json`: name, semantic version, kind, tier, requires object; optional namespaces and classPrefixes are nonempty arrays of nonempty strings (whitespace-only entries fail). Omitted arrays default to the library suffix and `Aeco<X>` respectively. Tiers core, section, kind, record, sector, organization, project, toolchain, data, gate, board, integration. Requirements are nonempty comma-separated bounds using `<`, `<=`, `>`, `>=`, `~=`; never `==`, `!=`, bare versions or wildcards. |
| S04 | All | `dependencies.json`: `repos` maps input names to `{repo, library, ref}`. Repository names accept lowercase slugs (including `usdaeco-*`), `usdAeco` / `usdAeco<X>`, and the exact kit/upstream allowlist below. Invalid names report the input key, offending repository name and accepted forms. Each ref is an exact `vX.Y.Z` tag or 40-hex revision (schema-library revisions also declare `version`); each requirement has exactly one direct pin and its version satisfies the range. Optional `fixtures` retains historical evidence. Entries marked `flakeInput: true` declare separate test input names with the same pin shape plus a nonblank `reason`; fixtures cannot satisfy requirements. Unmarked evidence is outside the input-pin checks. |
| S05 | All | Every direct or explicitly declared fixture flake URL uses `github:criad-com/<repo>?ref=<ref>` and matches a dependency pin; every pin has a URL; `nixpkgs.follows` present. Schema flakes expose default, pluginSet, library/structure checks, default dev shell and example/render apps. |
| S06 | Schema | Exactly one immediate schema directory, named as the library, containing schema.usda, generatedSchema.usda and plugInfo.json. Source and install layouts are distinct. |
| S07 | Schema | GLOBAL.libraryName equals the directory; skipCodeGeneration and useLiteralIdentifier true; sublayers usd/schema.usda, usdGeom/schema.usda, usdAeco/schema.usda (core omits itself). |
| S08 | Schema | All local class identifiers start with any declared classPrefixes entry (case-sensitive), defaulting to `Aeco<X>`. Undeclared extras fail. Their className still yields registered type `Usd` + libraryName without `usd` + className. Stage data uses the class identifier. |
| S09 | Schema | Locally introduced properties use `aeco:<namespace>:<property>`, where the segment after `aeco:` starts with any declared namespaces entry, defaulting to the library suffix (the name without `usdAeco`), compared case-insensitively. Thus `aeco:buildUp:x`, `aeco:cctvCamera:x` and `aeco:pipeType:x` belong to their respective libraries; undeclared extras fail. An unused declared namespace produces a warning detail in a PASS row. Core with no explicit declaration permits any `aeco:` property. Multiple-apply APIs instead set propertyNamespacePrefix to a namespace satisfying the same rule, without its trailing colon; local properties may be unprefixed. Inherited property overrides may retain their original namespace. Properties contributed by APIs in the composed apiSchemas list are also exempt, including APIs inherited from bases in the same or sublayered schema. The API definition must supply the property for that instance; applying CollectionAPI:members never exempts foreign:driver or another collection instance. |
| S10 | Schema | Every singleApply/multipleApply API declares a nonempty apiSchemaCanOnlyApplyTo array, or explicitly declares `string aecoApplicability = "unrestricted"` in the class customData and a class `doc` sentence explaining why unrestricted application is needed (for example, untyped catalog class prims). The lint checks the exact marker and a nonblank locally authored class doc; schema review checks the explanation. Missing restrictions alone do not grant an exception. |
| S11 | Schema | usdGenSchema accepts the source; `--validate` is clean for generatedSchema.usda and the generator descriptor before the documented resource/Info.aeco patch; committed generated data equals fresh generation. Missing generator/dependencies fails, never silently skips. |
| S12 | Schema | Exactly one resource plugin, library name, no binary LibraryPath; Info.aeco equals library.json version, tier, requires; generated types present. |
| S13 | Schema | userDoc overview links a minimal example; schemaUserDoc sublayers ../schema.usda and adds userDocBrief overs; example PNG exists and meets S23 caps. A generated starter uses a real minimal-stage render as its placeholder. |
| S14 | Schema | Sibling validators directory has Python plugInfo.json, __init__.py and validatorTokens.py; Validators keyword is `UsdAeco<X>Validators`; rule names are `<Rule>Checker`, with docs and prim schemaTypes where applicable. |
| S15 | Schema | Every full validator name and keyword has a literal token; error tokens are ProperCase; declared ERROR_NAMES is nonempty. |
| S16 | Schema | RegisterPlugins on the validator directory discovers and loads every declared validator through UsdValidation.ValidationRegistry, with the correct keyword and registered schema types. |
| S17 | Schema | testenv contains Schema and Validators unittest scripts with #!/pxrpythonsubst, RegisterPlugins, and one test_<ErrorName> per error token. |
| S18 | Schema | Companion package __init__.py and cli.py; pyproject exposes `aeco-<x>` pointing at usdaeco_<x>.cli:main. |
| S19 | Schema | Conformance profile is JSON with the plugin keyword and severity_overrides whose values are error, warn or info. |
| S20 | Story | docs/usecase.md has exactly the nine H2 sections below, in order. |
| S21 | Example | Example tree exists, expected findings is a JSON list, inputs include cameras.usda and run.py calls the shared run_example harness with a library hook. result/example.usdc, result/README.md, result/vanilla.png and result/layers/ exist. out/ is transient; only root /result and /result-* are Nix ignores. |
| S22 | Example | manifest.json names facility demo-datacentre-01, datacentre {ref, variant}, pins equal dependencies.json, source mode (pinned, override, minimal), findings hash and nonempty render records {path, sha256, width, height, bytes}; hashes and sizes match committed files. Datacentre ref matches its pin; source layers record hashes/bytes, and pinned sources record dc.manifest.json sha256. result lists every file with sha256/bytes (crates also normalized_sha256), total bytes, prim_count and normalization sdf-usda-v1. Inventory and hashes match; total result/ ≤10,000,000 bytes and each USDA layer ≤2,000,000 bytes. |
| S23 | Schema/Example | Every committed PNG/GIF in userDoc, renders and result is valid, non-uniform, each dimension ≤1600 and file ≤400000 bytes. Default render 1280×800. Sheets/GIFs obey the same caps. |
| S24 | Schema/Example | Minimal/example stage roots compose in a fresh process with no family plugins; every used Aeco typed prim has fallbackPrimTypes resolving to stock USD types. Input overlays are composed by the harness. |
| S25 | All | Term sweep over repository text: no private addresses, MACs, local absolute paths, private hostnames or internal terms; no repository file is address-allowlisted; private registry overrides live outside the checkout. The exact public org slug `criad-com` is allowed; the bare company term remains flagged outside the existing licence attribution contexts detailed under Licences. Other terms still fail there. Extra patterns may be supplied with --term-pattern. Committed result text layers included, even result/layers/out/. VCS, caches, transient out/build/dist, root Nix result and ignored generated artifacts excluded. Reports paths/lines, never matched text. |
| S26 | All | check.py uses Report and structure lint and the literal family summary contract `N checks, M failed`; schema checks also invoke registry_probe, can_apply, validate_examples and validator listing. |
| S27 | Example | Committed result/example.usdc opens after relocation into an empty directory in a fresh plugin-free process, with zero composition errors, no external asset dependencies, complete stock fallbackPrimTypes, defaultPrim, metres, Z-up and TraverseAll prim count matching the manifest. check_example additionally compares against a fresh run: USDA/README bytes exactly, usdc via Sdf.Layer.OpenAsAnonymous and ExportToString (sdf-usda-v1); stale results fail. |
| S28 | Example | result/vanilla.png is a non-uniform S23-capped PNG, with hash/dimensions/bytes in result.vanilla and the result file inventory. A fresh process with no family plugins or PYTHONPATH re-renders the committed crate using inputs/cameras.usda (overview, otherwise first sorted view), usdrecord --disableGpu --renderer Embree --purposes proxy,render. check_example repeats this proof; PNG bytes are not compared across renders. Integration results must be the final composed stage after re-import/convergence. |
| S29 | Example | Result layers reference sources only through the example's own inputs/ or documented assetResolvers scheme tokens in manifest.json. Paths are relative to each archived layer; no parent traversal may escape above the example. References among archived layers and to result/example.usdc are allowed. Sublayers, references, payloads and asset values (including samples) are checked without requiring source resolution. inputs/source is an ignored runtime symlink to the pinned data-centre root. |

| README H2 order | Heading |
|---|---|
| 1 | Use case |
| 2 | The schema on an index card |
| 3 | The example |
| 4 | Build and check |
| 5 | Family |
| 6 | Layout |
| 7 | Status |
| 8 | Licence |

| Use-case H2 order | Heading |
|---|---|
| 1 | 1 The problem |
| 2 | 2 The data as it arrives |
| 3 | 3 The model in USD |
| 4 | 4 Workflow |
| 5 | 5 Validation |
| 6 | 6 The example on the demo data centre |
| 7 | 7 Trade-offs and alternatives |
| 8 | 8 Out of scope and open questions |
| 9 | 9 Status |

| Example operation | Contract |
|---|---|
| Resolve | AECO_DATACENTRE_ROOT/dist/<variant>/dc.usda; temporary AECO_DATACENTRE_STAGE override; starter falls back to the module's examples/minimal.usda. Record which mode ran. |
| Compose | Sorted inputs/*.usda overlays strongest, pinned stage weakest. Cameras: named Camera children of /Renders in inputs/cameras.usda. |
| Hook | hook(stage, out_dir) returns JSON findings; writes derived opinions to separate layers in out/. Editors author drivers only. |
| Compare | out/findings.json versus expected/findings.json, unordered lists with multiplicity, numeric absolute/relative tolerance. |
| Render | usdrecord --disableGpu --renderer Embree --purposes proxy,render; default-purpose geometry is always included; opt into guides with --purposes guide,proxy,render. Ambient occlusion samples 0; renders/<view>.png or <view>.<frame>.png, <view>.sheet.png, optional <view>.gif. |
| Publish | Explicit --publish copies result/ and renders and writes the committed manifest; ordinary runs only write out/. No silent replacement of expected findings. |
| Pins | Ranges describe supported versions; dependency refs record target checks, observations record any substituted dependency separately. Flake refs select the same exact releases. |
| Install | Builder commits generated files beside schema.usda; --install-root emits plugins/<lib>/resources/ plus Python validator module; plugin sets accept both old resource dirs and new repo roots. |
| Nix | Public source refs; external private registry/--override-input mapping described in README; the committed registry template uses public URLs. Lockfiles with deployment addresses remain uncommitted. |

### Consumers' notes

S04 accepts these case-sensitive kit/upstream repository names:
`usdSolid`, `usdSolidOcct`, `hdOcct`, `aeco-toolchain`, `OpenUSD`.
The family forms are `usdaeco-*`, `usdAeco` and `usdAeco<X>` (an uppercase
initial followed by letters or digits). Existing lowercase slugs matching
`[a-z][a-z0-9-]*` remain accepted for compatibility. Other mixed-case names,
including `usdSolidExtra` and `OpenUSD-fork`, fail; a `kind` field does not
bypass the name check. The allowlist applies to each pin's `repo` value,
independently of its input key or `library`. Exact refs, library uniqueness
and declared version ranges are checked as before, including for kit pins.
S05 still requires matching public flake URLs, and example manifests must
record the same pins. No consumer adapter is needed.

Optional ownership declarations in `library.json` replace their defaults with
complete lists. A library retaining the seed of a future opening library uses:

```json
{
  "name": "usdAecoWall",
  "version": "0.2.0",
  "kind": "usecase",
  "tier": "kind",
  "requires": {"usdAeco": ">=0.9,<1.0"},
  "namespaces": ["wall", "opening"],
  "classPrefixes": ["AecoWall", "AecoOpening"]
}
```

`AecoOpeningAPI` with className `OpeningAPI` still registers as
`UsdAecoWallOpeningAPI`; its stage identifier remains `AecoOpeningAPI`.
Namespace ownership is explicit while the API lives here; a later extraction
must update the declarations. The arrays are lint metadata and do not extend
the `Info.aeco` version/tier/requires contract. The starter's `_comment` field
documents this option without adding invalid JSON comments.

Tests run from source in environments without setuptools. Do not require an
editable install or import setuptools during collection. In conftest.py, insert
the repository's tools directory into sys.path before importing its packages:

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
```

Per-variant data-centre outputs live under `out/<variant>/`; select the variant
directory when inspecting findings and renders. Published data-centre stages
remain under `dist/<variant>/`. The shared example harness always writes its transient outputs to the
selected example directory’s `out/`. See [example publication](examples.md)
for committed results and deterministic comparison.

### Licences

New family repositories use MIT; library.json declares `"licence": "MIT"`.
S01 accepts full canonical MIT, Apache-2.0 and BSD-3-Clause terms. Detection
compares the complete grant, conditions and disclaimer after normalizing
whitespace, case, quote typography and BSD bullet style. Headings, copyright
holder text and the optional Apache appendix do not determine the licence;
a title, SPDX identifier or abridged text is insufficient. BSD's
non-endorsement clause may name the copyright holder.

An explicit `licence` must be one of those three identifiers and match LICENSE.
When the key is absent, S01 infers the licence from LICENSE for compatibility
with released repositories. The opening paragraph of README `## Licence`
names that same licence using either spelling below; dependency tables cannot
satisfy this declaration. Matching is case-sensitive with word boundaries;
two spellings of the same licence agree, while naming different allowlisted
licences in the opening paragraph fails.

| SPDX identifier | Full name accepted in README |
|---|---|
| MIT | MIT License |
| Apache-2.0 | Apache License 2.0 |
| BSD-3-Clause | BSD 3-Clause |

Per-directory LICENSE or LICENCE files (also .md/.txt, case-insensitive) retain
their own terms. S01 lists their paths as INFO without applying the root
allowlist to their contents. Mention each path in README `## Licence`, for
example `blender/LICENSE` for GPL-3.0 scripts. Missing documentation fails;
the additional licence itself never does. VCS, ignored files and transient
build outputs use the same exclusions as S25. The toolchain template's
separate licence is documented in its own root README.

S25 permits the family copyright holder in the exact copyright line shipped
in LICENSE files, README `## Licence` sections, and the exact notice in
`library.json.copyright`. The same name in code docstrings or other documentation
still fails. All other private terms and caller-supplied patterns remain checked,
including inside licence sections.

The public GitHub org is `criad-com`, defined by the single
`PUBLIC_GITHUB_ORG` constant in `tools/usdaeco_check/structure.py`. S05 requires
that exact owner for every direct and declared fixture input; alternate owners
still fail. The family index and publication report use the same constant.
The registry template maps that owner to public Git URLs; deployment overrides
remain outside the checkout as described in the README.

S25 and the publication sweep explicitly allow the exact `criad-com` slug in
URLs and other text. The bare company term remains flagged outside the existing
licence attribution contexts. Prefixes, suffixes and other private terms on
the same line do not inherit the exception. Caller-supplied patterns still
inspect the original text, including the public slug.

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
