import json
import os
from pathlib import Path
import shutil

import pytest

from conftest import make_plugin, run_python
from pluginset import plugin_set


def test_plugin_set_computes_transitive_closure_and_relocates(tmp_path, monkeypatch):
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    family = tmp_path / "family"
    core = make_plugin(family / "core", "usdAeco", "0.7", tier="core")
    kind = make_plugin(family / "kind", "usdAecoKind", requires={"usdAeco": ">=0.7"})
    record = make_plugin(family / "record", "usdAecoRecord", requires={"usdAecoKind": ">=0.1"}, tier="record")
    unrelated = make_plugin(family / "unused", "usdAecoUnused", requires={"Missing": ">=1"})
    names = plugin_set(family / "set", [record], [core, kind, unrelated])
    assert names == ["usdAeco", "usdAecoKind", "usdAecoRecord"]
    descriptor = json.loads((family / "set/plugInfo.json").read_text())
    assert all(not Path(path).is_absolute() for path in descriptor["Includes"])
    assert len(descriptor["Includes"]) == 3
    moved = tmp_path / "moved"
    shutil.move(family, moved)
    result = run_python('''
from pxr import Plug
from usdaeco_check import plugin_requires
assert plugin_requires()
names = {p.name for p in Plug.Registry().GetAllPlugins()}
assert {"usdAeco", "usdAecoKind", "usdAecoRecord"} <= names
assert "usdAecoUnused" not in names
''', plugins=[moved / "set"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_plugin_set_searches_environment(tmp_path, monkeypatch):
    core = make_plugin(tmp_path / "core", "usdAeco", "0.7", tier="core")
    kind = make_plugin(tmp_path / "kind", "usdAecoKind", requires={"usdAeco": ">=0.7"})
    monkeypatch.setenv("PXR_PLUGINPATH_NAME", str(core))
    assert plugin_set(tmp_path / "set", [kind]) == ["usdAeco", "usdAecoKind"]


@pytest.mark.parametrize("version", [None, "0.6"])
def test_plugin_set_rejects_missing_or_old_dependency(tmp_path, monkeypatch, version):
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    kind = make_plugin(tmp_path / "kind", "usdAecoKind", requires={"usdAeco": ">=0.7"})
    search = [] if version is None else [make_plugin(tmp_path / "core", "usdAeco", version, tier="core")]
    with pytest.raises(ValueError, match="absent|found 0.6"):
        plugin_set(tmp_path / "set", [kind], search)
    assert not (tmp_path / "set/plugInfo.json").exists()


def test_plugin_set_rejects_conflicting_names(tmp_path, monkeypatch):
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    one = make_plugin(tmp_path / "one", "usdAeco", "0.7", tier="core")
    two = make_plugin(tmp_path / "two", "usdAeco", "0.8", tier="core")
    with pytest.raises(ValueError, match="duplicate plugin name"):
        plugin_set(tmp_path / "set", [one, two])


def test_plugin_set_cannot_overwrite_input(tmp_path, monkeypatch):
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    core = make_plugin(tmp_path / "core", "usdAeco", "0.7", tier="core")
    before = (core / "plugInfo.json").read_bytes()
    with pytest.raises(ValueError, match="must not replace"):
        plugin_set(core, [core])
    assert (core / "plugInfo.json").read_bytes() == before


@pytest.mark.core
def test_plugin_set_registers_core_and_template_from_one_path(tmp_path, core, template_library, monkeypatch):
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    aggregate = tmp_path / "aggregate"
    assert plugin_set(aggregate, [template_library[1]], [core[1]]) == ["usdAeco", "usdAecoTest"]
    result = run_python('''
from pxr import Plug, Tf
from usdaeco_check import plugin_requires, registry_probe
assert plugin_requires()
apis = ["AecoProjectAPI", "AecoElementAPI", "AecoClassificationAPI", "AecoTypeAPI",
        "AecoAxisAPI", "AecoDerivedGeometryAPI", "AecoTestAPI"]
types = ["AecoSite", "AecoFacility", "AecoFacilityPart", "AecoLevel", "AecoSpace",
         "AecoSystem", "AecoZone", "AecoPort"]
r = registry_probe(apis, types)
assert r, r.detail
for name in ("usdAeco", "usdAecoTest"):
    for type_name in Plug.Registry().GetPluginWithName(name).metadata["Types"]:
        assert not Tf.Type.FindByName(type_name).isUnknown, type_name
print("PASS one path registers core + template: " + r.detail)
''', plugins=[aggregate])
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())
