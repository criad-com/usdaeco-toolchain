"""Portable sources are independent of source and consumer checkout layouts."""
import json
from pathlib import Path
import shutil

import pytest

from usdaeco_check.example import _source
from usdaeco_check.example_paths import archive_source_paths, check_result_paths, relocate_source
from usdaeco_check.structure import check_structure


@pytest.mark.parametrize("asset,valid", [
    ("../../../inputs/source/dist/clash/dc.usda", True),
    ("../inputs/cameras.usda", True),
    ("./peer.usda", True),
    ("../../../../source/dc.usda", False),
    ("../../../out/pinned/source/dc.usda", False),
    ("../../../source/dc.usda", False),
    ("../../../../datacentre/../demo/inputs/dc.usda", False),
    ("/source/dc.usda", False),
    ("C:/source/dc.usda", False),
    ("file:source/dc.usda", False),
    ("release:demo/clash/dc.usda", True),
    ("unknown:demo/clash/dc.usda", False),
])
@pytest.mark.parametrize("field", ["subLayers", "references", "payload", "asset"])
def test_s29_asset_fields(tmp_path, asset, valid, field):
    repo = tmp_path / "repo"
    example = repo / "examples/datacentre"
    layers = example / "result/layers"
    (layers / "out").mkdir(parents=True)
    (layers / "inputs").mkdir()
    (layers / "out/peer.usda").write_text("#usda 1.0\n")
    (layers / "inputs/cameras.usda").write_text("#usda 1.0\n")
    (repo / "library.json").write_text('{"name":"usdaeco-demo","kind":"usecase"}')
    (example / "manifest.json").write_text(json.dumps({"assetResolvers": {
        "release:": "The release resolver maps a release identifier to its pinned published directory."
    }}))
    if field == "subLayers":
        body = f"( subLayers = [@{asset}@] )"
    elif field == "asset":
        body = f'def "A" {{\n asset input.timeSamples = {{ 1: @{asset}@ }}\n}}'
    else:
        body = f'def "A" ( {field} = @{asset}@ ) {{}}'
    (layers / "out/source.usda").write_text("#usda 1.0\n" + body + "\n")
    result, = check_structure(repo, only=["S29"])
    assert result.ok == valid, result.detail
    if not valid:
        assert "ResultSourcePathInvalid" in result.detail


def test_relocation_retargets_only_links_and_refuses_real_inputs(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir(); second.mkdir()
    example = tmp_path / "consumer"
    link = relocate_source(example, first)
    assert relocate_source(example, first) == link
    assert relocate_source(example, second).resolve() == second
    link.unlink()
    link.mkdir()
    (link / "keep").write_text("authored input")
    with pytest.raises(ValueError, match="runtime symlink"):
        relocate_source(example, first)
    assert (link / "keep").read_text() == "authored input"


def test_archive_source_relocation_preserves_opinions_across_two_layouts(tmp_path, monkeypatch):
    from pxr import Sdf, Usd
    archived = []
    for source_name, consumer_name in [("releases/dataset", "repo"), ("deep/dependencies/data", "elsewhere/nested/consumer")]:
        release = tmp_path / source_name
        published = release / "dist/clash"
        published.mkdir(parents=True)
        (published / "dc.usda").write_text('#usda 1.0\n( defaultPrim = "World" )\ndef Xform "World" {}\n')
        (published / "dc.manifest.json").write_text('{}')
        (release / "library.json").write_text('{"version":"0.4.5"}')
        example = tmp_path / consumer_name / "examples/datacentre"
        example.mkdir(parents=True)
        (example / "manifest.json").write_text('{}')
        monkeypatch.setenv("AECO_DATACENTRE_ROOT", str(release))
        monkeypatch.delenv("AECO_DATACENTRE_STAGE", raising=False)
        source, info = _source(example, None, {"ref":"v0.4.5"}, "clash")
        assert source == example / "inputs/source/dist/clash/dc.usda"
        assert info["mode"] == "pinned"
        original = example / "out/driver.usda"
        original.parent.mkdir()
        literal = '@' + str(source.resolve()) + '@'
        before = '#usda 1.0\n( subLayers = [' + literal + '] )\nover "World" {\n double driver = 3\n string note = "' + literal + '"\n}\n# ' + literal + '\n'
        original.write_text(before)
        target = example / "out/result/layers/out/driver.usda"
        target.parent.mkdir(parents=True)
        shutil.copyfile(original, target)
        archive_source_paths(original, target, example)
        assert target.read_text() == before.replace(str(source.resolve()), "../../../inputs/source/dist/clash/dc.usda", 1)
        assert original.read_text() == before
        shutil.copytree(example / "out/result", example / "result")
        check_result_paths(example)
        stage = Usd.Stage.Open(str(example / "result/layers/out/driver.usda"))
        assert not stage.GetCompositionErrors()
        assert stage.GetPrimAtPath("/World").GetAttribute("driver").Get() == 3
        archived.append(target.read_text().replace(str(source.resolve()), "<literal-source>"))
        (example / "inputs/source").unlink()
        check_result_paths(example)  # A clean checkout does not require the link.
    assert archived[0] == archived[1]
