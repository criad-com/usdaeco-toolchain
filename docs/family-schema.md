# Family manifest schema

A train is a compatible set of released repositories. The gate owns family.json;
the board consumes it. The [fixture](../tests/fixtures/family.json) records the
current release inventory and one unreleased documentation seed. During
migration it is not a compatible train: sync, ifc, bonsai and revit still
require core below v0.9. Their actual ranges remain recorded. This checkout
prepares v0.3.5; the historical inventory still records toolchain v0.2.2.
It is a regression fixture, not a description of today's sibling releases.
An explicit sibling comparison fails on version drift; name compatibility
does not waive that check.

| Field | Type | Constraint |
|---|---|---|
| train | string | Nonempty identifier using letters, digits, dots, underscores or hyphens |
| repos | array | Nonempty; repository names and non-null libraries unique |
| repos[].name | string | Same vocabulary as S04: lowercase slugs (including usdaeco-*), usdAeco / usdAeco<X>, or usdSolid, usdSolidOcct, hdOcct, aeco-toolchain, OpenUSD; case-sensitive |
| repos[].kind | enum | library, usecase, integration, data, gate, board, meta (docs-only inventory entry) |
| repos[].library | string or null | Registered library identifier; null for schema-free repositories |
| repos[].tag | string or null | Exact vX.Y.Z release, optional prerelease suffix; null marks an unreleased seed |
| repos[].requires | object | Schema library or repository names to supported version ranges; targets must occur in the inventory; cycles fail. Train validation additionally requires released targets satisfying every range. |
| repos[].example | object or null | {datacentre: exact release tag, variant: lowercase-name}; must match the train's data-centre tag |
| repos[].enclave | string or null | Relative artifact path for work outside the Nix environment |

All seven repository fields are required; use null for absent example/enclave.
Repository names share S04's check and diagnostic, with the offending array
entry identified. The allowlist changes names only: kinds, release tags,
library identifiers (including usdSolid), ranges and cycle checks retain
their existing contracts. Full OpenUSD revisions belong in dependencies.json;
family.json still requires a release tag or a null unreleased seed.
The fixture's null examples make no claim about the older repositories' shared
example contract. Requirements copy the released manifest, including schema-free dependencies
such as the data-centre requirement on usdaeco-revit. Dependency pins in each repository describe build inputs.

```sh
env -u PYTHONPATH usdaeco-check family family.json --siblings ../
env -u PYTHONPATH usdaeco-check family tests/fixtures/family.json --inventory
```

`python -m usdaeco_check family` exposes the same command. Sibling comparison is
opt-in: pass --siblings or set AECO_FAMILY_SIBLINGS. Without either, the command
validates only the document, regardless of checkout location. Every available root
library.json is compared for name, version and requirements; kind is compared
when present. Seeds have no released version to compare. Older releases without that file are explicitly counted as
unavailable; absent checkouts are counted separately. Those comparisons are
not proven. The command never changes sibling checkouts or their pins.

Python: `validate_family(file_or_object, sibling_root=..., inventory=False)`
returns a Result. An omitted sibling_root performs document-only validation.
The default requires a compatible release train. Explicit --inventory (Python:
inventory=True) admits unreleased seeds and reports released range conflicts,
with names and a compatibility-not-proven label; malformed fields, missing
dependencies, cycles and mismatched sibling manifests still fail. The toolchain
gate and released-inventory test use this mode and the explicit sibling root.
