# Shared example harness

`run_example(example_dir, hook, minimal=..., variant="base", publish=False)`
implements the fixed run.py contract. The hook takes `(stage, out_dir)` and
returns a JSON findings list. It authors derived opinions in separate out/
layers and inserts those layers into the composed stage. It never edits inputs.

| Phase | Operation |
|---|---|
| Resolve | Explicit AECO_DATACENTRE_STAGE override; otherwise AECO_DATACENTRE_ROOT/dist/<variant>/dc.usda with release version checked against the pin; otherwise the starter minimal stage |
| Compose | Sorted inputs/*.usda layers above the source; root defaultPrim, units, axis, time range and fallback metadata preserved |
| Derive | Hook writes separate derived layers; registered validators add findings |
| Compare | JSON findings against expected/findings.json; order-insensitive, multiplicity retained, absolute/relative tolerance 1e-6 |
| Render | Named /Renders cameras; fixed image dimensions; non-uniform content and caps verified |
| Record | out/manifest.json includes source mode/hash, all source layer hashes/sizes, the pinned dc.manifest.json hash, pins, findings hashes, renders and result files |
| Publish | Explicit --publish refreshes committed result/, renders/ and manifest after findings match; expected findings never rewritten |

`check_example(example_dir)` runs run.py in a fresh process, compares findings,
checks every output image against the manifest, and compares the committed
result with the fresh result. It returns the family's
Result type. A missing source, mismatched pin, hook failure, changed finding,
blank image or hash mismatch fails. `execute=False` verifies existing outputs.

An example may declare `"budgetSeconds": 600` at the top level of its committed
`examples/<name>/manifest.json`. The default is **180 seconds**; a declared budget
must be a positive finite JSON number no greater than the **900-second hard cap**.
The budget covers the fresh `run.py` process, including its hook and publications.
The gate prints measured wall time against that budget and reports
`ExampleBudgetExceeded` only when the runner exceeds it; other findings, images
and result checks still apply. Invalid budgets fail before execution with
`ExampleBudgetInvalid`. The elapsed time also appears in the check result,
including on timeout. `--publish` preserves an explicit budget in both manifests;
elapsed time is diagnostic output and is never published as deterministic data.
`execute=False` does not run or time the example. The independent result probes
and vanilla re-render retain their existing limits.

A checkout includes an immediately viewable result, with no sibling checkout
or family plugin required:

```text
examples/datacentre/                 # examples/roundtrip/ for integrations
  result/example.usdc                # flattened composed view
  result/layers/inputs/*.usda         # original overlays, including cameras
  result/layers/out/**/*.usda         # authored derived, study, presentation,
                                     # intent and result layers
  result/README.md                    # what to open, own layers, source pin
  result/vanilla.png                  # stock USD render proof
  renders/ · expected/ · manifest.json
  out/                               # ignored; fresh run evidence
