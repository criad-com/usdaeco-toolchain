# usdAecoExample — a minimal semantic aspect

## Use case

A positive driver decorates an existing element. A companion tool derives its
result in a separate layer. Replace this example with your contract; start in
[the use-case document](docs/usecase.md).

## The schema on an index card

| Schema | Applicability | Drivers | Derived |
|---|---|---|---|
| AecoExampleAPI | Imageable | aeco:example:driver (metres) | aeco:example:derived (metres) |

Ownership defaults to the library suffix for namespaces and `AecoExample` for
class prefixes. If this library temporarily owns another API family, declare
the complete lists in library.json, including its original names. For example,
a wall library retaining an opening API declares:

```json
"namespaces": ["wall", "opening"],
"classPrefixes": ["AecoWall", "AecoOpening"]
```

Both optional arrays must contain nonempty strings. S08 checks class prefixes
case-sensitively; S09 compares namespace prefixes case-insensitively and reports
unused declared namespaces as warnings in a passing row. Undeclared extras
fail. These declarations do not change registered type names or Info.aeco.
The `_comment` in library.json is explanatory text only.

## The example

The [example](examples/datacentre/README.md) composes overlays over the pinned
demo-datacentre-01 release. Until that stage is available it uses the
[minimal stage](usdAecoExample/examples/minimal.usda).

```sh
env -u PYTHONPATH python examples/datacentre/run.py
```

Open the committed result immediately with
`usdview examples/datacentre/result/example.usdc`; no family plugins or sibling
checkouts are needed. Fresh outputs include `out/derived.usda`, `out/findings.json`,
`out/result/`, `out/renders/` and `out/manifest.json`. Add `--publish` to update the
committed result, renders and manifest. Checks fail if the committed result is stale.

![Example](usdAecoExample/userDoc/usdAecoExampleExample.png)

## Build and check

Use Python with OpenUSD and the shared toolchain installed, or set TOOLCHAIN_DIR
to its checkout. Set CORE_PLUGIN_DIR to the built core resource directory.

```sh
export PYTHON=python3
env -u PYTHONPATH ./build.sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m unittest discover -s testenv -p 'test*.py'
nix flake check
```

The check ends with `N checks, M failed`. A missing or incompatible dependency
fails. `build.sh --generate-only` compiles schema files for inspection without
claiming runtime compatibility. See the shared toolchain README for local Nix
input overrides.

## Family

Core support: `>=0.9,<1.0`. Exact target releases live in dependencies.json and
flake.nix. See [family conventions](https://github.com/criad-com/usdaeco-toolchain/blob/main/docs/repo-conventions.md)
and the [family board](https://github.com/criad-com/usdaeco-board).

## Layout

The schema and generated resource plugin live in usdAecoExample/. The sibling
usdAecoExampleValidators/ Python plugin registers two rules. Companion tools,
pxr-style tests, profiles, documentation and the example complete the kit.

## Status

Version 0.1.0 starter. Run the checks to obtain local counts. The placeholder
image renders the minimal stage. Published data-centre integration requires the
pinned release; fallback runs are recorded as `minimal`, never `pinned`.

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
