"""Every stable rule has a named, materialized defective repository fixture."""
import json
from pathlib import Path
import shutil
import struct

import pytest

from conftest import ROOT, run_python
from new_library import new_library
from usdaeco_check.contracts import RANGE
from usdaeco_check.plugins import read_json
from usdaeco_check.structure import RULES, check_structure

FIXTURES = ROOT / "tests/fixtures/structure"


def test_documented_rules_match_fixture_inventory():
    import re
    documented = set(re.findall(r"\| (S\d\d) \|", (ROOT / "docs/repo-conventions.md").read_text()))
    assert documented == {f"S{n:02d}" for n in RULES} == {p.name for p in FIXTURES.iterdir()}


def test_generated_template_passes_structure(tmp_path):
    repo = new_library("Example", tmp_path / "repo", kind="usecase")
    results = check_structure(repo)
    assert len(results) == 29
    assert all(results), [(r.name, r.detail) for r in results if not r]


@pytest.mark.parametrize("owner", ["usdaeco", "another-org", "criad-com" + "-extra"])
def test_s05_rejects_other_public_owners(tmp_path, owner):
    repo = new_library("Example", tmp_path / "repo")
    assert all(check_structure(repo, only=["S05"]))
    flake = repo / "flake.nix"
    flake.write_text(flake.read_text().replace("github:criad-com/", f"github:{owner}/"))
    result, = check_structure(repo, only=["S05"])
    assert not result and result.detail == "flake URLs and exact dependency refs differ"


def test_registry_maps_the_public_org_to_public_git_urls():
    entries = read_json(ROOT / "nix/registry.json")["flakes"]
    assert entries
    for entry in entries:
        assert entry["from"]["type"] == "github"
        assert entry["from"]["owner"] == "criad-com"
        assert entry["to"] == {"type": "git", "url": f'https://github.com/criad-com/{entry["from"]["repo"]}.git'}


@pytest.fixture
def repo_with_fixture(tmp_path):
    repo = new_library("Example", tmp_path / "repo")
    path = repo / "dependencies.json"
    document = read_json(path)
    document["fixtures"] = {"legacy-core": read_json(ROOT / "dependencies.json")["fixtures"]["core"]}
    path.write_text(json.dumps(document))
    fixture = document["fixtures"]["legacy-core"]
    flake = repo / "flake.nix"
    flake.write_text(flake.read_text().replace("inputs = {", 'inputs = {\n'
        f'    legacy-core.url = "github:criad-com/{fixture["repo"]}?ref={fixture["ref"]}";'))
    return repo


def test_fixture_pin_is_separate_from_direct_requirements(repo_with_fixture):
    results = check_structure(repo_with_fixture, only=["S04", "S05", "S22"])
    assert all(results), [(r.name, r.detail) for r in results if not r]
    path = repo_with_fixture / "dependencies.json"
    document = read_json(path)
    del document["repos"]["core"]
    path.write_text(json.dumps(document))
    result, = check_structure(repo_with_fixture, only=["S04"])
    assert not result and result.detail == "usdAeco: missing pin"


@pytest.mark.parametrize("change,message", [
    ({"ref": "main"}, "ref must be an exact release tag or full revision"),
    ({"ref": "0123456789abcdef0123456789abcdef01234567"}, "schema revision pins need a version"),
    ({"reason": None}, "legacy-core: fixture needs a nonblank reason"),
    ({"reason": "  "}, "legacy-core: fixture needs a nonblank reason"),
])
def test_fixture_pins_require_exact_refs_and_reasons(repo_with_fixture, change, message):
    path = repo_with_fixture / "dependencies.json"
    document = read_json(path)
    document["fixtures"]["legacy-core"].update(change)
    path.write_text(json.dumps(document))
    result, = check_structure(repo_with_fixture, only=["S04"])
    assert not result and result.detail == message


