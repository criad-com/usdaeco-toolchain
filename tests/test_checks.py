import json

import pytest

from conftest import make_plugin, run_python
from usdaeco_check import Report, link_check, term_sweep
from usdaeco_check.plugins import check_requirements
from usdaeco_check.report import Result


def test_report_collects_failure_and_continues(capsys):
    report = Report()
    report.check("first", True)
    report.run("broken", lambda: 1 / 0)
    report.check("last", True)
    assert report.finish() == 1
    text = capsys.readouterr().out
    assert "PASS  first" in text and "FAIL  broken" in text and "PASS  last" in text
    assert "3 checks, 1 failed" in text


def test_report_exit_success():
    report = Report()
    report.check("ok", True)
    with pytest.raises(SystemExit) as result:
        report.exit()
    assert result.value.code == 0


def test_report_counts_not_run_separately(capsys):
    report = Report()
    report.check("passed", True)
    assert not report.not_run("unavailable", "prerequisites are offline")
    report.run("deferred", lambda: Result("probe", None, "build unavailable"))
    assert not report.results[-1]
    assert report.finish() == 0
    report.check("broken", False)
    assert report.finish() == 1
    assert report.failed == 1 and report.not_run_count == 2
    output = capsys.readouterr().out
    assert "NOT RUN  unavailable  — prerequisites are offline" in output
    assert "3 checks, 0 failed, 2 not run" in output
    assert "4 checks, 1 failed, 2 not run" in output


def test_report_not_run_requires_cause():
    with pytest.raises(ValueError, match="requires a cause"):
        Report().not_run("unknown", " ")


def test_link_check_handles_files_references_and_code(tmp_path):
    (tmp_path / "with space.txt").touch()
    doc = tmp_path / "README.md"
    doc.write_text('[inline](<with space.txt>)\n[ref][target]\n[target]: with%20space.txt\n'
                   '[external](https://example.invalid/)\n[anchor](#section)\n'
                   '```md\n[code](absent.md)\n```\n')
    result = link_check(tmp_path)
    assert result, result.detail
    doc.write_text(doc.read_text() + '\n[missing](missing.md)\n')
    assert not link_check(tmp_path)


def test_term_sweep_reports_locations_without_content(tmp_path):
    (tmp_path / "binary").write_bytes(b"\xff\xfe")
    (tmp_path / "notes.txt").write_text("ordinary\nFORBIDDEN_VALUE\n")
    result = term_sweep([tmp_path], [r"forbidden_\w+"])
    assert not result and "notes.txt:2" in result.detail
    assert "FORBIDDEN_VALUE" not in result.detail
    assert term_sweep(tmp_path, [r"another_token"])


@pytest.mark.parametrize("version,expected", [("0.6.9", False), ("0.7", True), ("0.7.0", True), ("0.10.0", True)])
def test_plugin_requires_version_comparison(tmp_path, version, expected):
    core = make_plugin(tmp_path / "core", "usdAeco", version, tier="core")
    library = make_plugin(tmp_path / "kind", "usdAecoTest", requires={"usdAeco": ">=0.7"})
    result = run_python('''
from usdaeco_check import plugin_requires
r = plugin_requires(sys.argv[1:])
print(r.detail)
raise SystemExit(0 if r else 1)
''', core, library)
    assert (result.returncode == 0) == expected, result.stdout + result.stderr
    if not expected:
        assert "requires usdAeco >=0.7: found 0.6.9" in result.stdout


def test_plugin_requires_rejects_absent_core(tmp_path):
    library = make_plugin(tmp_path / "kind", "usdAecoTest", requires={"usdAeco": ">=0.7"})
    result = run_python('''
from usdaeco_check import plugin_requires
r = plugin_requires(sys.argv[1]); print(r.detail)
assert not r and "plugin absent" in r.detail
''', library)
    assert result.returncode == 0, result.stdout + result.stderr


