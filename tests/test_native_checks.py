from pathlib import Path
import subprocess

import pytest

import native_check
from usdaeco_check import Report


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clean_native_environment(monkeypatch):
    for name in ("AECO_NATIVE_SCHEMA", "AECO_NATIVE_PLUGIN", "AECO_NATIVE_PYTHON",
                 "AECO_USD_PYTHON", "AECO_NIX_ARGS"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("diagnostic", [
    "error: unable to start any build; either increase '--max-jobs' or enable remote builds",
    "error: cannot fetch input because it is not cached and offline mode is enabled",
    "error: unable to download required source: connection refused",
    "error: path 'required-source' is required, but there is no substituter",
    "error: builder for 'source.drv' failed: couldn't resolve host",
    "error: path '" + str(Path("/", "nix", "store", "0" * 32 + "-source")) + "' does not exist",
    "error: Cannot build 'ncurses-6.6.drv'.\n       Reason: required system or feature not available\n"
    "error: Cannot build 'usdAecoExampleNative-0.1.0.drv'.\n       Reason: 1 dependency failed.",
])
def test_unavailable_prerequisites_leave_all_native_rows_not_run(monkeypatch, capsys, diagnostic):
    monkeypatch.setenv("AECO_NIX_ARGS", "--offline --max-jobs 0")

    def run(command, **kwargs):
        assert command[:2] == ["nix", "build"]
        assert "--offline" in command and "--max-jobs" in command
        return subprocess.CompletedProcess(command, 1, "", diagnostic)

    monkeypatch.setattr(native_check.subprocess, "run", run)
    report = Report()
    native_check.native_checks(report, ROOT)
    assert [r.name for r in report.results] == list(native_check.NATIVE_ROWS)
    assert all(r.ok is None and r.detail for r in report.results)
    assert report.finish() == 0
    assert "4 checks, 0 failed, 4 not run" in capsys.readouterr().out


def test_missing_nix_is_not_run(monkeypatch):
    def run(*args, **kwargs):
        raise FileNotFoundError("nix")

    monkeypatch.setattr(native_check.subprocess, "run", run)
    report = Report()
    native_check.native_checks(report, ROOT)
    assert report.failed == 0 and report.not_run_count == 4
    assert all("nix executable" in r.detail for r in report.results)


@pytest.mark.parametrize("diagnostic", [
    "error: builder for 'usdAecoExampleNative-0.1.0.drv' failed with exit code 2",
    "error: Cannot build 'usdAecoExampleHello-0.1.0.drv'.\n       Reason: builder failed with exit code 1.\nconnection refused by a runtime test",
    "error: attribute 'template-native-schema' missing",
    "error: path 'template-native/schema' does not exist",
])
def test_build_and_configuration_defects_remain_failures(monkeypatch, diagnostic):
    monkeypatch.setattr(native_check.subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 100, "", diagnostic))
    report = Report()
    native_check.native_checks(report, ROOT)
    assert report.results[0].ok is False
    assert diagnostic in report.results[0].detail
    assert report.failed == 1 and report.not_run_count == 3
    assert report.finish() == 1


@pytest.mark.parametrize("output", ["not json", "[]", '[{"drvPath": "schema.drv"}]'])
def test_successful_nix_with_invalid_output_fails(monkeypatch, output):
    monkeypatch.setattr(native_check.subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, output, ""))
    report = Report()
    native_check.native_checks(report, ROOT)
    assert report.failed == 1 and report.not_run_count == 3


def installed_outputs(tmp_path, monkeypatch):
    for variable, name in (("AECO_NATIVE_SCHEMA", "usdAecoExampleNative"),
                           ("AECO_NATIVE_PLUGIN", "usdAecoExampleHello")):
        root = tmp_path / name
        files = ["lib/plugInfo.json", f"lib/{name}/resources/plugInfo.json",
                 f"lib/cmake/{name}/{name}Config.cmake", f"lib/lib{name}.dylib"]
        if variable == "AECO_NATIVE_SCHEMA":
            files.append("lib/python3.14/site-packages/pxr/UsdAecoExampleNative/_usdAecoExampleNative.so")
        for filename in files:
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        monkeypatch.setenv(variable, str(root))
    monkeypatch.setenv("AECO_NATIVE_PYTHON", "native-python")
    monkeypatch.setenv("AECO_USD_PYTHON", str(tmp_path / "usd-python"))
    monkeypatch.setattr(native_check, "plugin_set", lambda *args: None)


@pytest.mark.parametrize("runtime_failure", [False, True])
def test_installed_probes_record_actual_results(tmp_path, monkeypatch, runtime_failure):
    installed_outputs(tmp_path, monkeypatch)
    calls = []

    def run(command, **kwargs):
        assert command[0] == "native-python"
        calls.append(command)
        failed = runtime_failure and len(calls) == 2
        return subprocess.CompletedProcess(command, int(failed), "", "import failed" if failed else "")

    monkeypatch.setattr(native_check.subprocess, "run", run)
    report = Report()
    native_check.native_checks(report, ROOT)
    assert len(calls) == 3
    assert report.not_run_count == 0
    assert report.failed == int(runtime_failure)
    assert report.results[2].ok is not runtime_failure


def test_invalid_installed_layout_is_failure(tmp_path, monkeypatch):
    installed_outputs(tmp_path, monkeypatch)
    (tmp_path / "usdAecoExampleNative/lib/plugInfo.json").unlink()
    report = Report()
    native_check.native_checks(report, ROOT)
    assert report.failed == 1 and report.not_run_count == 3
