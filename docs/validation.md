# Python validation plugins

Register the schema resource directories first, then call
`Plug.Registry().RegisterPlugins()` with an absolute validator directory path,
then construct `UsdValidation.ValidationRegistry()`. The supported `usdaeco_check.validation.run` route adds registered source
plugin package parents to sys.path before loading. For direct registry use, run
from the repository root, install the companion package, or add that root to
sys.path in the calling script. Clearing PYTHONPATH
protects the USD ABI; it does not install a Python plugin.

```python
from usdaeco_check.validation import register_prim_validator, register_stage_validator, wrap_legacy, run

register_prim_validator("usdAecoSampleValidators:DriverChecker", prim_task, ["UsdGeomXform"])
register_stage_validator("usdAecoSampleValidators:StageChecker", wrap_legacy("StageChecker", legacy_check))
errors = run(stage, ["UsdAecoSampleValidators"])
```

Callbacks take a prim or stage, optionally followed by a time range. Native
plugin registration uses the descriptor metadata; standalone registration
constructs equivalent ValidatorMetadata. schema_types are registered Tf names,
not stage schema identifiers. The registry's ValidationContext dispatches the
rules. Unknown keywords fail instead of passing with zero selected rules.

Legacy ValidationError objects pass through. Dictionaries accept name/code,
path, message, severity; triples accept (code, path, message); strings use the
adapter's error name. Legacy error spellings are retained, including earlier
lowercase codes. New error tokens use ProperCase.

The tested Python runtime exposes the real UsdValidation API. No shim is used.
For source checkout CLI validation, run from the generated repository root:

```sh
export PXR_PLUGINPATH_NAME="$CORE_PLUGIN_DIR:$PWD/usdAecoExample:$PWD/usdAecoExampleValidators"
env -u PYTHONPATH usdchecker --includeKeywords UsdAecoExampleValidators --dumpRules usdAecoExample/examples/minimal.usda
```

Both rules must be listed and loaded without Python import diagnostics. Some
usdchecker builds return success after a Python plugin load error; exit status
alone is insufficient evidence.

Any gate selecting the core's `UsdAecoValidators` keyword must also make the
core checkout importable. `PXR_PLUGINPATH_NAME` discovers descriptors; it does
not put Python packages on sys.path. Keep `PYTHONPATH` cleared when launching
the USD interpreter, then explicitly add the core checkout to sys.path (or use
the shared `run` helper, which adds registered plugin package parents):

```python
import os
from pathlib import Path
import sys
from pxr import Plug, UsdValidation

core = Path(os.environ["USDAECO_CORE_DIR"]).resolve()
sys.path.insert(0, str(core))
Plug.Registry().RegisterPlugins(str(Path(os.environ["CORE_PLUGIN_DIR"]).resolve()))
Plug.Registry().RegisterPlugins(str(core / "usdAecoValidators"))
import usdAecoValidators  # Import errors must fail this gate.

registry = UsdValidation.ValidationRegistry()
metadata = registry.GetValidatorMetadataForKeyword("UsdAecoValidators")
assert metadata, "core validator selection is empty"
validators = [registry.GetOrLoadValidatorByName(item.name) for item in metadata]
assert all(validators), "a core validator failed to import/load"
```

Do not catch an import error and continue, accept an empty validator selection,
or report a passed validation from the CLI exit status alone. The validator
gate intentionally loads family plugins; the separate S27/S28 processes clear
family plugin/search paths to prove stock USD composition and rendering.
