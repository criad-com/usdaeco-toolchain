import copy
import json
import os
import pytest
from conftest import ROOT, run_python
from usdaeco_check.family import validate_family


@pytest.fixture
def family():
    return json.loads((ROOT / "tests/fixtures/family.json").read_text())


@pytest.mark.parametrize("case", json.loads((ROOT / "tests/fixtures/structure/S04/names.json").read_text()),
                         ids=lambda case: case["repo"])
def test_family_uses_s04_repository_names(family, case):
    family["repos"] = [family["repos"][0]]
    family["repos"][0]["name"] = case["repo"]
    result = validate_family(family)
    assert result.ok == case["passes"], result.detail
    if not result:
        assert f"repos[0].name: invalid repository name {case['repo']!r}" in result.detail
        assert "usdAeco<X>" in result.detail and "OpenUSD" in result.detail


@pytest.mark.parametrize("defect", [None, "missing", "cycle", "range"])
def test_family_kit_library_dependencies(family, defect):
    core = family["repos"][0]
    solid = dict(core, name="usdSolid", library="usdSolid", tag="v0.1.0")
    occt = dict(core, name="usdSolidOcct", library=None, tag="v0.1.0",
                requires={"usdSolid": ">=0.1,<0.2"})
    family["repos"] = [solid, occt]
    if defect == "missing":
        family["repos"] = [occt]
    elif defect == "cycle":
        solid["requires"] = {"usdSolidOcct": ">=0.1,<0.2"}
    elif defect == "range":
        occt["requires"] = {"usdSolid": ">=0.2,<0.3"}
    result = validate_family(family)
    assert result.ok == (defect is None), result.detail


def test_released_family_validates(family):
    result = validate_family(family, sibling_root=os.environ.get("AECO_FAMILY_SIBLINGS") or None, inventory=True)
    assert result, result.detail
    assert "1 unreleased seeds; 4 incompatible requirements" in result.detail
    print(result.detail)


@pytest.mark.parametrize("defect", ["train", "duplicate", "library", "tag", "range", "missing", "cycle", "example", "enclave", "kind"])
def test_family_rejects_defects(family, defect):
    first = family["repos"][0]
    if defect == "train": family["train"] = ""
    elif defect == "duplicate": family["repos"].append(copy.deepcopy(first))
    elif defect == "library": family["repos"][1]["library"] = "usdAeco"
    elif defect == "tag": first["tag"] = "main"
    elif defect == "range": family["repos"][2]["requires"]["usdAeco"] = "==0.8.4"
    elif defect == "missing": family["repos"][2]["requires"]["Missing"] = ">=1.0"
    elif defect == "cycle": first["requires"]["usdAecoBuildUp"] = ">=0.1"
    elif defect == "example": first["example"] = {"datacentre":"v9.0.0", "variant":"base"}
    elif defect == "enclave": first["enclave"] = "../escape"
    elif defect == "kind": first["kind"] = "unknown"
    assert not validate_family(family, inventory=True)


def test_family_checks_sibling_manifest(family, tmp_path):
    core = tmp_path / "usdaeco-core"
    core.mkdir()
    metadata = {"name":"usdAeco","kind":"library","version":"0.9.1","requires":{}}
    (core / "library.json").write_text(json.dumps(metadata))
    assert validate_family(family, sibling_root=tmp_path, inventory=True)
    metadata["version"] = "0.8.3"
    (core / "library.json").write_text(json.dumps(metadata))
    assert not validate_family(family, sibling_root=tmp_path, inventory=True)


def test_family_cli():
    result = run_python('from usdaeco_check.cli import main; raise SystemExit(main(["family", "tests/fixtures/family.json", "--inventory"]))', AECO_FAMILY_SIBLINGS="")
    assert result.returncode == 0 and "16 repositories" in result.stdout, result.stdout + result.stderr
    assert "sibling comparison not requested" in result.stdout


def test_inventory_does_not_claim_a_compatible_train(family):
    result = validate_family(family)
    assert not result and "4 incompatible requirements" in result.detail
    family["repos"] = [repo for repo in family["repos"] if repo["name"] in ("usdaeco-core", "usdaeco-axis")]
    assert validate_family(family)
    family["repos"][0]["tag"] = "v0.8.4"
    assert not validate_family(family)


def test_family_cli_uses_explicit_sibling_root(tmp_path):
    core = tmp_path / "usdaeco-core"
    core.mkdir()
    (core / "library.json").write_text(json.dumps({"name": "usdAeco", "version": "0.8.4"}))
    result = run_python('from usdaeco_check.cli import main; raise SystemExit(main(["family", "tests/fixtures/family.json", "--inventory"]))', AECO_FAMILY_SIBLINGS=str(tmp_path))
    assert result.returncode == 1 and "version differs from tag" in result.stdout


@pytest.mark.parametrize("defect", [None, "missing", "cycle", "range"])
def test_family_schema_free_dependencies(family, defect):
    family["repos"] = [repo for repo in family["repos"]
                       if repo["name"] in ("usdaeco-datacentre", "usdaeco-revit")]
    data, integration = sorted(family["repos"], key=lambda repo: repo["name"])
    integration["requires"] = {}
    if defect == "missing":
        data["requires"] = {"usdaeco-missing": ">=0.1,<0.2"}
    elif defect == "cycle":
        integration["requires"] = {data["name"]: ">=0.4,<0.5"}
    elif defect == "range":
        data["requires"][integration["name"]] = ">=0.2,<0.3"
    result = validate_family(family)
    assert bool(result) == (defect is None), result.detail
