"""Runtime gates for installed native templates, using the pinned USD Python."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

from pluginset import plugin_set


NATIVE_ROWS = ("native-template-builds", "native-discovery", "native-python", "native-tf-plugin")


def prerequisite_cause(diagnostic):
    """Recognize unavailable inputs; never turn a template build defect into a skip."""
    native_derivation = r"[^\n]*usdAecoExample(?:Native|Hello)[^\n]*"
    if (re.search(r"builder for ['\"]" + native_derivation + r"failed", diagnostic, re.I)
            or re.search(r"cannot build ['\"]" + native_derivation
                         + r"\n\s*(?:reason: )?builder failed", diagnostic, re.I)):
        return None
    causes = (
        (r"unable to start any build|no available machine.*build|no build machine",
         "uncached prerequisites cannot be built with the configured offline builders"),
        (r"required system or feature not available",
         "uncached prerequisites require an available builder (Nix: required system or feature not available)"),
        (r"cannot (?:fetch|download).*offline|not available.*offline|offline.*not (?:available|cached)",
         "required inputs are not cached for offline use"),
        (r"unable to download|failed to download|could not resolve (?:host|hostname)|couldn't resolve host|could not connect|couldn't connect|connection refused|network is unreachable",
         "required inputs could not be fetched"),
        (r"cannot substitute.*no substituter|path .* is required, but there is no substituter",
         "required store paths have no available substituter"),
        (r"path ['\"]/{1,2}nix/store/[0-9a-z]{32}-source['\"] does not exist",
         "required cached Nix input source is unavailable"),
    )
    for pattern, cause in causes:
        if re.search(pattern, diagnostic, re.I):
            return cause
    return None


def unavailable(report, cause, *, build_failed=False):
    if build_failed:
        report.check(NATIVE_ROWS[0], False, cause)
    else:
        report.not_run(NATIVE_ROWS[0], cause)
    for name in NATIVE_ROWS[1:]:
        report.not_run(name, cause)


def native_checks(report, repo):
    schema = os.environ.get("AECO_NATIVE_SCHEMA")
    plugin = os.environ.get("AECO_NATIVE_PLUGIN")
    python = os.environ.get("AECO_NATIVE_PYTHON")
    usd_python = os.environ.get("AECO_USD_PYTHON")
    try:
        if not all((schema, plugin, python, usd_python)):
            args = shlex.split(os.environ.get("AECO_NIX_ARGS", ""))
            try:
                result = subprocess.run(["nix", "build", "--no-link", "--json", *args,
                                         ".#template-native-schema", ".#template-native-plugin", ".#nativePython"],
                                        cwd=repo, text=True, capture_output=True)
            except FileNotFoundError:
                unavailable(report, "nix executable is unavailable")
                return
            if result.returncode:
                diagnostic = (result.stdout + result.stderr).strip()
                cause = prerequisite_cause(diagnostic)
                unavailable(report, f"nix prerequisites unavailable: {cause}" if cause else
                            f"nix build exited {result.returncode}: {diagnostic}",
                            build_failed=cause is None)
                return
            outputs = {Path(row["drvPath"]).name.partition("-")[2]: row["outputs"]["out"]
                       for row in json.loads(result.stdout)}
            schema = next(v for k, v in outputs.items() if k.startswith("usdAecoExampleNative-"))
            plugin = next(v for k, v in outputs.items() if k.startswith("usdAecoExampleHello-"))
            environment = next(v for k, v in outputs.items() if "python3-" in k)
            python = str(Path(environment) / "bin/python3")
            usd_python = str(next((Path(environment) / "lib").glob("python*/site-packages")))
        schema, plugin = Path(schema).resolve(), Path(plugin).resolve()
        for root, name in ((schema, "usdAecoExampleNative"), (plugin, "usdAecoExampleHello")):
            assert (root / "lib/plugInfo.json").is_file()
            assert (root / f"lib/{name}/resources/plugInfo.json").is_file()
            assert (root / f"lib/cmake/{name}/{name}Config.cmake").is_file()
            assert any((root / "lib").glob(f"lib{name}.*"))
        schema_python = next((schema / "lib").glob("python*/site-packages"))
        assert any((schema_python / "pxr/UsdAecoExampleNative").glob("_usdAecoExampleNative*.so"))
        report.check("native-template-builds", True, "both installed layouts and compiled Python module")
    except (OSError, ValueError, KeyError, TypeError, AssertionError, StopIteration) as exc:
        unavailable(report, f"invalid native build output or configuration ({type(exc).__name__}): {exc}",
                    build_failed=True)
        return
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONPATH", "PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH")}
    environment["PYTHONPATH"] = os.pathsep.join((str(schema_python), usd_python))
    with tempfile.TemporaryDirectory(prefix="aeco-native-set-") as temporary:
        plugin_set(temporary, (schema, plugin))
        environment["PXR_PLUGINPATH_NAME"] = temporary
        probes = {
            "native-discovery": "from pxr import Plug; r=Plug.Registry(); "
                "assert r.GetPluginWithName('usdAecoExampleNative'); "
                "assert r.GetPluginWithName('usdAecoExampleHello'); print('2 plugins discovered')",
            "native-python": (repo / "template-native/schema/testenv/testSchema.py").read_text(),
            "native-tf-plugin": (repo / "template-native/plugin/testenv/testHello.py").read_text(),
        }
        for name, code in probes.items():
            try:
                result = subprocess.run([python, "-c", code], env=environment, text=True, capture_output=True)
                report.check(name, result.returncode == 0, (result.stdout + result.stderr).strip())
            except OSError as exc:
                report.check(name, False, f"native runtime could not execute: {exc}")
