import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


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
    plugin = Path(os.environ.get("CORE_PLUGIN_DIR", checkout / "plugins/usdAeco/resources")).resolve()
    assert (plugin / "usdAeco/schema.usda").is_file(), "Built core resources required; set USDAECO_CORE_DIR for another checkout"
    return checkout, plugin


@pytest.fixture(scope="session")
def template_library(tmp_path_factory, core):
    from new_library import new_library
    directory = compatibility_library("usdAecoTest", tmp_path_factory.mktemp("template") / "library with spaces")
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


def compatibility_library(name, target):
    """Explicit v0.8.4 probe copy; never relax the shipped v0.9 target contract."""
    from new_library import new_library
    repo = new_library(name, target)
    target_ref = json.loads((repo / "dependencies.json").read_text())["repos"]["core"]["ref"]
    fixture_ref = json.loads((ROOT / "dependencies.json").read_text())["fixtures"]["core"]["ref"]
    for path in repo.rglob("*"):
        if path.is_file():
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            path.write_text(text.replace(">=0.9,<1.0", ">=0.8,<0.9").replace(target_ref, fixture_ref))
    from usdaeco_check.example_result import file_records
    manifest = repo / "examples/datacentre/manifest.json"
    data = json.loads(manifest.read_text())
    data["result"]["files"] = file_records(manifest.parent / "result")
    data["result"]["bytes"] = sum(i["bytes"] for i in data["result"]["files"])
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    return repo
