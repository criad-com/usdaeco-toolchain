import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, run_python


@pytest.mark.core
def test_clean_core_registry_runs_all_eight_validators(core):
    result = run_python('''
from pxr import Plug, Sdf, Usd, UsdValidation
Plug.Registry().RegisterPlugins(sys.argv[1])
import usdAecoValidators  # Import failure must fail the gate.
registry = UsdValidation.ValidationRegistry()
metadata = registry.GetValidatorMetadataForKeyword("UsdAecoValidators")
assert len(metadata) == 8, [m.name for m in metadata]
assert all(registry.GetOrLoadValidatorByName(m.name) for m in metadata)
from usdaeco_check.validation import run
stage = Usd.Stage.CreateInMemory()
assert run(stage, ["UsdAecoValidators"]) == []
for path in ("/First", "/Second"):
    prim = stage.DefinePrim(path, "Xform")
    prim.AddAppliedSchema("AecoElementAPI")
    prim.GetAttribute("aeco:id").Set("element.same")
assert "duplicateId" in {error.GetName() for error in run(stage, ["UsdAecoValidators"])}
print("8 core validators loaded; duplicate identity detected")
''', core[0] / "usdAecoValidators", plugins=[core[1]],
        PYTHONPATH=str(core[0]), TOOLCHAIN_DIR=str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


def test_template_registry_discovers_two_real_validators():
    result = run_python('''
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pxr import Plug, Sdf, Usd, UsdValidation
Plug.Registry().RegisterPlugins(str(Path(sys.argv[1]) / "usdAecoExample"))
Plug.Registry().RegisterPlugins(str(Path(sys.argv[1]) / "usdAecoExampleValidators"))
registry = UsdValidation.ValidationRegistry()
metadata = registry.GetValidatorMetadataForKeyword("UsdAecoExampleValidators")
assert len(metadata) == 2, [m.name for m in metadata]
print("2 validators: " + ", ".join(sorted(m.name for m in metadata)))
from usdaeco_check.validation import run
stage = Usd.Stage.Open(str(Path(sys.argv[1]) / "usdAecoExample/examples/minimal.usda"))
assert run(stage, ["UsdAecoExampleValidators"]) == []
stage.GetPrimAtPath("/Example").GetAttribute("aeco:example:driver").Set(-1)
assert [e.GetName() for e in run(stage, ["UsdAecoExampleValidators"])] == ["InvalidDriver"]
''', ROOT / "template")
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)


def test_explicit_registration_and_legacy_errors():
    result = run_python('''
from pxr import Usd, UsdValidation
from usdaeco_check.validation import register_prim_validator, register_stage_validator, wrap_legacy, run
stage = Usd.Stage.CreateInMemory()
prim = stage.DefinePrim("/Thing", "Xform")
register_prim_validator("usdAecoProbeValidators:PrimChecker", lambda prim: [], ["UsdGeomXform"])
wrapped = wrap_legacy("usdAecoProbeValidators:LegacyChecker", lambda stage: [
    {"code":"OldCode", "path":"/Thing", "message":"legacy", "severity":"warn"},
    ("TupleError", "/Thing", "triple"), "message"])
register_stage_validator("usdAecoProbeValidators:LegacyChecker", wrapped)
errors = run(stage, ["UsdAecoProbeValidators"])
assert len(errors) == 3
assert {e.GetName() for e in errors} == {"OldCode", "TupleError", "LegacyChecker"}
assert sum(e.GetType() == UsdValidation.ValidationErrorType.Warn for e in errors) == 1
try:
    run(stage, ["MissingKeyword"])
except ValueError:
    pass
else:
    raise AssertionError("missing keyword passed")
''')
    assert result.returncode == 0, result.stdout + result.stderr


def test_plugin_metadata_registration_helpers(tmp_path):
    plugin = tmp_path / "usdAecoHelperValidators"
    plugin.mkdir()
    (plugin / "plugInfo.json").write_text(json.dumps({"Plugins":[{"Name":plugin.name,"Type":"python","Info":{"Validators":{
        "keywords":["UsdAecoHelperValidators"],"PrimChecker":{"doc":"prim", "schemaTypes":["UsdGeomXform"]},"StageChecker":{"doc":"stage"}}}}]}))
    (plugin / "__init__.py").write_text('''from usdaeco_check.validation import register_prim_validator, register_stage_validator
register_prim_validator("usdAecoHelperValidators:PrimChecker", lambda p: [], ["UsdGeomXform"])
register_stage_validator("usdAecoHelperValidators:StageChecker", lambda s: [])
''')
    result = run_python('''
from pxr import Plug, Usd
Plug.Registry().RegisterPlugins(sys.argv[2])
from usdaeco_check.validation import run
assert run(Usd.Stage.CreateInMemory(), ["UsdAecoHelperValidators"]) == []
''', tmp_path, plugin)
    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_preserves_existing_validation_errors():
    from pxr import Usd, UsdValidation
    from usdaeco_check.validation import wrap_legacy
    error = UsdValidation.ValidationError("Existing", UsdValidation.ValidationErrorType.Error, [], "existing")
    errors = wrap_legacy("Example", lambda s: [error])(Usd.Stage.CreateInMemory())
    assert errors[0].GetName() == "Existing"


def test_usdchecker_lists_template_validators():
    import os
    command = shutil.which("usdchecker")
    if not command:
        pytest.skip("usdchecker executable is unavailable")
    template = ROOT / "template"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PXR_PLUGINPATH_NAME"] = os.pathsep.join(str(template / p) for p in ("usdAecoExample", "usdAecoExampleValidators"))
    result = subprocess.run([command, "--includeKeywords", "UsdAecoExampleValidators", "--dumpRules",
                             "usdAecoExample/examples/minimal.usda"], cwd=template, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[usdAecoExampleValidators:DriverChecker]" in result.stdout
    assert "[usdAecoExampleValidators:StageChecker]" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr, result.stderr
    print("usdchecker lists and loads 2 validators")
