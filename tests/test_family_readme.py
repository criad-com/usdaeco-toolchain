import json
import shutil

import pytest

from conftest import ROOT
from family_readme import collect, fresh_check, main, render
from publish import git


@pytest.fixture
def sources(tmp_path):
    root = tmp_path / "usdaeco-example"
    root.mkdir()
    manifest = {"name": "usdAecoExample", "kind": "usecase", "version": "0.1.0", "requires": {}, "licence": "MIT"}
    (root / "library.json").write_text(json.dumps(manifest))
    (root / "README.md").write_text("# usdAecoExample — demonstrate a source card\n\n## Status\n\nFallback status.\n")
    (root / "docs").mkdir()
    (root / "docs/usecase.md").write_text("## 9 Status\n\nTwo tests passed; runtime NOT RUN.\n")
    shutil.copyfile(ROOT / "LICENSE", root / "LICENSE")
    (root / "examples/datacentre").mkdir(parents=True)
    (root / "examples/datacentre/README.md").write_text("Example\n")
    git("init", "-q", root)
    git("add", ".", cwd=root)
    git("commit", "-qm", "Source card", cwd=root)
    git("tag", "v0.1.0", cwd=root)
    family = {"train": "test-0.1", "repos": [{"name": root.name, "kind": "usecase", "library": "usdAecoExample",
               "tag": "v0.1.0", "requires": {}, "example": None, "enclave": None}]}
    path = tmp_path / "family.json"
    path.write_text(json.dumps(family))
    return path, tmp_path, root


def test_table_and_live_source_freshness(sources, tmp_path):
    family, repos, root = sources
    output = tmp_path / "index/README.md"
    assert main(["--family", str(family), "--repos", str(repos), "--output", str(output)]) == 0
    text = output.read_text()
    assert "MIT" in text and "Two tests passed; runtime NOT RUN." in text
    assert "https://github.com/criad-com/usdaeco-example/tree/v0.1.0/examples/datacentre/README.md" in text
    assert fresh_check(output, family=family, repos=repos)
    # Tagged sources are independent of checkout edits.
    (root / "docs/usecase.md").write_text("Different checkout\n")
    assert fresh_check(output, family=family, repos=repos)
    output.write_text(text.replace("Two tests", "Three tests"))
    assert not fresh_check(output)


def test_updated_train_is_stale(sources, tmp_path):
    family, repos, root = sources
    output = tmp_path / "index/README.md"
    main(["--family", str(family), "--repos", str(repos), "--output", str(output)])
    data = json.loads(family.read_text())
    data["train"] = "test-0.2"
    family.write_text(json.dumps(data))
    assert not fresh_check(output, family=family, repos=repos)
    assert not fresh_check(output, family=family)


def test_untagged_and_private_rows_are_not_releases(sources):
    path, repos, root = sources
    data = json.loads(path.read_text())
    data["repos"][0]["tag"] = None
    data["repos"].append(dict(data["repos"][0], name="usdaeco-meta", kind="meta", library=None))
    path.write_text(json.dumps(data))
    private = repos / "usdaeco-meta"
    private.mkdir()
    (private / "library.json").write_text("Invalid and must never be read")
    result = render(collect(path, repos))
    assert "Unreleased in train (checkout 0.1.0)" in result
    assert "Excluded from public publication" in result
    assert "https://github.com/criad-com/usdaeco-meta" not in result


def test_missing_source_and_mismatched_metadata(sources):
    path, repos, root = sources
    data = json.loads(path.read_text())
    data["repos"][0]["tag"] = None
    path.write_text(json.dumps(data))
    (root / "library.json").unlink()
    assert "NOT RUN: Source card unavailable" in render(collect(path, repos))
    (root / "library.json").write_text(json.dumps({"name": "wrong", "kind": "library"}))
    with pytest.raises(ValueError, match="kind differs"):
        collect(path, repos)
