import json
from pathlib import Path

import pytest
from pluginset import plugin_set
from usdaeco_check.plugins import discover


def native_output(root, name="usdAecoExampleHello", requires=None):
    resources = root / "lib" / name / "resources"
    resources.mkdir(parents=True)
    (root / "lib/plugInfo.json").write_text('{"Includes": ["*/resources/"]}')
    descriptor = resources / "plugInfo.json"
    descriptor.write_text(json.dumps({"Plugins": [{
        "Name": name, "Type": "library", "Root": "..", "ResourcePath": "resources",
        "LibraryPath": f"../lib{name}.dylib", "Info": {
            "Types": {"AecoExampleHello": {}},
            "aeco": {"version": "0.1.0", "tier": "toolchain", "requires": requires or {}}}
    }]}))
    return descriptor


def test_native_install_includes_keep_library_path(tmp_path):
    root = tmp_path / "install with spaces"
    descriptor = native_output(root)
    original = descriptor.read_bytes()
    destination = tmp_path / "set"
    assert plugin_set(destination, [root]) == ["usdAecoExampleHello"]
    plugin = discover([destination])["usdAecoExampleHello"]
    assert plugin.descriptor == descriptor
    assert plugin.resource_path == descriptor.parent
    assert descriptor.read_bytes() == original


def test_native_dependency_closure_and_duplicate_rejection(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    native_output(first, "usdAecoExampleFirst")
    native_output(second, requires={"usdAecoExampleFirst": ">=0.1,<0.2"})
    assert plugin_set(tmp_path / "set", [second], [first]) == ["usdAecoExampleFirst", "usdAecoExampleHello"]
    third = tmp_path / "third"
    native_output(third)
    with pytest.raises(ValueError, match="duplicate plugin name"):
        discover([first, second, third])
