import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, run_python
from new_library import new_library
from usdaeco_check.plugins import read_json


def build(name, source, output, dependencies):
    args = ["bash", str(ROOT / "build.sh"), name, str(source), str(output)]
    for dependency in dependencies:
        args += ["--dep", str(dependency)]
    # Exercise the shell entry point's protection from an inherited PYTHONPATH.
    return subprocess.run(args, capture_output=True, text=True,
                          env={**os.environ, "PYTHON": sys.executable, "PYTHONPATH": "/not-a-python-environment"})


def test_new_library_names_and_existing_target(tmp_path):
    for name in ("../bad", "usdAeco", "AecoExample", "usdAecolower"):
        with pytest.raises(ValueError):
            new_library(name, tmp_path / "invalid")
    target = new_library("usdAecoExample", tmp_path / "example")
    before = (target / "usdAecoExample/schema.usda").read_bytes()
    with pytest.raises(FileExistsError):
        new_library("usdAecoChanged", target)
    assert (target / "usdAecoExample/schema.usda").read_bytes() == before
    assert os.access(target / "build.sh", os.X_OK)


@pytest.mark.core
def test_template_build_and_check(core, template_library):
    directory, plugin = template_library
    data = read_json(plugin / "plugInfo.json")
    entry, = data["Plugins"]
    assert entry["Type"] == "resource" and entry["LibraryPath"] == ""
    assert entry["Info"]["aeco"] == {"version": "0.1.0", "tier": "kind", "requires": {"usdAeco": ">=0.9,<1.0"}}
    assert (plugin / "usdAecoTest/schema.usda").read_bytes() == (directory / "usdAecoTest/schema.usda").read_bytes()
    assert "@PLUG_INFO_" not in (plugin / "plugInfo.json").read_text()
    assert not list(plugin.glob("*.cpp"))
    result = run_python('''
import runpy
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name="__main__")
''', directory / "check.py", TOOLCHAIN_DIR=str(ROOT), CORE_PLUGIN_DIR=str(core[1]))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "36 checks, 0 failed" in result.stdout
    print(result.stdout.strip())


@pytest.mark.core
def test_build_against_installed_core_without_bootstrap(tmp_path, core):
    installed = tmp_path / "installed-core"
    shutil.copytree(core[1], installed)
    source = new_library("usdAecoInstalled", tmp_path / "source")
    result = build("usdAecoInstalled", source, tmp_path / "out", [installed])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Could not load sublayer" not in result.stderr
    probe = run_python('''
from pxr import Usd
definition = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoInstalledAPI")
assert definition.GetPropertyMetadata("aeco:installed:derived", "aecoDerived") is True
''', plugins=[installed, tmp_path / "out"])
    assert probe.returncode == 0, probe.stdout + probe.stderr


@pytest.mark.core
def test_downstream_sublayers_installed_dependency_source(tmp_path, core, template_library):
    source = new_library("usdAecoDownstream", tmp_path / "downstream")
    manifest = json.loads((source / "library.json").read_text())
    manifest.update(tier="record", requires={"usdAeco": ">=0.7", "usdAecoTest": ">=0.1"})
    (source / "library.json").write_text(json.dumps(manifest))
    schema = (source / "usdAecoDownstream/schema.usda").read_text().replace(
        "@usdAeco/schema.usda@", "@usdAeco/schema.usda@,\n        @usdAecoTest/schema.usda@")
    schema = schema.replace("inherits = </APISchemaBase>",
                            'inherits = </APISchemaBase>\n    prepend apiSchemas = ["AecoTestAPI"]')
    (source / "usdAecoDownstream/schema.usda").write_text(schema)
    result = build("usdAecoDownstream", source, tmp_path / "out", [core[1], template_library[1]])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Could not load sublayer" not in result.stderr
    probe = run_python('''
from pxr import Usd
definition = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoDownstreamAPI")
assert definition.GetPropertyMetadata("aeco:test:derived", "aecoDerived") is True
assert definition.GetPropertyMetadata("aeco:downstream:derived", "aecoDerived") is True
''', plugins=[core[1], template_library[1], tmp_path / "out"])
    assert probe.returncode == 0, probe.stdout + probe.stderr


def test_build_rejects_undeclared_or_absent_core(tmp_path):
    source = new_library("usdAecoMissing", tmp_path / "source")
    result = build("usdAecoMissing", source, tmp_path / "out", [])
    assert result.returncode != 0 and "plugin absent" in result.stderr
    assert not (tmp_path / "out/plugInfo.json").exists()