@pytest.mark.parametrize("fixtures,message", [
    ([], "fixtures must be an object"),
    ({"legacy-core": {"flakeInput": "yes"}}, "legacy-core: flakeInput must be a boolean"),
    ({"core": {"flakeInput": True}}, "fixture input names must be distinct from direct pins"),
])
def test_fixture_declarations_reject_ambiguous_inputs(repo_with_fixture, fixtures, message):
    path = repo_with_fixture / "dependencies.json"
    document = read_json(path)
    document["fixtures"] = fixtures
    path.write_text(json.dumps(document))
    result, = check_structure(repo_with_fixture, only=["S04"])
    assert not result and result.detail == message


def test_fixture_flake_pin_must_match(repo_with_fixture):
    flake = repo_with_fixture / "flake.nix"
    flake.write_text(flake.read_text().replace("?ref=v0.8.4", "?ref=v0.8.3"))
    result, = check_structure(repo_with_fixture, only=["S05"])
    assert not result and result.detail == "flake URLs and exact dependency refs differ"


@pytest.mark.parametrize("evidence", [
    {"repo": "usdaeco-core", "ref": "v0.8.4"},
    {"reason": "Historical acceptance evidence", "repos": {
        "core": {"repo": "usdaeco-core", "ref": "v0.9.1"}}},
    {"repo": "usdaeco-example", "ref": "v0.0.9", "path": "testenv/baseline.json",
     "reason": "Synthetic requirement rejection", "flakeInput": False},
])
def test_historical_fixture_evidence_needs_no_flake_input(repo_with_fixture, evidence):
    path = repo_with_fixture / "dependencies.json"
    document = read_json(path)
    document["fixtures"]["evidence"] = evidence
    path.write_text(json.dumps(document))
    results = check_structure(repo_with_fixture, only=["S04", "S05", "S22"])
    assert all(results), [(r.name, r.detail) for r in results if not r]


@pytest.mark.parametrize("case", read_json(FIXTURES / "S04/names.json"),
                         ids=lambda case: case["repo"])
def test_s04_repository_names(tmp_path, case):
    repo = new_library("Example", tmp_path / "repo", kind="data")
    path = repo / "dependencies.json"
    document = read_json(path)
    document["repos"]["selected-input"] = {"repo": case["repo"], "ref": "v0.1.0"}
    path.write_text(json.dumps(document))
    result, = check_structure(repo, only=["S04"])
    assert result.ok == case["passes"], result.detail
    if not result:
        assert result.detail == (
            f"selected-input: invalid repository name {case['repo']!r}; expected a lowercase "
            "slug [a-z][a-z0-9-]* (including usdaeco-*), usdAeco or usdAeco<X>, "
            "or a declared kit/upstream name: usdSolid, usdSolidOcct, hdOcct, aeco-toolchain, OpenUSD"
        )


@pytest.mark.parametrize("kind", ["usecase", "integration"])
def test_s04_kit_pins_pass_all_rules_without_adapters(tmp_path, kind):
    repo = new_library("Example", tmp_path / "repo", kind=kind)
    path = repo / "dependencies.json"
    document = read_json(path)
    kit_pins = read_json(FIXTURES / "S04/kit-pins.json")
    document["repos"].update(kit_pins)
    path.write_text(json.dumps(document))
    flake = repo / "flake.nix"
    urls = "\n".join(f'    {key}.url = "github:criad-com/{pin["repo"]}?ref={pin["ref"]}";'
                     for key, pin in kit_pins.items())
    flake.write_text(flake.read_text().replace("inputs = {", "inputs = {\n" + urls))
    manifest = repo / "examples" / ("roundtrip" if kind == "integration" else "datacentre") / "manifest.json"
    data = read_json(manifest)
    data["pins"] = document["repos"]
    manifest.write_text(json.dumps(data))
    results = check_structure(repo)
    assert len(results) == 29
    assert all(results), [(r.name, r.detail) for r in results if not r]


