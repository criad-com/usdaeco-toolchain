# Example result verification

Version 0.3.1, using Python 3.13.12, usd-core 26.8 and Pillow 12.3.0. Tests
import tools directly without an installed package or setuptools. Compatibility
tests use frozen core v0.8.4; the committed template's direct structure check
uses current core v0.9.1 resources. Dependencies were not built or modified.

| Acceptance | Measured result |
|---|---|
| Full check.py, including S28 | 65 checks, 0 failed, 4 not run; 61 PASS |
| Pytest inside that gate | 266 passed in 229.00 seconds |
| Generated template / toolchain structure | 28/28 each |
| Committed template with core v0.9.1 | 28/28 |
| Full tracked-file term sweep | 175 files, zero findings, including normalized crate text and new commit messages; no registry exception |
| Published starter source | Module examples/minimal.usda; source mode minimal |
| Plugin-free result | 4 prims, zero composition errors after relocation |
| result/example.usdc | 1,393 bytes |
| result/layers/inputs/cameras.usda | 354 bytes |
| result/layers/out/derived.usda | 67 bytes |
| result/README.md | 587 bytes |
| result/vanilla.png | 76,590 bytes; 1280 x 800; non-uniform stock Embree render |
| Complete result directory | 78,991 / 10,000,000 bytes |
| Largest authored USDA layer | 354 / 2,000,000 bytes |
| Committed regular render | 1280 x 800, 76,457 bytes, non-uniform |
| Repeat publish | Identical authored USDA bytes and canonical Sdf USDA crate text |
| Defect tests | Size caps, stale crate/layer/inventory, corrupt crate, missing or wrongly typed fallbacks/defaultPrim, wrong units/count, external references/assets and sensitive result text rejected |
| S28 negative tests | Missing/blank PNG and removed geometry rejected; supplied family plugin/PYTHONPATH environment cannot contaminate the stock-render worker |
| Integration starter | Renamed binary semantics and both S27/S28 checks pass in examples/roundtrip/ |
| One nix flake check attempt | Five aarch64-darwin check derivations evaluated; build exited 1 on an uncached prerequisite with no offline builder |

The comparison is `sdf-usda-v1`: `Sdf.Layer.OpenAsAnonymous` followed by
UTF-8 `ExportToString()`, without stripping opinions. Crate hashes and sizes
still describe actual committed bytes. The full gate regenerates and compares
the committed template result directly, then independently re-renders the
committed crate with stock USD. Each PNG's inventory and content are checked;
Embree pixel hashes are not compared between renders.

S27 requires token arrays and actual stock fallback resolution on flattened
specs; its declarations also cover types inside instance prototypes. The
reference/payload test removes the original sources before opening the result
and verifies preservation of purpose, proxyPrim and displayColor.

To reproduce, set PYTHON to the USD-enabled interpreter, USDAECO_CORE_DIR to the
frozen compatibility checkout, CORE_PLUGIN_DIR to its built resource directory,
and PYTHONDONTWRITEBYTECODE=1 for read-only dependencies. Follow the offline
native override recipe in [native verification](native-verification.md), with
private overrides supplied externally. Run:

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q
```

## Deviations

The single Nix attempt used offline local/mirror overrides, disabled substitution
and no builders. Inputs resolved and five native-system checks evaluated, but
an uncached prerequisite could not build (`required system or feature not
available`). The attempt preceded the added S28 requirement and was not
repeated. The final full gate includes S28 and reports four native rows NOT RUN
because prerequisites remain unavailable. Nix builds and Linux execution are
not proven; no native source was changed.

`Usd.Stage.Flatten` plus `Sdf.Layer.Export` is used because
`UsdUtils.FlattenLayerStack` preserves references and payloads. The result is
the selected composed view, with the example's own editable layers archived
separately. External texture/assets are rejected rather than packaged.

The starter proves the minimal source contract, not composition of a pinned
data-centre release. Integration hooks must finish re-import/convergence before
returning the final composed stage. Consumer publication belongs to subsequent
releases; no consumer checkout was modified or republished.

The existing committed registry contained deployment URLs. It now contains
public URLs; private overrides live outside the checkout, as documented in
the README. S25 no longer exempts a repository file from address checks.
