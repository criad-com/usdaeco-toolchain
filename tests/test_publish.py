import json
from pathlib import Path

import pytest

from conftest import ROOT
from publish import git, main, prepare
from usdaeco_check.publication import inspect_tree, text_findings


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "library.json").write_text(json.dumps({"name": "usdaeco-example", "version": "0.1.0", "kind": "library", "licence": "MIT"}))
    (root / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
    (root / "README.md").write_text("# usdaeco-example — fixture\n\n## Licence\n\nMIT.\n")
    git("init", "-q", "--initial-branch=main", root)
    git("add", ".", cwd=root)
    git("commit", "-qm", "Initial fixture", cwd=root)
    return root


def tag(source):
    git("add", "--force", "--all", cwd=source)
    git("commit", "--allow-empty", "-qm", "Release fixture", cwd=source)
    git("tag", "v0.1.0", cwd=source)


def test_report_is_deterministic_orphan_of_tag(source, tmp_path):
    (source / "run.sh").write_text("#!/bin/sh\nexit 0\n")
    (source / "run.sh").chmod(0o755)
    (source / "alias").symlink_to("README.md")
    (source / "dist").mkdir()
    (source / "dist/data.txt").write_text("published data\n")
    (source / "data-alias").symlink_to("dist", target_is_directory=True)
    (source / ".gitignore").write_text("dist/\n")
    (source / "STEERING.md").write_text("Local operational notes\n")
    tag(source)
    # Neither dirty source content nor the source history is published.
    (source / "README.md").write_text("Uncommitted change\n")
    results = [prepare(str(source), "v0.1.0", tmp_path / name) for name in ("first", "second")]
    assert results[0] == results[1]
    report = results[0]
    assert report["ok"] and not report["pushed"] and report["commit_count"] == 1
    tree = tmp_path / "first/tree"
    assert git("rev-list", "--parents", "HEAD", cwd=tree).decode().split() == [report["orphan_commit"]]
    assert git("remote", cwd=tree) == b""
    assert (tree / "dist/data.txt").is_file()
    assert not (tree / "STEERING.md").exists()
    assert (tree / "run.sh").stat().st_mode & 0o111
    assert (tree / "alias").is_symlink()
    assert (tree / "data-alias/data.txt").read_text() == "published data\n"
    assert len(report["licences"]) == 1
    assert b"Uncommitted" not in (tree / "README.md").read_bytes()
    assert b"dist/data.txt" in git("ls-files", cwd=tree)
    assert not git("status", "--porcelain", cwd=tree)
    assert report["public_url"] == "https://github.com/criad-com/usdaeco-example"
    assert "| usdaeco-example | https://github.com/criad-com/usdaeco-example |" in (tmp_path / "first/report.md").read_text()


@pytest.mark.parametrize("library,repository", [
    ("usdAeco", "usdaeco-core"), ("usdAecoAxis", "usdaeco-axis"), ("usdAecoCctv", "usdaeco-cctv"),
])
def test_schema_public_url_uses_repository_name(source, tmp_path, library, repository):
    metadata = source / "library.json"
    metadata.write_text(json.dumps(json.loads(metadata.read_text()) | {"name": library}))
    tag(source)
    report = prepare(str(source), "v0.1.0", tmp_path / "report")
    assert report["ok"] and not report["pushed"]
    assert report["public_url"] == "https://github.com/criad-com/" + repository


@pytest.mark.parametrize("defect", ["text", "path", "dist", "crate", "image", "symlink", "cycle", "archive", "gzip", "licence", "custom"])
def test_seeded_defects_block_orphan_and_push(source, tmp_path, defect):
    private = ".".join(map(str, (10, 23, 45, 67)))
    patterns = []
    if defect in {"text", "dist", "custom"}:
        file = source / ("dist/data.txt" if defect == "dist" else "private.txt")
        file.parent.mkdir(exist_ok=True)
        file.write_text(private if defect != "custom" else "customer-code")
        patterns = ["customer-code"] if defect == "custom" else []
    elif defect == "path":
        (source / private).write_text("otherwise harmless")
    elif defect == "crate":
        from pxr import Sdf
        layer = Sdf.Layer.CreateNew(str(source / "model.usdc"))
        layer.customLayerData = {"private": private}
        layer.Save()
    elif defect == "symlink":
        (source / "unsafe").symlink_to(tmp_path / "secret")
    elif defect == "cycle":
        (source / "unsafe").symlink_to("unsafe")
    elif defect == "archive":
        (source / "archive.zip").write_bytes(b"PK\x03\x04payload")
    elif defect == "gzip":
        import gzip
        (source / "archive.gz").write_bytes(gzip.compress(private.encode()))
    elif defect == "image":
        from PIL import Image, PngImagePlugin
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("description", private, zip=True)
        Image.new("RGB", (2, 2)).save(source / "image.png", pnginfo=metadata)
    elif defect == "licence":
        (source / "LICENSE").write_text("MIT\n")
    tag(source)
    output = tmp_path / "output"
    remote = tmp_path / "remote.git"
    git("init", "--bare", "-q", remote)
    report = prepare(str(source), "v0.1.0", output, push=True, remote=str(remote), patterns=patterns)
    assert not report["ok"] and not report["pushed"]
    assert not (output / "tree/.git").exists()
    assert git("for-each-ref", cwd=remote) == b""
    assert private not in (output / "report.json").read_text()
    assert private not in (output / "report.md").read_text()


def test_explicit_push_to_fixture_remote_and_no_force(source, tmp_path):
    tag(source)
    remote = tmp_path / "remote.git"
    git("init", "--bare", "-q", remote)
    report = prepare(str(source), "v0.1.0", tmp_path / "published", push=True, remote=str(remote))
    assert report["pushed"]
    assert git("rev-parse", "refs/heads/main", cwd=remote).decode().strip() == report["orphan_commit"]
    assert git("rev-parse", "refs/tags/v0.1.0^{commit}", cwd=remote).decode().strip() == report["orphan_commit"]
    # An unrelated release cannot replace a public branch or tag.
    (source / "file").write_text("change\n")
    metadata = json.loads((source / "library.json").read_text())
    metadata["version"] = "0.2.0"
    (source / "library.json").write_text(json.dumps(metadata))
    git("add", ".", cwd=source)
    git("commit", "-qm", "Another release", cwd=source)
    git("tag", "v0.2.0", cwd=source)
    with pytest.raises(ValueError, match="git push failed"):
        prepare(str(source), "v0.2.0", tmp_path / "rejected", push=True, remote=str(remote))
    assert git("tag", "--list", cwd=remote).decode().split() == ["v0.1.0"]


def test_documented_report_cli_and_exclusive_push(source, tmp_path):
    tag(source)
    arguments = [str(source), "--tag", "v0.1.0", "--output", str(tmp_path / "cli")]
    assert main([*arguments, "--report"]) == 0
    report = json.loads((tmp_path / "cli/report.json").read_text())
    assert report["ok"] and report["mode"] == "report" and not report["pushed"]
    with pytest.raises(SystemExit) as result:
        main([*arguments, "--report", "--push", "--remote", "unused"])
    assert result.value.code == 2


@pytest.mark.parametrize("arguments", [dict(push=True), dict(remote="unused")])
def test_remote_and_push_must_be_explicit(source, tmp_path, arguments):
    with pytest.raises(ValueError, match="requires"):
        prepare(str(source), "v0.1.0", tmp_path / "output", **arguments)
    assert not (tmp_path / "output").exists()


def test_ref_version_output_and_private_repository_refusals(source, tmp_path):
    tag(source)
    with pytest.raises(ValueError, match="exact version tag"):
        prepare(str(source), "main", tmp_path / "bad")
    with pytest.raises(ValueError, match="new directory"):
        prepare(str(source), "v0.1.0", source)
    with pytest.raises(ValueError, match="outside"):
        prepare(str(source), "v0.1.0", source / "new")
    assert main([str(source), "--tag", "v9.9.9", "--output", str(tmp_path / "missing")]) == 1
    manifest = json.loads((source / "library.json").read_text())
    manifest["kind"] = "meta"
    manifest["version"] = "0.2.0"
    (source / "library.json").write_text(json.dumps(manifest))
    git("add", ".", cwd=source)
    git("commit", "-qm", "Private fixture", cwd=source)
    git("tag", "v0.2.0", cwd=source)
    with pytest.raises(ValueError, match="private metadata"):
        prepare(str(source), "v0.2.0", tmp_path / "private")


def test_size_limits_and_source_licence_unchanged(source):
    original = (source / "LICENSE").read_bytes()
    report = inspect_tree(source, max_file=10, max_tree=20)
    assert {r["rule"] for r in report["sweep"]["findings"]} >= {"FileSizeExceeded", "TreeSizeExceeded"}
    assert (source / "LICENSE").read_bytes() == original


@pytest.mark.parametrize("text", ["example" + ".lan", "build" + ".internal", "https://" + "service/path",
                                "https://" + "criad-com" + "/path",
                                "/" + "Users" + "/example/file", ":".join(["ab"] * 6)])
def test_host_and_path_patterns(text):
    assert text_findings(text, "fixture.txt")


def test_public_urls_and_native_paths_are_allowed():
    assert not text_findings("https://github.com/criad-com/example /usr/bin/env /nix/store/package", "fixture.txt")
    assert not text_findings("http://localhost:8858/healthz", "fixture.txt")