```

From the example directory, run `usdview result/example.usdc`. To regenerate,
run `env -u PYTHONPATH python run.py --publish` in the configured environment.
Ordinary runs write the same result under out/result/ for comparison.
The starter publishes its module's examples/minimal.usda with the derived layer
and cameras. `new-library` renames both the binary's semantics and text layers,
then updates hashes. Its template pins the toolchain at v0.3.7.

The complete result/ directory is capped at **10 MB (10,000,000 bytes)**,
including README and layers. Each `.usda` is capped at **2 MB (2,000,000 bytes)**.
The vanilla PNG is included in that total and obeys S23: at most 1600 pixels
per dimension and 400,000 bytes, with non-uniform pixels.
Failures are named `ResultSizeExceeded` and `ResultLayerSizeExceeded`.
S21 requires the tree; S22 verifies the exact file inventory, sha256 and byte
sizes. S27 copies only the crate to an empty directory and opens it using an
isolated Python interpreter with family plugin/search paths removed. It checks
zero composition errors, complete stock fallbacks for all Aeco typed prims,
defaultPrim, metres, Z-up and the manifest's `prim_count` (`TraverseAll`, excluding
instance prototypes). External assets are rejected, including textures: this
contract does not package texture dependencies. S25 scans the committed text
layers, including paths retained as result/layers/out/.

The writer uses `Usd.Stage.Flatten(addSourceFileComment=False)` followed by
`Sdf.Layer.Export` to usdc. Unlike `UsdUtils.FlattenLayerStack`, this resolves
references and payloads as well as sublayers. It bakes the selected variants;
instance sharing uses internal references. The original own layers preserve the
editable opinions. Units/axis must already be metres/Z-up; the writer never
relabels differently scaled geometry. Missing fallbacks are filled from registered
schema fallbacks or rejected when no declaration exists.
S27 requires token arrays and verifies USD actually applies the stock fallback,
including for typed prims inside instance prototypes.

Only USD files authored under inputs/ and out/ are retained, with their relative
subdirectories preserved. The transient out/example.usda composition wrapper is
excluded. Source asset paths are rebased through the example-local alias; all other
text bytes are retained. Own binary layers are serialized
to USDA. Save hook layers before returning. Pinned source layers are excluded
even if present under those directories; their hashes and sizes are recorded in
source.layers instead, along with source.manifest_sha256 for dc.manifest.json.
The archived overlays are for inspection/reuse; use example.usdc as the standalone
entry point, and recreate inputs/source before opening an archived overlay.

This contract also applies to every integration's `examples/roundtrip/`.
Its hook must finish re-import and convergence before returning: the flattened
result is that final composed stage. Preserve any intent, result and presentation
layers separately under out/ so they are archived with the example's own layers.

S28 renders the committed crate in a fresh isolated process with
`PXR_PLUGINPATH_NAME` empty and no `PYTHONPATH` or family search paths. The crate
and inputs/cameras.usda are copied to an empty directory. The view is `overview`
if declared there, otherwise the first named camera in sorted order. The shared
renderer invokes `usdrecord --disableGpu --renderer Embree --purposes proxy,render`.
The flattened stage preserves `purpose`, `proxyPrim` and `primvars:displayColor`.
Every run writes out/result/vanilla.png; publication commits result/vanilla.png.
`result.vanilla` records its sha256, dimensions and bytes in manifest.json.
Both S28 and check_example re-render the committed crate independently and
reject missing, invalid or blank images with a named failure. No family plugin
is loaded for this proof.

Determinism uses **sdf-usda-v1**: open each crate with
`Sdf.Layer.OpenAsAnonymous`, canonically rename its flattened prototypes, then
compare the UTF-8 bytes of `ExportToString()`. OpenUSD assigns
`Flattened_Prototype_N` numbers in an unstable order. The normalizer identifies
referenced prototype `over` roots, hashes each subtree with SHA-256 at a neutral
root path, and uses that hash as its canonical name. During hashing, paths to
other prototypes use stable names derived from their first expanded instance
site; nested instances and cross-prototype relationships therefore do not depend
on generated numbers. Equal subtrees remain separate, with suffixes assigned by
instance site. Only generated roots are reordered. Internal references,
relationship targets and attribute connections follow the new names; literal
strings, geometry, time samples, metadata and authored layer bytes are preserved.
The source crate is never rewritten by comparison.

No fields, timestamps or opinions are stripped. The manifest stores both the
actual crate sha256/bytes and `normalized_sha256`; each actual inventory must
match its files, while fresh-versus-committed crates use the normalized hash.
Existing manifests may retain the original v1 hash of the unrenamed Sdf export:
the checker verifies that hash against the actual crate, then recomputes canonical
hashes for both sides of the comparison. A manifest edit cannot mask a content
change. Crates without generated prototypes keep their original normalization.
Authored USDA layers and README compare byte for byte. Vanilla PNG inventories
and non-uniform content are checked, but pixels are not compared between runs:
Embree pixel hashes are not promised across runs or platforms. `ResultStale` names a
fresh-result difference; `ResultManifestMismatch` names altered/missing files
or hashes; `ResultSourceStale` names changed pins or source evidence. Updating
only a manifest cannot hide stale output. Image hashes record the render and
are not used for cross-platform result determinism.

`diff_findings(out, expected, abs_tol=1e-6, rel_tol=1e-6)` accepts JSON paths or
objects and returns a list of differences (empty means equivalent). All JSON
lists compare as unordered multisets. Booleans remain distinct from numbers;
non-finite numbers never match. Tolerance matching does not depend on list order.

The harness refreshes its own out/ directory on each run. Published manifests
carry no local paths. A `minimal` or `override` run proves the harness contract;
only a `pinned` run proves composition of the declared data-centre release.

S29 makes review-layer sources portable. A pinned run creates or retargets the
ignored `inputs/source` symlink from `AECO_DATACENTRE_ROOT` to the pinned checkout
root (which contains `dist/`). Real files or directories at that location are
refused. Neither the link nor source files are committed. From the example root,
the published stage is `./inputs/source/dist/<variant>/dc.usda`; from an authored
`out/` layer it is `../inputs/source/dist/<variant>/dc.usda`. Publication rebases
that source reference to `../../../inputs/source/dist/<variant>/dc.usda` in
`result/layers/out/`. References between archived own layers retain their relative
layout. The alias never appears in source hashes, which still describe the actual
published files. Hooks may resolve paths for reading; publication maps references
back through the alias. Every other opinion is retained.

S29 scans sublayers, references, payloads and asset-valued properties, including
time samples, without following the runtime symlink. No `..` traversal may cross
above the example directory. Other source locations, absolute filesystem paths
and undeclared resolver schemes fail with `ResultSourcePathInvalid`. A resolver
can instead be documented in the example manifest, for example:

```json
{"assetResolvers": {"release:": "The release resolver maps release identifiers to pinned published assets; configure its search path before run.py."}}
```

The runner preserves this declaration on publication. Resolver availability is
still proved by composition; S29 alone verifies the authored path contract.
A plugin-free standalone viewer continues to open `result/example.usdc` directly.
For a relocated checkout, select the same source release with
`AECO_DATACENTRE_ROOT` and run `run.py`; it refreshes the local alias automatically.
