# Licence verification

Version 0.3.2 uses Python 3.13.12, usd-core 26.8 and Pillow 12.3.0. Tests
import tools/ from source through conftest.py; no installed kit or setuptools
is needed. Repository licences and generated defaults are MIT.

| Check | Result |
|---|---|
| Full check.py gate | 65 checks, 0 failed, 4 not run; 61 PASS |
| Pytest, invoked by check.py | 296 passed in 239.33 seconds |
| Focused licence tests | 28 passed |
| Generated starter / toolchain structure | 28/28 each |
| Unmodified core v0.9.1, S01–S26 | 26/26; Apache-2.0 inferred |
| Unmodified axis v0.1.1, S01–S26 | 26/26; Apache-2.0 inferred |
| Core UsdValidation preflight | 8 validators imported and loaded; absence fails |
| Committed example | Findings and result match; 4 plugin-free prims, 1 non-blank render |
| Term sweep | 182 repository files, including 1 normalized crate and 3 image metadata records; 0 findings |
| Documentation / release metadata | 23 README links and 10 documentation links resolve; 7 final structure rows pass |
| Nix flake check | 1 attempt; input resolution failed before builds |
| Native build/runtime rows | 4 NOT RUN; missing cached Nix source |

The licence fixtures cover all three allowlisted texts with declared and
inferred metadata, missing LICENSE, manifest/README mismatch and invalid
declarations. Additional directory licences remain informational, including
GPL-3.0; their paths must appear in the README licence section. Dependency
licence names cannot satisfy a mismatched repository declaration.

Tests also reject abridged terms and removed operative wording, accept wrapping
and BSD bullet changes, cover all six generated repository kinds, and enforce
the narrow copyright attribution exceptions. The holder in a code docstring
fails; private addresses still fail inside README licence sections.

To reproduce the source gate, set PYTHON to a USD-enabled interpreter,
USDAECO_CORE_DIR to the frozen core v0.8.4 compatibility checkout, CORE_PLUGIN_DIR
to its built resource directory, and PYTHONDONTWRITEBYTECODE=1 for read-only
dependencies. Use the existing usdrecord/usdchecker wrappers and external Nix
overrides described in [native verification](native-verification.md).

```sh
env -u PYTHONPATH "$PYTHON" check.py
env -u PYTHONPATH "$PYTHON" -m pytest -q tests/test_licences.py
```

For current consumer lint, use core v0.9.1 resources instead. Make that checkout
importable with `env -u PYTHONPATH PYTHONPATH="$CORE_CHECKOUT"`. Import this
checkout's usdaeco_check.structure before usdAecoValidators and assert its
module path, since dependency plugin imports can add another toolchain to
sys.path. Import usdAecoValidators explicitly, require its eight validators
to load through UsdValidation, then run S01–S26 on both consumer checkouts.
These probes read the consumers without rebuilding or modifying them.

## Deviations

The one offline Nix attempt used local source and cached store overrides with
builders and substitution disabled. A local override referred to a missing
cached systems source, so evaluation stopped during input resolution. No
second flake-check attempt was made. Native builds and Linux execution are
not proven. The native gate now recognizes this precise missing cached-source
diagnostic as an unavailable prerequisite; missing project sources and actual
native build defects remain failures.

The inherited runtime compatibility tests still use core v0.8.4. Current core
v0.9.1 and axis v0.1.1 compatibility was measured separately through the
unmodified consumer structure checks. The starter still targets core v0.9.0
and proves its minimal example; a pinned data-centre integration is not claimed.
