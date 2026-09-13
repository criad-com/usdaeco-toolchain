# Changelog

## 0.3.11 — 2026-09-13

- Update repository references to usdaeco-repeat and remove private repository
  names from public inventories, source cards, fixtures and publication checks.
- Exclude private metadata entries from generated family indexes while retaining
  publication refusal based on repository kind.
- Align native verification instructions with the pinned core v0.9.2 fixture.

## 0.3.10 — 2026-09-12

- Pin the build toolchain to published v0.4.0 and the core test fixture to
  published clean-core v0.9.2, recording both checked revisions. The upstream
  usd-dev output and nixpkgs revision are unchanged; OpenUSD now uses its
  public upstream URL at the same revision.
- Extend S05 without renumbering: direct and declared fixture family inputs
  require matching release-tag refs; matching commit-hash pins fail clearly.
  Non-family upstream inputs such as nixpkgs and OpenUSD retain hash support.
- Retire the v0.8 compatibility rewrite, old source-layout/axis probes and the
  test that depended on v0.8 rejecting the current starter. Exercise current
  flat core builds, metadata registration, plugin sets and unsupported ranges
  with v0.9.2 instead; require all eight core validators and detect a seeded
  duplicate identity. No old core schema tree is retained as test data.
- Move the starter core pin and example provenance to v0.9.2 as well. Keep
  the starter toolchain on published v0.3.8 until consumer release scheduling.

## 0.3.9 — 2026-09-12

- Read the Nix Python package version from library.json in the toolchain and
  reduced starter, preventing stale derivation versions at release time.
- Extend S05 to reject literal flake versions that differ from library.json,
  with regression coverage for mismatches, matching literals and derived values.

## 0.3.8 — 2026-09-12

- public names → github.com/criad-com: update flakes, registry mappings,
  templates, documentation and generated family links. Keep S05 strict with
  one documented public-org constant shared by URL generators.
- Allow the exact public org slug in S25 and publication sweeps while keeping
  the bare company term, adjacent terms, private hostnames and custom patterns
  checked; seed regressions for both allowed and rejected forms.
- Include the intended public repository URL in publication reports and advance
  starter toolchain pins to v0.3.8; retain all other dependency pins and results.

## 0.3.7 — 2026-09-12

- Record core v0.8.4 under dependencies.json.fixtures with its compatibility-test
  reason; retain the exact upstream build pin as the sole direct dependency.
- Validate refs and reasons for fixtures marked flakeInput: true separately
  from direct requirements, and include their exact public URLs in S05.
  Unmarked historical evidence retains its existing meaning. Fixtures cannot
  satisfy requirements; consumer pin, range and example checks are unchanged.
- Advance starter pins to core v0.9.3, data centre v0.4.6 and toolchain v0.3.7,
  including flakes and example provenance. Compatibility copies read the fixture
  ref from metadata and continue to build against the frozen v0.8.4 resources.

## 0.3.6

- Add S29 for portable result-layer sources, with seeded coverage of sublayers,
  references, payloads and sampled asset values.
- Create the ignored inputs/source alias for pinned examples and rebase archived
  source references without changing other authored opinions.


## 0.3.5 — 2026-09-12

- Let example manifests declare budgetSeconds: default 180 seconds, positive
  finite values up to 900. Measure and report runner time against its budget,
  reject invalid declarations, and preserve the budget through publication.
- Canonically name flattened prototype roots by SHA-256 of their subtrees before
  comparing crates. Preserve instance sharing, nested references, path targets,
  authored values and separate equal prototypes; sort only generated roots.
- Verify legacy sdf-usda-v1 hashes against their crates while comparing both
  results with canonical names. Raw inventories and all other rules stay exact.
- Add seeded budget and prototype-order regressions, including stale geometry
  detection; advance package metadata and starter toolchain pins to v0.3.5.

## 0.3.4 — 2026-09-12

- Generate a family README from an explicit train and tagged library/use-case
  source cards, with a source freshness check and private metadata exclusion.
- Add the five-paragraph contribution guide and publication documentation.
- Add usdaeco-publish: fresh tagged clone, deterministic orphan tree, licence
  and file reports, and a hard publication sweep. Report mode is the default;
  an explicit push requires an explicit remote and uses atomic, unforced refs.
- Inspect tracked data, result layers, decoded USD crates, binary strings,
  symlinks, filenames and size limits. Preserve source licences unchanged.
- Integrate family-index freshness and publication sweep in check.py; add
  seeded publication and source-card regressions. Advance starter pins to v0.3.4.

## 0.3.3 — 2026-09-12

- Accept the declared kit/upstream repository names usdSolid, usdSolidOcct,
  hdOcct, aeco-toolchain and OpenUSD in S04, alongside family names and
  existing lowercase slugs. Invalid names identify the input and accepted forms.
- Share the same name validation with family manifests, preserving dependency
  range, cycle and sibling version checks and the historical family fixture.