@pytest.mark.parametrize("defect,message", [
    ({"ref": "main"}, "ref must be an exact release tag or full revision"),
    ({"ref": "0123456789abcdef0123456789abcdef01234567"}, "schema revision pins need a version"),
    ({"ref": "v0.8.0"}, "usdAeco: pin outside declared range"),
])
def test_s04_kit_names_preserve_pin_checks(tmp_path, defect, message):
    repo = new_library("Example", tmp_path / "repo")
    path = repo / "dependencies.json"
    document = read_json(path)
    document["repos"]["core"].update({"repo": "usdSolid", **defect})
    path.write_text(json.dumps(document))
    result, = check_structure(repo, only=["S04"])
    assert not result and result.detail == message


@pytest.mark.parametrize("rule", sorted(p.name for p in FIXTURES.iterdir()))
def test_seeded_rule_fixture_fails(tmp_path, rule):
    repo = new_library("Example", tmp_path / rule, kind="usecase")
    defect = json.loads((FIXTURES / rule / "defect.json").read_text())
    if "remove" in defect:
        (repo / defect["remove"]).unlink()
    elif "move" in defect:
        (repo / defect["move"][0]).rename(repo / defect["move"][1])
    elif "image" in defect:
        path = repo / "usdAecoExample/userDoc/usdAecoExampleExample.png"
        raw = bytearray(path.read_bytes())
        raw[16:20] = struct.pack(">I", 1601)
        path.write_bytes(raw)
    elif "term" in defect:
        # Construct the private address only in the temporary seeded fixture.
        (repo / "leak.txt").write_text(".".join(map(str, [10, 2, 3, 4])))
    else:
        path = repo / defect["file"]
        text = path.read_text()
        assert defect["before"] in text
        path.write_text(text.replace(defect["before"], defect["after"]))
    result, = check_structure(repo, only=[rule])
    assert result.name == rule and not result, result.detail
    print(f"{rule} seeded fixture FAIL detected: {result.detail}")


@pytest.mark.parametrize("kind", ["library", "integration", "data", "gate", "board"])
def test_kind_rule_sets(tmp_path, kind):
    repo = new_library("Example", tmp_path / kind, kind=kind)
    if kind == "library":
        shutil.rmtree(repo / "examples/datacentre")
        (repo / "docs/usecase.md").unlink()
    results = check_structure(repo)
    assert all(results), [(r.name, r.detail) for r in results if not r]


@pytest.mark.parametrize("value,valid", [(">=0.9,<1.0", True), (">=0.9", True), ("~=0.9.1", True), ("==0.9", False), ("!=0.9", False), ("0.9", False), ("*", False), ("", False)])
def test_version_range_grammar(value, valid):
    assert bool(RANGE.fullmatch(value)) == valid


def test_structure_cli_returns_nonzero(tmp_path):
    repo = new_library("Example", tmp_path / "repo")
    (repo / "LICENSE").unlink()
    result = run_python('from usdaeco_check.cli import main; raise SystemExit(main(["structure", sys.argv[1]]))', repo)
    assert result.returncode == 1 and "S01 FAIL" in result.stdout and "29 checks," in result.stdout


def test_multi_apply_namespace_and_inherited_overrides(tmp_path):
    repo = new_library("Example", tmp_path / "repo")
    schema = repo / "usdAecoExample/schema.usda"
    text = schema.read_text().replace('token apiSchemaType = "singleApply"',
        'token apiSchemaType = "multipleApply"\n        token propertyNamespacePrefix = "aeco:example"')
    text = text.replace('aeco:example:driver', 'driver').replace('aeco:example:derived', 'derived')
    schema.write_text(text)
    assert all(check_structure(repo, only=["S09"]))
    schema.write_text(text.replace('propertyNamespacePrefix = "aeco:example"', 'propertyNamespacePrefix = "other"'))
    assert not all(check_structure(repo, only=["S09"]))


