import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from usdaeco_check.plugins import read_json


def run_python(code, *args, plugins=(), **environment):
    env = {key: value for key, value in os.environ.items()
           if key not in ("PYTHONPATH", "PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH")}
    env.update(environment)
    env["PXR_PLUGINPATH_NAME"] = os.pathsep.join(map(str, plugins))
    # Source imports also work before installing the package into this Python.
    setup = f"import sys; sys.path.insert(0, {str(ROOT / 'tools')!r});\n"
    return subprocess.run([sys.executable, "-c", setup + code, *map(str, args)],
                          text=True, capture_output=True, env=env, cwd=ROOT)


def make_plugin(directory, name, version="0.1.0", requires=None, tier="kind"):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plugInfo.json").write_text(json.dumps({"Plugins": [{
        "Name": name, "Type": "resource", "Root": ".", "ResourcePath": ".",
        "Info": {"aeco": {"version": version, "tier": tier, "requires": requires or {}}}
    }]}))
    return directory


@pytest.fixture(scope="session")
def core():
    checkout = Path(os.environ.get("USDAECO_CORE_DIR", ROOT.parent / "usdaeco-core")).resolve()
    plugin = Path(os.environ.get("CORE_PLUGIN_DIR", checkout / "out/plugins/usdAeco/resources")).resolve()
    assert (plugin / "usdAeco/schema.usda").is_file(), "Built core resources required; set USDAECO_CORE_DIR for another checkout"
    fixture = json.loads((ROOT / "dependencies.json").read_text())["fixtures"]["core"]
    assert json.loads((checkout / "library.json").read_text())["version"] == fixture["ref"].removeprefix("v"), "Core checkout must match the declared fixture tag"
    metadata = read_json(plugin / "plugInfo.json")["Plugins"][0]["Info"]["aeco"]
    assert metadata["version"] == fixture["ref"].removeprefix("v"), "Built core resources must match the declared fixture tag"
    return checkout, plugin


@pytest.fixture(scope="session")
def template_library(tmp_path_factory, core):
    from new_library import new_library
    directory = new_library("usdAecoTest", tmp_path_factory.mktemp("template") / "library with spaces")
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment.update(PYTHON=sys.executable, TOOLCHAIN_DIR=str(ROOT), CORE_DIR=str(core[0]))
    result = subprocess.run(["bash", str(directory / "build.sh"), "--install-root", str(directory / "out/install")], env=environment,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Could not load sublayer" not in result.stderr
    # Also regenerate committed source files; install output remains isolated.
    generated = subprocess.run(["bash", str(directory / "build.sh")], env=environment, text=True, capture_output=True)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    return directory, directory / "out/install/plugins/usdAecoTest/resources"
