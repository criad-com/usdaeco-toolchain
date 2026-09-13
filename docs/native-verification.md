# Native verification

Version 0.3.0, integrated with main v0.2.3 through a merge commit. Main's S09/S10
rules, declared ownership support, regression fixtures and released family
inventory are retained. All four version declarations select 0.3.0.

Source checks use Python 3.13.12, usd-core 26.8 and Pillow 12.3.0, without
setuptools or an installed kit. The existing native CMake builds use AppleClang
16.0.0, pinned usd-dev 0.26.11-dev-g47154dc and Python 3.14.6. Their sources are
unchanged; ctests and relocated runtime probes were repeated after integration.

| Check | Result |
|---|---|
| Full check.py gate | **60 checks, 0 failed, 4 not run**: 56 PASS, four unavailable Nix native rows |
| Pytest, invoked by the full gate | **241 passed**, 77.44 seconds |
| Generated template / toolchain structure | **26/26 each** |
| Committed template structure | **26/26**, with current core v0.9.1 resources |
| Namespace, ownership and applicability smoke | **74 passed** |
| Reporting and native failure-handling smoke | **21 passed** |
| Term sweep | **0 findings**, S25 PASS; existing registry allowlist only |
| Codeful template, existing out-of-tree CMake install | Shared library, resources, generated headers, exported CMake package and Python module present |
| Schema build-tree ctest | **1/1 passed**; schema type, default value, authored value and Python import |
| Native Tf build-tree ctest | **1/1 passed**; descriptor discovers and loads the type |
| Installed C++ consumer ctest | **1/1 passed**; exported target, public header and schema value |
| Installed runtime gates after relocation to paths with spaces | **4/4 passed**; installed layouts, discovery, Python authoring, native Tf type loading |
| Plugin-free example | Record composes as a Scope through fallbackPrimTypes |
| One nix flake check --no-build attempt | **PASS**, all five aarch64-darwin check derivations evaluate; exit 0 |
| Native Nix builds / full flake builds | **NOT PROVEN**, uncached prerequisites and no available offline builder |

## Reproduce the gates

Use the existing USD-enabled Python environment. Set USDAECO_CORE_DIR to the
pinned core v0.9.2 checkout and CORE_PLUGIN_DIR to its built
plugins/usdAeco/resources directory. Set PYTHONDONTWRITEBYTECODE=1 when using
read-only dependencies. The shipped template targets core v0.9.2;
compiler checks with substituted dependencies are not a runtime compatibility
claim. The direct template lint above used current core v0.9.1 separately.

The verification environment puts usdrecord/usdchecker wrappers for the pinned
usd-dev on PATH. They select that build's site-packages; system launchers lack
required flags, and the source-check virtual environment has no launchers.
No package installation or dependency rebuild is required for source checks.

For the offline gate leave AECO_NATIVE_SCHEMA, AECO_NATIVE_PLUGIN,
AECO_NATIVE_PYTHON and AECO_USD_PYTHON unset. AECO_HUB_CHECKOUT selects the hub
revision in dependencies.json; AECO_CORE_CHECKOUT selects pinned core v0.9.2.
OPENUSD_OVERRIDE is the Git URL from the hub's local registry, prefixed with
`git+`. Use [the registry override instructions](native.md#local-input-overrides)
without committing deployment addresses or local lockfiles.

```sh
export AECO_NIX_ARGS="--offline --no-write-lock-file --max-jobs 0 --option substituters '' --option builders '' --override-input aeco-toolchain 'path:$AECO_HUB_CHECKOUT' --override-input aeco-toolchain/openusd '$OPENUSD_OVERRIDE?ref=dev&rev=47154dc7b5e28df623745495a7a508b69535ba24' --override-input core 'path:$AECO_CORE_CHECKOUT'"
env -u PYTHONPATH "$PYTHON" check.py
```

Nix cannot start prerequisite builds under this offline configuration. It
reports `required system or feature not available`, followed by dependency
failures for the templates. All four native rows report NOT RUN with that cause.
Recognized fetch failures and unavailable store paths also report NOT RUN;
compilation defects, malformed output and failed runtime probes still fail.
The summary counts NOT RUN separately, so exit 0 does not imply native builds ran.

The single evaluation attempt used the same overrides:

```sh
nix flake check --no-build --offline --no-write-lock-file --max-jobs 0 \
  --option substituters '' --option builders '' \
  --override-input aeco-toolchain "path:$AECO_HUB_CHECKOUT" \
  --override-input aeco-toolchain/openusd "$OPENUSD_OVERRIDE?ref=dev&rev=47154dc7b5e28df623745495a7a508b69535ba24" \
  --override-input core "path:$AECO_CORE_CHECKOUT"
```

For CMake-built outputs, set the four AECO_NATIVE variables as described in
[native.md](native.md#build-and-verify). The installed C++ consumer ctest also
needs PXR_PLUGINPATH_NAME set to the schema install prefix's lib directory.
The runtime probes create their own plugin set; they passed after copying both
install prefixes into a temporary directory with spaces.

## Deviations

Main was merged into the published branch to preserve its history and permit a
normal push. No force-push or main-branch update was used.

Full Nix reproduction remains unproven. Evaluation succeeded, but the native
build probe stopped before compilation because prerequisites were uncached and
builders/substitution were disabled for offline verification. Existing CMake
smoke results do not establish successful Nix derivations. The companion hub's
OCCT/IfcGeom acceptance and transitive static-archive check remain unproven.
Linux is declared but was not evaluated or run by this native-system check.

The native template remains a separate scaffold from the codeless schema
starter; S07/S12 are unchanged. Runtime probes use pinned core v0.9.2.
The retained inventory reports four incompatible core
requirements; it does not establish a compatible release train.