@pytest.mark.parametrize("api_type", ["singleApply", "multipleApply"])
@pytest.mark.parametrize("library,namespace,valid", [
    ("usdAecoBuildUp", "aeco:buildUp", True),
    ("usdAecoCctv", "aeco:cctvCamera", True),
    ("usdAecoCctv", "aeco:cctvSensor", True),
    ("usdAecoPipe", "aeco:pipeType", True),
    ("usdAecoPipe", "aeco:PIPEFitting", True),
    ("usdAecoPipe", "aeco:pipe:detail", True),
    ("usdAecoPipe", "aeco:wall", False),
    ("usdAecoPipe", "aeco:wall:pipe", False),
    ("usdAecoPipe", "aeco:pip", False),
    ("usdAecoPipe", "foreign", False),
    ("usdAecoPipe", "foreign:pipe", False),
    ("usdAecoPipe", "aeco", False),
    ("usdAeco", "aeco", True),
    ("usdAeco", "aeco:anything", True),
    ("usdAeco", "foreign", False),
])
def test_s09_library_namespaces(tmp_path, api_type, library, namespace, valid):
    module = tmp_path / library
    module.mkdir()
    (tmp_path / "library.json").write_text(json.dumps({"name": library, "kind": "library"}))
    multiple = api_type == "multipleApply"
    prefix = f'        token propertyNamespacePrefix = "{namespace}"\n' if multiple else ""
    property_name = "x" if multiple else namespace + ":x"
    (module / "schema.usda").write_text(
        '#usda 1.0\nclass "AecoTestAPI" (\n'
        '    customData = {\n'
        f'        token apiSchemaType = "{api_type}"\n' + prefix +
        '    }\n) {\n'
        f'    double {property_name} = 1\n'
        '}\n')
    result, = check_structure(tmp_path, only=["S09"])
    assert bool(result) == valid, result.detail


@pytest.mark.parametrize("api_type", ["singleApply", "multipleApply"])
@pytest.mark.parametrize("restriction,marker,doc,valid", [
    ('["Imageable"]', None, None, True),
    (None, "unrestricted", "Supports untyped catalog class prims for inherited defaults.", True),
    ("[]", "unrestricted", "Supports untyped catalog class prims for inherited defaults.", True),
    (None, None, "Supports untyped catalog class prims for inherited defaults.", False),
    ("[]", None, "Supports untyped catalog class prims for inherited defaults.", False),
    (None, "unrestricted", None, False),
    (None, "unrestricted", "", False),
    (None, "unrestricted", "   ", False),
    (None, "Unrestricted", "Supports untyped catalog class prims for inherited defaults.", False),
])
def test_s10_explicit_applicability(tmp_path, api_type, restriction, marker, doc, valid):
    module = tmp_path / "usdAecoExample"
    module.mkdir()
    (tmp_path / "library.json").write_text(json.dumps({"name": module.name, "kind": "library"}))
    metadata = [f'        token apiSchemaType = "{api_type}"']
    if restriction is not None:
        metadata.append(f'        token[] apiSchemaCanOnlyApplyTo = {restriction}')
    if marker is not None:
        metadata.append(f'        string aecoApplicability = "{marker}"')
    documentation = f'    doc = "{doc}"\n' if doc is not None else ""
    (module / "schema.usda").write_text(
        '#usda 1.0\nclass "AecoExampleAPI" (\n' + documentation +
        '    customData = {\n' + '\n'.join(metadata) + '\n    }\n) {}\n')
    result, = check_structure(tmp_path, only=["S10"])
    assert bool(result) == valid, result.detail
    if not valid:
        assert 'aecoApplicability = "unrestricted"' in result.detail