def test_plugin_requires_checks_every_registered_plugin(tmp_path):
    core = make_plugin(tmp_path / "core", "usdAeco", "0.7", tier="core")
    library = make_plugin(tmp_path / "kind", "usdAecoTest", requires={"usdAecoMissing": ">=1"})
    result = run_python('''
from usdaeco_check import plugin_requires
r = plugin_requires(sys.argv[1]); print(r.detail)
assert not r and "usdAecoMissing" in r.detail
''', core, plugins=[library])
    assert result.returncode == 0, result.stdout + result.stderr


def test_plugin_requires_rejects_missing_metadata(tmp_path):
    core = make_plugin(tmp_path / "core", "usdAeco", "0.7", tier="core")
    descriptor = core / "plugInfo.json"
    data = json.loads(descriptor.read_text())
    data["Plugins"][0]["Info"] = {}
    descriptor.write_text(json.dumps(data))
    result = run_python('''
from usdaeco_check import plugin_requires
r = plugin_requires(sys.argv[1]); print(r.detail)
assert not r and "Info.aeco" in r.detail
''', core)
    assert result.returncode == 0, result.stdout + result.stderr
    result = run_python('''
from usdaeco_check import plugin_requires
r = plugin_requires(); print(r.detail)
assert not r and "Info.aeco" in r.detail
''', plugins=[core])
    assert result.returncode == 0, result.stdout + result.stderr


def test_plugin_requires_rejects_nonexistent_directory(tmp_path):
    result = run_python('''
from usdaeco_check import plugin_requires
assert not plugin_requires(sys.argv[1])
''', tmp_path / "missing")
    assert result.returncode == 0, result.stdout + result.stderr


def test_dependency_cycles_are_rejected():
    with pytest.raises(ValueError, match="cycle"):
        check_requirements({
            "one": {"version": "1", "tier": "kind", "requires": {"two": ">=1"}},
            "two": {"version": "1", "tier": "kind", "requires": {"one": ">=1"}}})


def test_invalid_version_constraint_is_rejected():
    with pytest.raises(ValueError):
        check_requirements({"one": {"version": "1", "tier": "kind", "requires": {"two": "banana"}}})


def test_example_validation_rejects_empty_directory(tmp_path):
    result = run_python('''
from usdaeco_check import validate_examples
r = validate_examples(sys.argv[1], []); print(r.detail)
assert not r and "no USD examples" in r.detail
''', tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_example_validation_rejects_broken_composition(tmp_path):
    (tmp_path / "bad.usda").write_text('#usda 1.0\n(subLayers = [@missing.usda@])\n')
    result = run_python('''
from usdaeco_check import validate_examples
r = validate_examples(sys.argv[1], []); print(r.detail)
assert not r and "missing.usda" in r.detail
''', tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_example_validation_expected_errors_and_callbacks(tmp_path):
    (tmp_path / "example.usda").write_text('#usda 1.0\n(defaultPrim = "Example")\ndef Xform "Example" {}\n')
    result = run_python('''
from pxr import UsdValidation
from usdaeco_check import validate_examples
def validator(stage):
    return [UsdValidation.ValidationError("seeded", UsdValidation.ValidationErrorType.Error,
            [UsdValidation.ValidationErrorSite(stage, "/Example")], "seeded error")]
assert validate_examples(sys.argv[1], [], expect_errors=1, validators=[validator])
assert not validate_examples(sys.argv[1], [], validators=[validator])
''', tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_registry_and_can_apply_primitives():
    result = run_python('''
from usdaeco_check import registry_probe, can_apply
assert registry_probe(["CollectionAPI"], ["Xform"])
assert not registry_probe(["MissingAPI"], ["MissingType"])
assert can_apply([("Xform", "CollectionAPI", True, "members")])
assert not can_apply([("Xform", "CollectionAPI", False, "members")])
assert not can_apply([("Xform", "MissingAPI", False)])
''')
    assert result.returncode == 0, result.stdout + result.stderr
