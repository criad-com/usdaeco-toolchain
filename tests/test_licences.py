"""Root licence agreement, complete terms and per-directory disclosures."""
import json

import pytest

from conftest import ROOT
from new_library import new_library
from usdaeco_check.licences import detect_licence
from usdaeco_check.structure import check_structure

TEXTS = ROOT / "tools/usdaeco_check/licences"
CASES = json.loads((ROOT / "tests/fixtures/structure/S01/licences.json").read_text())


@pytest.fixture
def repo(tmp_path):
    return new_library("Example", tmp_path / "repo", kind="data")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_s01_licence_fixtures(repo, case):
    manifest = repo / "library.json"
    data = json.loads(manifest.read_text())
    data.pop("licence")
    if "declared" in case:
        data["licence"] = case["declared"]
    manifest.write_text(json.dumps(data))
    licence = repo / "LICENSE"
    if case["text"]:
        licence.write_text((TEXTS / (case["text"] + ".txt")).read_text())
    else:
        licence.unlink()
    (repo / "README.md").write_text("## Licence\n\n[" + case["readme"] + "](LICENSE).\n\n"
                                  "Dependencies: MIT, Apache-2.0, BSD-3-Clause.\n")
    result, = check_structure(repo, only=["S01"])
    assert result.ok == case["passes"], result.detail
    if case["passes"]:
        assert case["text"] in result.detail
        assert ("declared" if "declared" in case else "inferred") in result.detail


@pytest.mark.parametrize("name", ["MIT", "Apache-2.0", "BSD-3-Clause"])
def test_complete_terms_required(name):
    text = (TEXTS / (name + ".txt")).read_text()
    assert detect_licence(text) == name
    assert detect_licence("  ".join(text.lower().split())) == name
    assert detect_licence(name) is None
    assert detect_licence(text[:len(text) // 2]) is None
    assert detect_licence(text.replace("MERCHANTABILITY", "")) is None
    assert detect_licence(text.replace("permission", "prohibition")) is None


def test_bsd_bullets_and_named_holder():
    text = (TEXTS / "BSD-3-Clause.txt").read_text()
    for n in range(1, 4):
        text = text.replace(f"{n}. ", "* ")
    text = text.replace("the name of the copyright holder", "the name of Example Foundation")
    assert detect_licence(text) == "BSD-3-Clause"


def test_additional_licences_informational_and_documented(repo):
    paths = ["blender/LICENSE", "scripts/nested/LICENCE.md"]
    for name in paths:
        path = repo / name
        path.parent.mkdir(parents=True)
        # S01 does not apply the root allowlist or text completeness to these.
        path.write_text("GPL-3.0; separate terms\n")
    result, = check_structure(repo, only=["S01"])
    assert not result and "README Licence must mention" in result.detail
    readme = repo / "README.md"
    readme.write_text(readme.read_text() + "\nAdditional GPL-3.0 terms: " + ", ".join(paths))
    result, = check_structure(repo, only=["S01"])
    assert result and "INFO" in result.detail
    assert all(name in result.detail for name in paths)


def test_additional_notice_must_be_in_licence_section(repo):
    path = repo / "blender/LICENSE"
    path.parent.mkdir()
    path.write_text("GPL-3.0")
    readme = repo / "README.md"
    readme.write_text("blender/LICENSE uses GPL-3.0\n\n" + readme.read_text())
    result, = check_structure(repo, only=["S01"])
    assert not result


def test_transient_licences_are_not_disclosures(repo):
    for name in ("out/LICENSE", "build/LICENSE"):
        path = repo / name
        path.parent.mkdir()
        path.write_text("Separate terms")
    result, = check_structure(repo, only=["S01"])
    assert result and "INFO" not in result.detail


@pytest.mark.parametrize("kind", ["usecase", "library", "integration", "data", "gate", "board"])
def test_all_starters_declare_mit(tmp_path, kind):
    repo = new_library("Example", tmp_path / kind, kind=kind)
    assert json.loads((repo / "library.json").read_text())["licence"] == "MIT"
    assert (repo / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert all(check_structure(repo, only=["S01", "S25"]))


def test_copyright_exception_is_exact_and_licence_only(repo):
    notice = (ROOT / "LICENSE").read_text().splitlines()[2]
    assert all(check_structure(repo, only=["S25"]))
    path = repo / "notice.txt"
    path.write_text(notice)
    assert not all(check_structure(repo, only=["S25"]))
    path.unlink()
    licence = repo / "LICENSE"
    licence.write_text(licence.read_text() + notice + " extra\n")
    assert not all(check_structure(repo, only=["S25"]))
    licence.write_bytes((ROOT / "LICENSE").read_bytes())
    assert not all(check_structure(repo, only=["S25"], term_patterns=["Copyright"]))


def test_holder_in_docstring_fails(repo):
    holder = (ROOT / "LICENSE").read_text().splitlines()[2].split()[-1]
    (repo / "example.py").write_text('"""' + holder + ' documentation."""\n')
    result, = check_structure(repo, only=["S25"])
    assert not result and "example.py:1" in result.detail


def test_readme_licence_holder_exception_preserves_other_checks(repo):
    notice = (ROOT / "LICENSE").read_text().splitlines()[2]
    readme = repo / "README.md"
    original = readme.read_text()
    readme.write_text(original + "\n" + notice + "\n")
    assert all(check_structure(repo, only=["S25"]))
    readme.write_text(original + "\n" + notice + "\n" + ".".join(map(str, [10, 2, 3, 4])))
    assert not all(check_structure(repo, only=["S25"]))
    readme.write_text(original + "\n## Other section\n\n" + notice)
    assert not all(check_structure(repo, only=["S25"]))
    readme.write_text(notice + "\n\n" + original)
    assert not all(check_structure(repo, only=["S25"]))


def test_manifest_copyright_only(repo):
    notice = (ROOT / "LICENSE").read_text().splitlines()[2]
    path = repo / "library.json"
    data = json.loads(path.read_text())
    data["copyright"] = notice
    path.write_text(json.dumps(data))
    assert all(check_structure(repo, only=["S25"]))
    data["description"] = notice
    path.write_text(json.dumps(data))
    assert not all(check_structure(repo, only=["S25"]))