@pytest.mark.parametrize("missing", ["marker", "doc"])
def test_s10_unrestricted_declaration_must_be_local(tmp_path, missing):
    module = tmp_path / "usdAecoExample"
    module.mkdir()
    (tmp_path / "library.json").write_text(json.dumps({"name": module.name, "kind": "library"}))
    (module / "base.usda").write_text(
        '#usda 1.0\nclass "AecoExampleBase" (\n'
        '    doc = "Supports untyped catalog class prims for inherited defaults."\n'
        '    customData = {\n'
        '        string aecoApplicability = "unrestricted"\n'
        '    }\n) {}\n')
    metadata = ('    doc = "Supports untyped catalog class prims for inherited defaults."\n'
                if missing == "marker" else '')
    marker = ('        string aecoApplicability = "unrestricted"\n'
              if missing == "doc" else '')
    (module / "schema.usda").write_text(
        '#usda 1.0\n(subLayers = [@base.usda@])\n'
        'class "AecoExampleAPI" (\n'
        '    inherits = </AecoExampleBase>\n' + metadata +
        '    customData = {\n'
        '        token apiSchemaType = "singleApply"\n' + marker +
        '    }\n) {}\n')
    result, = check_structure(tmp_path, only=["S10"])
    assert not result, result.detail


@pytest.mark.parametrize("fixture,valid", [("stock_override", True), ("foreign_property", False)])
def test_s09_builtin_api_fixtures(tmp_path, fixture, valid):
    module = tmp_path / "usdAecoExample"
    module.mkdir()
    (tmp_path / "library.json").write_text(json.dumps({"name": module.name, "kind": "library"}))
    shutil.copyfile(FIXTURES / "S09" / (fixture + ".usda"), module / "schema.usda")
    result, = check_structure(tmp_path, only=["S09"])
    assert bool(result) == valid, result.detail


@pytest.mark.parametrize("base_location", ["same", "sublayer"])
@pytest.mark.parametrize("property_name,valid", [
    ("collection:members:expansionRule", True),
    ("collection:other:expansionRule", False),
    ("foreign:driver", False),
])
def test_s09_inherited_builtin_api(tmp_path, base_location, property_name, valid):
    module = tmp_path / "usdAecoExample"
    module.mkdir()
    (tmp_path / "library.json").write_text(json.dumps({"name": module.name, "kind": "library"}))
    base = 'class "AecoExampleBase" (prepend apiSchemas = ["CollectionAPI:members"]) {}\n'
    header = "#usda 1.0\n"
    if base_location == "sublayer":
        (module / "base.usda").write_text(header + base)
        header += "(subLayers = [@base.usda@])\n"
        base = ""
    (module / "schema.usda").write_text(header + base +
        'class "AecoExampleChild" (inherits = </AecoExampleBase>) {\n' +
        f'    uniform token {property_name} = "explicitOnly"\n' + '}\n')
    result, = check_structure(tmp_path, only=["S09"])
    assert bool(result) == valid, result.detail


def test_structure_rejects_unknown_validator_schema_type(tmp_path):
    repo = new_library("Example", tmp_path / "repo")
    descriptor = repo / "usdAecoExampleValidators/plugInfo.json"
    descriptor.write_text(descriptor.read_text().replace("UsdAecoExampleExampleAPI", "UsdAecoExampleMissingAPI"))
    assert not all(check_structure(repo, only=["S16"]))


@pytest.mark.parametrize("case", json.loads((FIXTURES / "S08/ownership.json").read_text()),
                         ids=lambda case: case["name"])
@pytest.mark.parametrize("multiple", [False, True])
def test_declared_ownership_fixtures(tmp_path, case, multiple):
    repo = new_library("Wall", tmp_path / "repo")
    manifest = repo / "library.json"
    manifest.write_text(json.dumps(json.loads(manifest.read_text()) | case["metadata"]))
    schema = repo / "usdAecoWall/schema.usda"
    declaration = '        token propertyNamespacePrefix = "aeco:OPENINGCut"\n' if multiple else ''
    property_name = "width" if multiple else "aeco:OPENINGCut:width"
    schema.write_text(schema.read_text() +
        '\nclass "AecoOpeningAPI" (\n'
        '    inherits = </APISchemaBase>\n'
        '    customData = {\n'
        '        string className = "OpeningAPI"\n' +
        f'        token apiSchemaType = "{"multipleApply" if multiple else "singleApply"}"\n' +
        declaration + '    }\n) {\n' + f'    double {property_name} = 1\n' + '}\n')
    descriptor = repo / "usdAecoWall/plugInfo.json"
    data = read_json(descriptor)
    data["Plugins"][0]["Info"]["Types"]["UsdAecoWallOpeningAPI"] = {"schemaIdentifier": "AecoOpeningAPI"}
    descriptor.write_text(json.dumps(data))
    results = check_structure(repo, only=["S03", "S08", "S09"])
    assert [r.name for r in results if r] == case["passing"], results
    if "warning" in case:
        assert results[-1].detail == "warning: declared namespaces unused: " + case["warning"]
    elif "S09" in case["passing"]:
        assert "warning" not in results[-1].detail