- Accept SPDX identifiers and full licence names in README Licence paragraphs
  for MIT, Apache-2.0 and BSD-3-Clause; retain complete terms and agreement checks.
- Add seeded name, pin and licence wording regressions, including all 28
  structure rules on use-case and integration fixtures with kit pins and no adapters.
- Advance the starter toolchain pins to v0.3.3.

## 0.3.2 — 2026-09-11

- Accept full MIT, Apache-2.0 and BSD-3-Clause terms in S01, require agreement
  with explicit library.json licence and README, and infer omitted metadata
  for existing releases.
- Default the toolchain and all generated repository kinds to MIT; document
  runtime dependency licences and additional per-directory terms.
- Report additional licence paths as informational and require README disclosure.
  Permit public copyright attribution in the scoped S25 contexts while keeping
  private terms blocked in code and other documentation.
- Add licence regression fixtures and advance starter toolchain pins to v0.3.2.
- Treat a missing cached Nix source input as an unavailable native prerequisite;
  missing project sources and native compilation failures still fail.

## 0.3.1 — 2026-09-11

- Publish standalone result/example.usdc, authored text layers and a reading
  guide with every example; record source manifest/layer hashes without copying
  the pinned data-centre layers.
- Extend S21/S22 with complete result inventories, a 10 MB total cap and 2 MB
  USDA layer cap; add S27 for relocated, plugin-free result composition/counts.
- Add S28: commit a capped stock-USD vanilla render and re-render the committed
  crate in isolation, including final integration round-trip results. Document
  required core-validator imports and reject vacuous validation claims.
- Compare committed and regenerated results using exact USDA bytes and canonical
  Sdf USDA serialization of crates; reject stale results and scan result text.
- Ship the starter result, preserve/rename it in new-library, and pin generated
  starters to this version of the publication contract.

## 0.3.0 — 2026-09-11

- Add buildCodefulSchema and buildNativePlugin against the pinned usd-dev ABI.
- Add native schema and Tf plugin templates, the shared CMake install scaffold,
  installed runtime gates and native-aware plugin sets.
- Preserve the codeless skeleton and its 56 existing check rows.
- Include the v0.2.3 namespace/applicability lint and released family inventory.
- Report unavailable native prerequisites as NOT RUN, separately counted in the
  family summary; retain failures for build defects and invalid runtime results.

## 0.2.3

- Allow libraries to declare complete namespaces and classPrefixes ownership
  lists, retaining single-library defaults. Reject malformed declarations and
  undeclared extras; report unused namespaces as non-failing warning details.
- Document the manifest shape and starter guidance; exercise all four outcomes
  for ordinary properties and multiple-apply namespace prefixes.
- Refresh the released family inventory and preserve actual compatibility drift.
  Validate schema-free repository requirements, including cycle and range checks,
  so the data-centre dependency on the integration package can be compared.

## 0.2.2

- Match S09 namespace ownership by a case-insensitive library-suffix prefix,
  accepting camelCase and per-API namespaces for properties and multiple-apply
  propertyNamespacePrefix declarations. Preserve built-in API exemptions.
- Let S10 accept explicitly unrestricted APIs through the class customData
  marker aecoApplicability = "unrestricted" and a nonblank class doc explaining
  why. Document the declaration in the conventions and starter schema comments.
- Add regression cases for namespace boundaries, missing applicability markers,
  empty documentation and inherited declarations; record direct shared-lint
  results for core, axis and build-up.

## 0.2.1

- Accept S09 overrides supplied by composed API schemas, including inherited
  CollectionAPI instances, while rejecting unrelated properties.
- Make family sibling comparisons explicit through AECO_FAMILY_SIBLINGS or
  --siblings; refresh the release inventory with board, axis and unreleased
  integration/meta seeds. Report migration drift in explicit inventory mode
  while retaining strict compatible-train validation by default.
- Render proxy/render purposes by default and add --purposes for guide opt-in.
  Explain guide-only and empty-stage failures and retain uniform-image checks.
- Document tests without setuptools and per-variant data-centre output paths.

## 0.2.0

- Define the shared repository skeleton with stable S01–S26 rules and six kinds.
- Generate flat schema modules, committed resource plugins, Python validators,
  pxr-style tests, companion CLIs, profiles and example contracts.
- Preserve older schema/resource layouts while adding flat source dependencies
  and plugin/validator install roots.
- Check structure, version ranges, exact pins, plugin discovery, image hashes,
  vanilla composition and repository sanitization; seed every rule with a defect.
- Register native UsdValidation callbacks and adapt legacy error-list functions.
- Render named cameras and frame sequences with Embree, capped PNGs, contact
  sheets and optional Pillow GIF previews.
- Compose pinned or explicitly substituted example stages, isolate derived
  layers, compare findings with tolerance and publish measured manifests.
- Validate release trains and compare available sibling library manifests.
- Use public Nix refs with one local registry mapping and explicit overrides.

## 0.1.0

- Initial codeless schema builder, dependency plugin sets, registry probes,
  reusable check results and library starter.
