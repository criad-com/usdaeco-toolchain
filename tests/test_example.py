import json
from pathlib import Path
import pytest

from conftest import ROOT, run_python
from new_library import new_library
from usdaeco_check.example import diff_findings, check_example, _source


@pytest.mark.parametrize("declared,elapsed,timeout,passed", [
    ({}, 179, 180, True),
    ({}, 181, 180, False),
    ({"budgetSeconds": 600}, 200, 600, True),
    ({"budgetSeconds": 600}, 601, 600, False),
    ({"budgetSeconds": 900}, 900, 900, True),
])
def test_example_budget_is_measured_and_enforced(tmp_path, monkeypatch, capsys,
                                                declared, elapsed, timeout, passed):
    import shutil
    import subprocess
    from usdaeco_check import example as harness

    example = tmp_path / "examples/demo"
    source = ROOT / "template/examples/datacentre"
    shutil.copytree(source, example,
                    ignore=lambda path, names: ["out"] if Path(path) == source else [])
    manifest = json.loads((example / "manifest.json").read_text())
    manifest.update(declared)
    (example / "manifest.json").write_text(json.dumps(manifest))
    shutil.copytree(example, example / "out")
    (example / "out/findings.json").write_text("[]")
    original_run = subprocess.run

    def run(command, **kwargs):
        if command[-1] == str(example / "run.py"):
            assert kwargs["timeout"] == timeout
            return subprocess.CompletedProcess(command, 0, "", "")
        return original_run(command, **kwargs)

    monkeypatch.setattr(harness.subprocess, "run", run)
    ticks = iter([0, elapsed])
    monkeypatch.setattr(harness.time, "perf_counter", lambda: next(ticks))
    result = check_example(example)
    assert bool(result) == passed, result.detail
    assert f"elapsed {elapsed:.3f}s / budget {timeout}s" in result.detail
    assert f"budget {timeout}s" in capsys.readouterr().out
    if not passed:
        assert "ExampleBudgetExceeded" in result.detail


@pytest.mark.parametrize("budget", [0, -1, 901, True, "600", None, float("inf"), float("nan")])
def test_invalid_example_budget_fails_before_execution(tmp_path, monkeypatch, budget):
    from usdaeco_check import example as harness
    (tmp_path / "manifest.json").write_text(json.dumps({"budgetSeconds": budget}))
    def unexpected(*args, **kwargs):
        pytest.fail("invalid budget must not execute the runner")
    monkeypatch.setattr(harness.subprocess, "run", unexpected)
    result = check_example(tmp_path)
    assert not result and "ExampleBudgetInvalid" in result.detail


def test_example_timeout_reports_measured_budget(tmp_path, monkeypatch):
    import subprocess
    from usdaeco_check import example as harness
    (tmp_path / "manifest.json").write_text('{"budgetSeconds": 0.5}')
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(harness.subprocess, "run", timeout)
    ticks = iter([0, 0.6])
    monkeypatch.setattr(harness.time, "perf_counter", lambda: next(ticks))
    result = check_example(tmp_path)
    assert not result and "ExampleBudgetExceeded" in result.detail
    assert "elapsed 0.600s / budget 0.5s" in result.detail


@pytest.mark.parametrize("actual,expected,match", [
    ([{"x":1}, {"x":2}], [{"x":2}, {"x":1}], True),
    ([{"x":1.0000001}], [{"x":1.0}], True),
    ([{"x":1.1}], [{"x":1.0}], False),
    ([1,1], [1,2], False), ([True], [1], False),
    ([{"x":1}], [{"y":1}], False), ([], [], True),
    ([float("nan")], [float("nan")], False),
])
def test_findings_comparison(actual, expected, match):
    assert (not diff_findings(actual, expected)) == match


def test_tolerance_matching_is_not_greedy():
    assert not diff_findings([1.0, 0.0], [0.0, 2.0], abs_tol=1.1, rel_tol=0)


def test_template_example_composes_overlays_derives_and_matches(tmp_path, monkeypatch):
    repo = new_library("Example", tmp_path / "example")
    example = repo / "examples/datacentre"
    (example / "inputs/drivers.usda").write_text('#usda 1.0\nover "Example"\n{\n    double aeco:example:driver = 3\n}\n')
    before = (example / "manifest.json").read_bytes()
    monkeypatch.delenv("AECO_DATACENTRE_ROOT", raising=False)
    monkeypatch.delenv("AECO_DATACENTRE_STAGE", raising=False)
    monkeypatch.setenv("TOOLCHAIN_DIR", str(ROOT))
    result = check_example(example)
    assert not result and "ResultStale" in result.detail, result.detail
    assert (example / "manifest.json").read_bytes() == before
    from pxr import Usd
    stage = Usd.Stage.Open(str(example / "out/example.usda"))
    assert stage.GetPrimAtPath("/Example").GetAttribute("aeco:example:driver").Get() == 3
    assert stage.GetPrimAtPath("/Example").GetAttribute("aeco:example:derived").Get() == 6
    assert "aeco:example:derived" not in (example / "inputs/drivers.usda").read_text()
    assert not diff_findings(example / "out/findings.json", example / "expected/findings.json")
    print(result.detail)


def test_example_override_and_publish(tmp_path):
    repo = new_library("Example", tmp_path / "repo")
    example = repo / "examples/datacentre"
    stage = repo / "usdAecoExample/examples/minimal.usda"
    declared = json.loads((example / "manifest.json").read_text())
    declared["budgetSeconds"] = 600
    (example / "manifest.json").write_text(json.dumps(declared))
    result = run_python('''
import runpy
sys.argv = [sys.argv[1], "--publish"]
runpy.run_path(sys.argv[0], run_name="__main__")
''', example / "run.py", AECO_DATACENTRE_STAGE=str(stage), TOOLCHAIN_DIR=str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((example / "manifest.json").read_text())
    assert manifest["source"]["mode"] == "override"
    assert manifest["budgetSeconds"] == 600
    assert json.loads((example / "out/manifest.json").read_text())["budgetSeconds"] == 600
    assert str(tmp_path) not in json.dumps(manifest)
    from usdaeco_check.structure import check_structure
    checks = check_structure(repo, only=["S22", "S23"])
    assert all(checks), checks


def test_pinned_source_requires_matching_release(tmp_path, monkeypatch):
    root = tmp_path / "release"
    path = root / "dist/base/dc.usda"
    path.parent.mkdir(parents=True)
    path.write_text('#usda 1.0\n')
    path.with_name("dc.manifest.json").write_text('{"files": []}')
    (root / "library.json").write_text('{"version":"0.4.0"}')
    monkeypatch.delenv("AECO_DATACENTRE_STAGE", raising=False)
    monkeypatch.setenv("AECO_DATACENTRE_ROOT", str(root))
    found, info = _source(tmp_path, None, {"ref":"v0.4.0"}, "base")
    assert found.resolve() == path and info["mode"] == "pinned"
    assert len(info["manifest_sha256"]) == 64
    with pytest.raises(ValueError, match="version"):
        _source(tmp_path, None, {"ref":"v0.5.0"}, "base")


def test_corrupt_outputs_fail_check_example(tmp_path):
    example = tmp_path / "example"
    (example / "expected").mkdir(parents=True)
    (example / "out").mkdir()
    (example / "expected/findings.json").write_text("[]")
    (example / "out/findings.json").write_text('[{"unexpected": true}]')
    assert not check_example(example, execute=False)