@pytest.mark.parametrize("field,rule", [("namespaces", "S09"), ("classPrefixes", "S08")])
@pytest.mark.parametrize("value", [[], "wall", None, 7, {}, [""], ["  "], [False], ["wall", 7]])
def test_invalid_ownership_declarations(tmp_path, field, rule, value):
    repo = new_library("Wall", tmp_path / "repo")
    manifest = repo / "library.json"
    manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {field: value}))
    results = check_structure(repo, only=["S03", rule])
    assert all(not result and field in result.detail for result in results)


@pytest.mark.parametrize("field,rule,value", [
    ("namespaces", "S09", ["opening"]),
    ("classPrefixes", "S08", ["AecoOpening"]),
    ("classPrefixes", "S08", ["aecowall"]),
])
def test_explicit_ownership_replaces_defaults(tmp_path, field, rule, value):
    repo = new_library("Wall", tmp_path / "repo")
    manifest = repo / "library.json"
    manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {field: value}))
    result, = check_structure(repo, only=[rule])
    assert not result


def test_reduced_kind_package_has_no_removed_schema_modules(tmp_path):
    import tomllib
    repo = new_library("Dataset", tmp_path / "data", kind="data")
    project = tomllib.loads((repo / "pyproject.toml").read_text())
    assert project["tool"]["setuptools"]["packages"] == ["usdaeco_dataset"]
    assert project["tool"]["setuptools"]["package-dir"] == {"usdaeco_dataset": "tools/usdaeco_dataset"}
    assert "buildCodelessSchema" not in (repo / "flake.nix").read_text()
    assert not (repo / "reduced-flake.nix").exists()


def test_term_sweep_excludes_ignored_notes_but_checks_tracked_files(tmp_path):
    import subprocess
    repo = new_library("Example", tmp_path / "repo")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("local-note.txt\n")
    (repo / "local-note.txt").write_text(".".join(map(str, [10, 2, 3, 4])))
    assert all(check_structure(repo, only=["S25"]))
    subprocess.run(["git", "-C", str(repo), "add", "-f", "local-note.txt"], check=True)
    assert not all(check_structure(repo, only=["S25"]))


@pytest.mark.parametrize("text,allowed", [
    ("criad-com", True),
    ("github:criad-com/usdaeco-core?ref=v0.9.3", True),
    ("https://github.com/criad-com/usdaeco-core", True),
    ("cr" + "iad", False),
    ("criad-com " + "Cr" + "iad", False),
    ("prefix-" + "criad-com", False),
    ("criad-com" + "-extra", False),
    ("criad-com" + ".internal", False),
    ("criad-com" + ".local", False),
])
def test_public_org_slug_has_a_narrow_term_exception(tmp_path, text, allowed):
    from usdaeco_check.publication import text_findings
    repo = new_library("Example", tmp_path / "repo")
    (repo / "public-name.txt").write_text(text)
    result, = check_structure(repo, only=["S25"])
    assert result.ok is allowed, result.detail
    assert bool(text_findings(text, "public-name.txt")) is not allowed


def test_custom_term_patterns_still_check_the_public_org(tmp_path):
    from usdaeco_check.publication import text_findings
    repo = new_library("Example", tmp_path / "repo")
    (repo / "public-name.txt").write_text("criad-com")
    result, = check_structure(repo, only=["S25"], term_patterns=["criad-com"])
    assert not result
    assert text_findings("criad-com", "public-name.txt", patterns=["criad-com"])
