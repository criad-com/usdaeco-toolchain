# Verification

Current v0.3.0 gates, native reporting and CMake smoke evidence are recorded in
[native verification](native-verification.md). The following v0.2.3 measurements
are retained as the baseline for ownership lint and consumer comparisons.

## v0.2.3 release evidence

Version 0.2.3, measured with Python 3.13.12, USD 26.8 and Pillow 12.3.0.
Setuptools is absent. Checks import the source tree; no package was installed.

| Acceptance row | Measured result |
|---|---|
| Full Python gate | **56 checks, 0 failed; 221 tests passed**, pytest elapsed 80.93 seconds |
| Generated template / toolchain structure | 26/26 each; all 26 seeded rule defects rejected |
| Ownership smoke | 59 tests passed: 29 new declaration cases and 30 existing namespace cases |
| Declaration fixtures | All four outcomes exercised for single-apply properties and multiple-apply propertyNamespacePrefix: declared extras pass, undeclared extras fail, malformed arrays fail, unused namespaces warn without failing |
| Family smoke | 19 tests passed against the read-only sibling inventory, including schema-free dependency validation |
| Family comparison | 16 repositories, 7 schema libraries, 11 manifests compared, 3 legacy manifests unavailable, 2 checkouts absent; 1 unreleased seed and 4 incompatible requirements reported |
| Sanitization | S25 PASS; no findings under the existing registry allowlist |
| Nix | Exactly one attempt, exit 1: processing-toolchain input HTTP 404 before evaluation/build; checks **not proven** |

## Consumer comparisons

Both versions of the shared lint ran directly on clean snapshots. No consumer
wrapper, accepted-failure filter or schema edit was used. Only the patched wall
snapshot received a temporary library.json overlay declaring namespaces
`["wall", "opening"]` and classPrefixes `["AecoWall", "AecoOpening"]`.

| Consumer | Source revision | v0.2.2 baseline | Patched lint |
|---|---|---|---|
| core v0.9.1 | ee20aa7e20590d9893d4fbf67a39fb3a0ea782d0 | 26/26 | **26/26** |
| axis v0.1.0 | 627dbb5e19ca9070dd123432f2acb46b3ad38f51 | 26/26 | **26/26** |
| build-up v0.2.0 | 0852913e366f765096505260184c15cb4bbffceb | 25/26, S10 FAIL | **25/26**, same S10 FAIL |
| cctv v0.5.0 | d38045082b04028152dfd0aec0869fd5c4037451 | 26/26 | **26/26** |
| wall v0.2.0 candidate | 37f0fab20000811b57449b09bb4e135b60a8bdc3 | 24/26, S08/S09 FAIL | **26/26**, manifest overlay only |

## Commands and dependencies

Run from the toolchain checkout with PYTHON selecting an existing USD-enabled
interpreter and its bin directory on PATH. The compatibility tests still use
core v0.8.4, as pinned in dependencies.json and flake.nix. Point these variables
at its existing checkout and built resources; no dependency rebuild is needed.
Example paths assume sibling checkouts.

```sh
export USDAECO_CORE_DIR="../usdaeco-core-0.8"
export CORE_PLUGIN_DIR="$USDAECO_CORE_DIR/plugins/usdAeco/resources"
export AECO_FAMILY_SIBLINGS=".."
export PYTHONDONTWRITEBYTECODE=1
env -u PYTHONPATH "$PYTHON" check.py
```

The full gate invokes pytest itself, including source imports through conftest.py.
For consumer probes, set CURRENT_CORE_DIR, AXIS_DIR, BUILDUP_DIR, CCTV_DIR and
WALL_DIR to the checkouts matching the revisions above. Core and axis use their
existing out/plugins resources; build-up uses its flat source module. All
schema parsing and generation occurs in scratch snapshots. For the baseline,
set LINT_TOOLS to the released v0.2.2 tools directory and omit
AECO_WALL_OWNERSHIP; for the patched run, set LINT_TOOLS to this checkout's tools
directory and AECO_WALL_OWNERSHIP to 1.

```sh
env -u PYTHONPATH "$PYTHON" - <<'PROBE'
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
sys.path.insert(0, os.environ['LINT_TOOLS'])
from usdaeco_check.structure import check_structure, print_results
core = Path(os.environ['CURRENT_CORE_DIR']).resolve()
axis = Path(os.environ['AXIS_DIR']).resolve()
buildup = Path(os.environ['BUILDUP_DIR']).resolve()
deps = [core / 'out/plugins/usdAeco/resources',
        axis / 'out/plugins/usdAecoAxis/resources', buildup / 'usdAecoBuildUp']
with tempfile.TemporaryDirectory(prefix='aeco-consumer-lint-') as temporary:
    for variable in ('CURRENT_CORE_DIR', 'AXIS_DIR', 'BUILDUP_DIR',
                     'CCTV_DIR', 'WALL_DIR'):
        source = Path(os.environ[variable]).resolve()
        print(f'== stage: unmodified structure {source.name}', flush=True)
        archive = subprocess.check_output(['git', '-C', str(source), 'archive', 'HEAD'])
        snapshot = Path(temporary) / variable
        snapshot.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(snapshot, filter='data')
        if variable == 'WALL_DIR' and os.environ.get('AECO_WALL_OWNERSHIP') == '1':
            manifest = snapshot / 'library.json'
            data = json.loads(manifest.read_text())
            data.update(namespaces=['wall', 'opening'],
                        classPrefixes=['AecoWall', 'AecoOpening'])
            manifest.write_text(json.dumps(data, indent=2))
        print_results(check_structure(snapshot, deps=deps))
PROBE
```

S11 creates temporary generated files beside the inspected schema. Snapshots
keep that work outside the read-only consumer checkouts. None of those consumers
was edited or rebuilt. Core resources register first.

## Deviations

- Build-up retains its existing S10 failure because the unrestricted API lacks
  the explicit applicability marker and explanation. Its result is unchanged.
- Exactly one `nix flake check --offline --no-write-lock-file` attempt failed
  resolving the pinned public processing-toolchain revision with HTTP 404.
  No retry was made. Nix evaluation, builds and platform checks remain **not proven**.
- This patch is based on v0.2.2 and releases as v0.2.3. Native build reporting
  is deferred; this base exposes no native build/runtime rows.
- The released-set fixture records toolchain v0.2.2, matching the stable sibling,
  while this branch prepares v0.2.3. Recording the unreleased candidate tag would
  fail exact sibling comparison. Advance the inventory after release tagging
  and sibling update; no version check was relaxed.
- The remaining fixture entries match available released manifests. Schema-free
  dependencies needed a small family-validator extension: data-centre v0.4.2
  requires usdaeco-revit, whose schema-library identifier is null. Missing
  dependencies, cycles and incompatible ranges remain rejected in strict mode.
- Sync and all three integration releases still require core below v0.9. Their
  four incompatible requirements are reported in inventory mode; a compatible
  release train is **not proven**. Three legacy manifests and two absent
  checkouts cannot be compared.
- Legacy runtime tests remain on pinned core v0.8.4. Consumer structure probes
  use current core v0.9.1 and do not claim wider runtime compatibility.

## Remaining work

The v0.3.0 native verification record tracks the current Nix build limitations.
The consumer results above are historical: downstream declarations and release
pins require fresh comparison when their versions advance. The released-set
fixture remains an inventory, not a proven compatible release train.
