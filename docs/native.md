# Native plugins

The kit supports codeful schemas and shared native plugins against the
processing toolchain's pinned `usd-dev`. Python bindings must use that build's
Python ABI. The ordinary schema starter and all semantic family schemas remain
codeless; native code is an explicit option for geometry and plugin behavior.

## Builders

```nix
schema = toolchain.lib.buildCodefulSchema {
  inherit system;
  name = "usdAecoExampleNative";
  src = ./schema;
  deps = [ ];
};
hello = toolchain.lib.buildNativePlugin {
  inherit system;
  name = "usdAecoExampleHello";
  src = ./plugin;
  deps = [ ];
  cmakeFlags = [ "-DBUILD_TESTING=ON" ];
};
plugins = toolchain.lib.pluginSet { inherit system; plugins = [ schema hello ]; };
```

Each source root has CMakeLists.txt, library.json, and tests. A codeful schema
lives under `<name>/schema.usda` and declares `libraryName`, `libraryPath`,
`useLiteralIdentifier = true`, and `skipCodeGeneration = false` in GLOBAL.
The builder runs the pinned usdGenSchema with code generation, then
`--validate`, before CMake configure/build/install. It never edits the checkout.
Version, tier and requirement ranges in Info.aeco come from library.json.

`deps` supplies build dependencies; outputs made by either builder carry their
transitive plugin dependencies in `aecoDependencies`. Ordinary dependencies
such as OCCT remain build inputs and are omitted from plugin sets. CMake sources call `find_package(pxr CONFIG REQUIRED)` and
include `${AECO_NATIVE_CMAKE}/AecoNative.cmake`. The helper
`aeco_codeful_schema(NAME ... PYTHON_MODULE ... LIBRARIES ...)` builds the
generated sources and wrapper. Link additional schema targets in LIBRARIES and
resolve their exported packages in the source CMakeLists.txt. The helper
`aeco_native_plugin(NAME ... DEPENDENCIES ...)` installs an existing SHARED target, using
`plugInfo.json.in`. Requirement names are resolved in the exported CMake
package; DEPENDENCIES adds non-plugin CMake packages such as OpenCASCADE.
It rejects static plugin targets. Every source supplies at
least one ctest; no tests is a failing build.

## Install contract

```text
lib/plugInfo.json                         Includes: ["*/resources/"]
lib/lib<name>.dylib                       .so on Linux
lib/<name>/resources/plugInfo.json        Root: "..", LibraryPath: "../lib<name>.dylib"
lib/<name>/resources/generatedSchema.usda codeful schemas
lib/<name>/resources/<name>/schema.usda   compiler dependency source
lib/cmake/<name>/<name>Config.cmake       exported <name>::<name> target
include/<libraryPath>/*.h                generated public schema headers
lib/pythonX.Y/site-packages/pxr/<Module>/ Python wrapper and __init__.py
```

LibraryPath is relative to Root. Both the build tree and install tree use this
layout. Plugin sets retain each descriptor in place and compose it with relative
Includes entries, so native libraries and their resources remain together.
Schema Python installs extend the pxr package search path; put the schema's
site-packages directory before usd-dev's when using separate prefixes.

The [two templates](../template-native/README.md) use one typed record and one
Tf registration. The record inherits UsdTyped and has a Scope fallback; it is a
new tutorial referent, with no geometry or parallel identity. Its stage remains
legible without plugins. This native scaffold is a separate contract from the
S07/S12 codeless schema rules; it does not relax those rules for family schemas.

## Build and verify

```sh
nix build .#template-native-schema .#template-native-plugin
nix flake check
```

The flake builds both templates, runs ctest with PXR_PLUGINPATH_NAME at the
build tree, checks installed discovery and Python authoring, and scans the
consumer closure for static OCCT archives. The Python check.py keeps the
56 existing rows and adds four native rows. Without prebuilt outputs it runs
Nix once to build the templates and Python environment. AECO_NIX_ARGS passes
explicit Nix arguments, such as `--no-write-lock-file --override-input ...`.
`--without-native` runs only the source compatibility gate and proves no native
build. Unavailable Nix prerequisites or a missing Nix executable report all four
rows as **NOT RUN**, with the cause. Compilation defects, malformed build outputs
and failed runtime probes remain **FAIL**. A failed build leaves its dependent
runtime probes NOT RUN. Unknown Nix errors fail rather than being hidden as
unavailable prerequisites.

The summary is `N checks, M failed, K not run`; NOT RUN rows are included in N
but count as neither passes nor failures. A zero exit status means no failures;
it does not establish that every check ran. For an offline prerequisite probe,
include `--offline --max-jobs 0 --option substituters '' --option builders ''`
in AECO_NIX_ARGS along with the local input overrides. This uses existing store
outputs and refuses to start uncached source builds.

For an existing build set AECO_NATIVE_SCHEMA and AECO_NATIVE_PLUGIN to their
install prefixes, AECO_NATIVE_PYTHON to usd-dev's Python executable, and
AECO_USD_PYTHON to its site-packages directory. This runs the four native rows
without rebuilding. Those rows verify installed artifacts, discovery through a
plugin set, `from pxr import UsdAecoExampleNative` plus authored values, and
loading the native Tf type. A source compiler run is recorded separately from
a Nix build; it cannot establish flake reproducibility.

## Local input overrides

Copy the public [registry template](../nix/registry.json) outside the checkout
and configure its destinations for your local Git service. Read that private
file into separate shell variables; keep local addresses and lockfiles out of
the repository:

```sh
export PYTHON=python3
export AECO_REGISTRY="$HOME/.config/usdaeco/registry.json"
export AECO_HUB="$(env -u PYTHONPATH "$PYTHON" -c 'import json, os; d=json.load(open(os.environ["AECO_REGISTRY"])); print("git+"+next(e["to"]["url"] for e in d["flakes"] if e["from"]["repo"]=="aeco-toolchain"))')"
export AECO_CORE="$(env -u PYTHONPATH "$PYTHON" -c 'import json, os; d=json.load(open(os.environ["AECO_REGISTRY"])); print("git+"+next(e["to"]["url"] for e in d["flakes"] if e["from"]["repo"]=="usdaeco-core"))')"
export AECO_HUB_REF="$(env -u PYTHONPATH "$PYTHON" -c 'import json; print(json.load(open("dependencies.json"))["repos"]["aeco-toolchain"]["ref"])')"
nix flake check --no-write-lock-file \
  --override-input aeco-toolchain "$AECO_HUB?allRefs=1&rev=$AECO_HUB_REF" \
  --override-input core "$AECO_CORE?ref=v0.8.4"
```

The hub's registry also supplies its OpenUSD mirror override and Harmonia cache
configuration. Use the same OpenUSD revision when overriding that transitive
input. The native development shell in the hub supplies CMake, Ninja, the
compiler, usd-dev and OCCT for out-of-tree development.

OCCT 7.9.3 is LGPL-2.1 with its upstream exception. Only dynamic OCCT linking is
supported. The closure gate rejects `libTK*.a`, including transitive consumers;
other dependencies' static archives (for example OpenSubdiv CMake exports) are
unrelated to this OCCT rule.