@pytest.mark.core
def test_builder_can_build_core_and_register_metadata(tmp_path, core):
    source = tmp_path / "source"
    shutil.copytree(core[0] / "usdAeco", source / "usdAeco")
    shutil.copyfile(core[0] / "library.json", source / "library.json")
    result = build("usdAeco", source, tmp_path / "out", [])
    assert result.returncode == 0, result.stdout + result.stderr
    probe = run_python('''
from pxr import Sdf, Usd
from usdaeco_check import plugin_requires
assert plugin_requires()
assert Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoDerivedGeometryAPI")
stage = Usd.Stage.CreateInMemory()
attribute = stage.DefinePrim("/Probe", "Xform").CreateAttribute("aeco:probe:derived", Sdf.ValueTypeNames.Double)
assert attribute.SetMetadata("aecoDerived", True)
assert attribute.GetMetadata("aecoDerived") is True
''', plugins=[tmp_path / "out"])
    assert probe.returncode == 0, probe.stdout + probe.stderr


@pytest.mark.core
@pytest.mark.parametrize("defect", ["name", "codegen", "sublayer"])
def test_builder_rejects_invalid_schema(tmp_path, core, defect):
    source = new_library("usdAecoInvalid", tmp_path / "source")
    schema = (source / "usdAecoInvalid/schema.usda").read_text()
    if defect == "name":
        schema = schema.replace('libraryName = "usdAecoInvalid"', 'libraryName = "wrong"')
    elif defect == "codegen":
        schema = schema.replace("skipCodeGeneration = true", "skipCodeGeneration = false")
    else:
        schema = schema.replace("@usdAeco/schema.usda@", "@missing/schema.usda@")
    (source / "usdAecoInvalid/schema.usda").write_text(schema)
    result = build("usdAecoInvalid", source, tmp_path / "out", [core[1]])
    assert result.returncode != 0
    assert not (tmp_path / "out/plugInfo.json").exists()


@pytest.mark.core
def test_examples_require_fallback_for_concrete_core_types(tmp_path, core):
    stage = tmp_path / "example.usda"
    stage.write_text('#usda 1.0\ndef AecoPort "Port" {}\n')
    result = run_python('''
from usdaeco_check import validate_examples
r = validate_examples(sys.argv[1], []); print(r.detail)
assert not r and "missing fallbackPrimTypes" in r.detail
''', tmp_path, plugins=[core[1]])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.core
def test_strict_builder_refuses_unsupported_core_range(tmp_path, core):
    source = new_library("usdAecoFuture", tmp_path / "future")
    path = source / "library.json"
    manifest = read_json(path)
    manifest["requires"]["usdAeco"] = ">=1.0,<2.0"
    path.write_text(json.dumps(manifest))
    result = build("usdAecoFuture", source, tmp_path / "out", [core[1]])
    assert result.returncode != 0 and "requires usdAeco >=1.0,<2.0" in result.stderr


@pytest.mark.core
def test_flat_source_dependency_and_installed_validator_layout(tmp_path, core, template_library):
    from usdaeco_check.plugins import discover
    source = new_library("usdAecoFlat", tmp_path / "source")
    manifest = json.loads((source / "library.json").read_text())
    manifest["requires"]["usdAecoTest"] = ">=0.1"
    (source / "library.json").write_text(json.dumps(manifest))
    schema = source / "usdAecoFlat/schema.usda"
    schema.write_text(schema.read_text().replace("@usdAeco/schema.usda@", "@usdAeco/schema.usda@, @usdAecoTest/schema.usda@"))
    result = build("usdAecoFlat", source, tmp_path / "out", [core[1], template_library[0] / "usdAecoTest"])
    assert result.returncode == 0, result.stdout + result.stderr
    installed = template_library[0] / "out/install"
    assert set(discover([installed])) == {"usdAecoTest", "usdAecoTestValidators"}
    assert (installed / "python/usdAecoTestValidators/__init__.py").is_file()


def test_new_library_command_named_arguments(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "tools/new_library.py"), "--kind", "usecase", "--name", "Named", "--tier", "sector", str(tmp_path / "named")], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((tmp_path / "named/library.json").read_text())
    assert manifest["name"] == "usdAecoNamed" and manifest["tier"] == "sector"
    import hashlib
    example_manifest = json.loads((tmp_path / "named/examples/datacentre/manifest.json").read_text())
    assert example_manifest["source"]["sha256"] == hashlib.sha256((tmp_path / "named/usdAecoNamed/examples/minimal.usda").read_bytes()).hexdigest()
