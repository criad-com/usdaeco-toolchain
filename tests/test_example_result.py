"""Publication contracts exercised with USD composition and isolated readers."""
import json
from pathlib import Path
import shutil

import pytest

from conftest import ROOT, run_python
from new_library import new_library
from usdaeco_check.example import check_example, run_example
from usdaeco_check.example_result import (
    LAYER_CAP, RESULT_CAP, file_records, normalized_layer, probe_result,
    record_result, result_files, write_result,
)
from usdaeco_check.structure import check_structure


def prototype_crate(path, *, reverse=False, sizes=(1, 2), nested=True):
    """Seed the numbering/order difference in actual flattened USDC files."""
    from pxr import Sdf
    layer = Sdf.Layer.CreateAnonymous()
    layer.defaultPrim = "World"
    layer.pseudoRoot.SetInfo("metersPerUnit", 1.0)
    layer.pseudoRoot.SetInfo("upAxis", "Z")
    numbers = (7, 2, 1) if reverse else (1, 2, 7)
    paths = [Sdf.Path(f"/Flattened_Prototype_{number}") for number in numbers]
    for index in (reversed(range(3)) if reverse else range(3)):
        prim = Sdf.CreatePrimInLayer(layer, paths[index])
        prim.specifier = Sdf.SpecifierOver
        body = Sdf.PrimSpec(prim, "Body", Sdf.SpecifierDef, "Cube")
        attr = Sdf.AttributeSpec(body, "size", Sdf.ValueTypeNames.Double)
        attr.default = sizes[index] if index < 2 else 0.5
        layer.SetTimeSample(attr.path, 1, attr.default)
        layer.SetTimeSample(attr.path, 2, attr.default + 1)
        Sdf.AttributeSpec(body, "note", Sdf.ValueTypeNames.String).default = "/Flattened_Prototype_1/Body"
        Sdf.RelationshipSpec(body, "self").targetPathList.explicitItems = [paths[index].AppendChild("Body")]
        Sdf.AttributeSpec(body, "input", Sdf.ValueTypeNames.Double).connectionPathList.explicitItems = [attr.path]
        if nested and index < 2:
            Sdf.RelationshipSpec(body, "peer").targetPathList.explicitItems = [paths[1 - index].AppendChild("Body")]
            child = Sdf.PrimSpec(prim, "Nested", Sdf.SpecifierDef, "Xform")
            child.instanceable = True
            child.referenceList.addedItems = [Sdf.Reference("", paths[2])]
    world = Sdf.PrimSpec(layer, "World", Sdf.SpecifierDef, "Xform")
    for index, name in enumerate(("One", "Two", "Three")):
        prim = Sdf.PrimSpec(world, name, Sdf.SpecifierDef, "Xform")
        prim.instanceable = True
        prim.referenceList.addedItems = [Sdf.Reference("", paths[index])]
    assert layer.Export(str(path))
    return path


@pytest.mark.parametrize("sizes,nested", [((1, 2), True), ((1, 1), False)])
def test_prototype_order_normalizes_to_identical_bytes(tmp_path, sizes, nested):
    from pxr import Sdf, Usd
    first = prototype_crate(tmp_path / "first.usdc", sizes=sizes, nested=nested)
    second = prototype_crate(tmp_path / "second.usdc", reverse=True, sizes=sizes, nested=nested)
    before = (first.read_bytes(), second.read_bytes())
    assert before[0] != before[1]
    assert normalized_layer(first, canonical_prototypes=False) != normalized_layer(second, canonical_prototypes=False)
    canonical = normalized_layer(first)
    assert canonical == normalized_layer(second)
    assert (first.read_bytes(), second.read_bytes()) == before
    layer = Sdf.Layer.CreateAnonymous()
    assert layer.ImportFromString(canonical.decode())
    stage = Usd.Stage.Open(layer)
    assert not stage.GetCompositionErrors()
    assert len(layer.rootPrims) == 4  # equal prototypes remain separate
    for name, size in zip(("One", "Two"), sizes):
        body = stage.GetPrimAtPath(f"/World/{name}/Body")
        assert body.GetAttribute("size").Get() == size
        assert body.GetAttribute("size").Get(2) == size + 1
        assert body.GetAttribute("note").Get() == "/Flattened_Prototype_1/Body"
        assert body.GetRelationship("self").GetTargets() == [body.GetPath()]
        assert body.GetAttribute("input").GetConnections() == [body.GetPath().AppendProperty("size")]
    layer.Export(str(tmp_path / "canonical.usdc"))
    assert normalized_layer(tmp_path / "canonical.usdc") == canonical
    changed = prototype_crate(tmp_path / "changed.usdc", reverse=True, sizes=(9, sizes[1]), nested=nested)
    assert normalized_layer(changed) != canonical


def test_normalizer_preserves_ordinary_prims_and_authored_opinions(tmp_path):
    from pxr import Sdf
    layer = Sdf.Layer.CreateAnonymous()
    prim = Sdf.PrimSpec(layer, "Flattened_Prototype_1", Sdf.SpecifierDef, "Xform")
    Sdf.AttributeSpec(prim, "stamp", Sdf.ValueTypeNames.String).default = "issued"
    path = tmp_path / "ordinary.usdc"
    layer.Export(str(path))
    assert normalized_layer(path) == layer.ExportToString().encode()


def test_prototype_comparison_accepts_verified_legacy_hash_and_detects_stale_result(example):
    import hashlib
    from usdaeco_check.example_result import compare_results, validate_result
    crate = example / "result/example.usdc"
    prototype_crate(crate)
    committed = record_result(example / "result")
    legacy = hashlib.sha256(normalized_layer(crate, canonical_prototypes=False)).hexdigest()
    next(item for item in committed["files"] if item["path"].endswith(".usdc"))["normalized_sha256"] = legacy
    shutil.copytree(example / "result", example / "out/result")
    fresh_crate = example / "out/result/example.usdc"
    prototype_crate(fresh_crate, reverse=True)
    fresh = record_result(example / "out/result")
    compare_results(example, committed, fresh)
    prototype_crate(fresh_crate, reverse=True, sizes=(9, 2))
    with pytest.raises(ValueError, match="ResultStale"):
        compare_results(example, committed, record_result(example / "out/result"))
    committed["files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="ResultManifestMismatch"):
        validate_result(example, committed)


@pytest.fixture
def example(tmp_path, monkeypatch):
    repo = new_library("Example", tmp_path / "repo")
    monkeypatch.delenv("AECO_DATACENTRE_ROOT", raising=False)
    monkeypatch.delenv("AECO_DATACENTRE_STAGE", raising=False)
    monkeypatch.setenv("TOOLCHAIN_DIR", str(ROOT))
    return repo / "examples/datacentre"


def publish(example):
    result = run_python('''
import runpy
sys.argv = [sys.argv[1], "--publish"]
runpy.run_path(sys.argv[0], run_name="__main__")
''', example / "run.py", TOOLCHAIN_DIR=str(ROOT))
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads((example / "manifest.json").read_text())


def test_publish_twice_and_check_fresh_run(example):
    first = publish(example)
    authored = {p.relative_to(example / "result"): p.read_bytes()
                for p in (example / "result/layers").rglob("*.usda")}
    flattened = normalized_layer(example / "result/example.usdc")
    second = publish(example)
    assert authored == {p.relative_to(example / "result"): p.read_bytes()
                        for p in (example / "result/layers").rglob("*.usda")}
    assert flattened == normalized_layer(example / "result/example.usdc")
    assert first["result"]["prim_count"] == second["result"]["prim_count"] == 4
    result = check_example(example)
    assert result, result.detail


@pytest.mark.parametrize("target,limit,failure", [
    ("layers/oversized.usda", LAYER_CAP, "ResultLayerSizeExceeded"),
    ("example.usdc", RESULT_CAP, "ResultSizeExceeded"),
])
def test_caps_have_named_failures(example, target, limit, failure):
    with (example / "result" / target).open("wb") as stream:
        stream.truncate(limit + 1)
    with pytest.raises(ValueError, match=failure):
        result_files(example / "result")
    result, = check_structure(example.parents[1], only=["S22"])
    assert not result and failure in result.detail


@pytest.mark.parametrize("stale", ["crate", "layer", "extra"])
def test_stale_result_with_updated_hashes_fails(example, stale):
    publish(example)
    if stale == "crate":
        from pxr import Sdf
        path = example / "result/example.usdc"
        layer = Sdf.Layer.OpenAsAnonymous(str(path))
        layer.GetAttributeAtPath("/Example.aeco:example:derived").default = 999
        layer.Export(str(path))
    elif stale == "layer":
        path = example / "result/layers/out/derived.usda"
        path.write_text(path.read_text().replace("= 4", "= 999"))
    else:
        (example / "result/layers/extra.usda").write_text("#usda 1.0\n")
    manifest = json.loads((example / "manifest.json").read_text())
    manifest["result"] = record_result(example / "result")
    (example / "manifest.json").write_text(json.dumps(manifest))
    result = check_example(example, execute=False)
    assert not result and "ResultStale" in result.detail, result.detail


def test_result_flattens_references_payloads_and_excludes_pinned_layers(example, tmp_path, monkeypatch):
    from pxr import Sdf, Usd
    import usdaeco_render
    release = tmp_path / "release"
    release.mkdir()
    (release / "geometry.usda").write_text('#usda 1.0\ndef Cube "Body" {}\n')
    source = release / "dc.usda"
    source.write_text('''#usda 1.0
(
    defaultPrim = "Facility"
    metersPerUnit = 1
    upAxis = "Z"
    fallbackPrimTypes = { token[] AecoFacility = ["Xform"] }
)
def AecoFacility "Facility" {
    uniform token purpose = "render"
    rel proxyPrim = </Facility/Body>
    def "Body" (references = @geometry.usda@</Body>) {
        uniform token purpose = "proxy"
        color3f[] primvars:displayColor = [(0.15, 0.5, 0.8)]
    }
    def "Payload" (payload = @geometry.usda@</Body>) {
        double3 xformOp:translate = (3, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
''')
    monkeypatch.setenv("AECO_DATACENTRE_STAGE", str(source))
    def render(*args, output, **kwargs):
        Path(output).mkdir()
        return []
    monkeypatch.setattr(usdaeco_render, "render", render)
    def hook(stage, out):
        own = Sdf.Layer.CreateNew(str(out / "study.usda"))
        own.ImportFromString('#usda 1.0\nover "Facility" {\n    double aeco:example:derived = 7\n}\n')
        own.Save()
        stage.GetRootLayer().subLayerPaths.insert(0, "study.usda")
        return []
    manifest = run_example(example, hook, publish=True, keywords=[], size=(640, 400))
    assert len(manifest["source"]["layers"]) == 2
    assert not any("geometry" in p["path"] or "dc.usda" in p["path"] for p in manifest["result"]["files"])
    shutil.rmtree(release)
    shutil.rmtree(example / "inputs")
    shutil.rmtree(example / "out")
    assert probe_result(example / "result/example.usdc")["prim_count"] == 5
    stage = Usd.Stage.Open(str(example / "result/example.usdc"))
    assert stage.GetPrimAtPath("/Facility/Body").GetTypeName() == "Cube"
    assert stage.GetPrimAtPath("/Facility/Payload").GetTypeName() == "Cube"
    assert stage.GetPrimAtPath("/Facility").GetAttribute("aeco:example:derived").Get() == 7
    assert stage.GetPrimAtPath("/Facility/Body").GetAttribute("purpose").Get() == "proxy"
    assert stage.GetPrimAtPath("/Facility").GetRelationship("proxyPrim").GetTargets() == [Sdf.Path("/Facility/Body")]
    assert stage.GetPrimAtPath("/Facility/Body").GetAttribute("primvars:displayColor").Get()[0][1] == 0.5


@pytest.mark.parametrize("change,failure", [
    ("fallback", "missing stock fallback"), ("count", "ResultPrimCountMismatch"),
    ("fallback_array", "missing stock fallback"),
    ("reference", "external asset dependencies"), ("asset", "external asset dependencies"),
    ("default", "defaultPrim required"), ("metrics", "metres and Z-up"),
])
def test_s27_rejects_invalid_result(example, change, failure):
    from pxr import Sdf, Vt
    path = example / "result/example.usdc"
    layer = Sdf.Layer.OpenAsAnonymous(str(path))
    prim = layer.GetPrimAtPath("/Example")
    if change == "fallback":
        prim.typeName = "AecoUnknown"
    elif change == "fallback_array":
        prim.typeName = "AecoUnknown"
        layer.pseudoRoot.SetInfo("fallbackPrimTypes", {"AecoUnknown": Vt.StringArray(["Xform"])})
    elif change == "reference":
        prim.referenceList.prependedItems = [Sdf.Reference("missing.usda")]
    elif change == "asset":
        Sdf.AttributeSpec(prim, "texture", Sdf.ValueTypeNames.Asset).default = Sdf.AssetPath("missing.png")
    elif change == "default":
        layer.ClearDefaultPrim()
    elif change == "metrics":
        layer.pseudoRoot.SetInfo("metersPerUnit", 0.01)
    layer.Export(str(path))
    manifest = json.loads((example / "manifest.json").read_text())
    manifest["result"]["files"] = file_records(example / "result")
    manifest["result"]["bytes"] = sum(i["bytes"] for i in manifest["result"]["files"])
    if change == "count":
        manifest["result"]["prim_count"] += 1
    (example / "manifest.json").write_text(json.dumps(manifest))
    result, = check_structure(example.parents[1], only=["S27"])
    assert not result and failure in result.detail, result.detail


def test_s25_scans_authored_result_out_layers(example):
    path = example / "result/layers/out/derived.usda"
    path.write_text(path.read_text() + "# " + ".".join(map(str, [10, 2, 3, 4])) + "\n")
    result, = check_structure(example.parents[1], only=["S25"])
    assert not result and "result/layers/out/derived.usda" in result.detail


def test_named_starter_result_renames_binary_and_manifest(tmp_path):
    repo = new_library("Renamed", tmp_path / "renamed", kind="integration")
    example = repo / "examples/roundtrip"
    text = normalized_layer(example / "result/example.usdc").decode()
    assert "AecoRenamedAPI" in text and "aeco:renamed:derived" in text
    assert "AecoExample" not in text
    assert all(check_structure(repo, only=["S21", "S22", "S27", "S28"]))


def test_example_results_tracked_while_out_and_nix_result_ignored(example):
    import subprocess
    repo = example.parents[1]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    paths = ["examples/datacentre/result/example.usdc", "examples/datacentre/result/layers/out/derived.usda",
             "examples/datacentre/out/example.usda", "result"]
    result = subprocess.run(["git", "check-ignore", *paths], cwd=repo, text=True, capture_output=True)
    assert result.stdout.splitlines() == paths[2:]


def test_corrupt_crate_has_named_failure(example):
    publish(example)
    (example / "result/example.usdc").write_bytes(b"not a crate")
    result = check_example(example, execute=False)
    assert not result and "ResultInvalid" in result.detail


def test_own_layers_are_included_in_source_package_data():
    import tomllib
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    included = {p for group in project["tool"]["setuptools"]["data-files"].values() for p in group}
    assert {p.relative_to(ROOT).as_posix() for p in (ROOT / "template/examples/datacentre/result").rglob("*")
            if p.is_file()} <= included


def test_fallbacks_include_types_inside_instance_prototypes(example, tmp_path):
    from pxr import Sdf, Usd, Vt
    (example / "out").mkdir()
    asset = Sdf.Layer.CreateNew(str(tmp_path / "asset.usda"))
    asset.ImportFromString('#usda 1.0\ndef Xform "Asset" {\n    def AecoPart "Part" {\n        def Cube "Body" {}\n    }\n}\n')
    asset.Save()
    stage = Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(stage.DefinePrim("/Facility", "Xform"))
    stage.SetMetadata("fallbackPrimTypes", {"AecoPart": Vt.TokenArray(["Xform"])})
    instance = stage.DefinePrim("/Facility/Instance")
    instance.GetReferences().AddReference(asset.identifier, "/Asset")
    instance.SetInstanceable(True)
    assert not any(p.GetTypeName() == "AecoPart" for p in stage.TraverseAll())
    write_result(example, stage, {Path(asset.realPath)}, {"mode": "minimal"}, {"ref": "v0.4.0"}, "base")
    result = Sdf.Layer.OpenAsAnonymous(str(example / "out/result/example.usdc"))
    assert result.pseudoRoot.GetInfo("fallbackPrimTypes")["AecoPart"] == Vt.TokenArray(["Xform"])


def test_vanilla_render_ignores_family_plugin_environment(example, monkeypatch):
    from usdaeco_check.example_result import check_vanilla
    from usdaeco_check.images import image_info
    monkeypatch.setenv("PXR_PLUGINPATH_NAME", str(example.parents[1] / "usdAecoExample"))
    monkeypatch.setenv("PYTHONPATH", str(example.parents[1]))
    manifest = json.loads((example / "manifest.json").read_text())
    assert check_vanilla(example, manifest["result"]) == image_info(example / "result/vanilla.png")


def test_s28_rejects_uniform_committed_vanilla_image(example):
    import numpy as np
    from usdaeco_check.images import write_png
    write_png(example / "result/vanilla.png", np.zeros((8, 8, 3)))
    result, = check_structure(example.parents[1], only=["S28"])
    assert not result and "uniform" in result.detail


def test_s28_renders_committed_geometry_even_with_matching_manifest(example):
    from pxr import Sdf
    path = example / "result/example.usdc"
    layer = Sdf.Layer.OpenAsAnonymous(str(path))
    layer.GetPrimAtPath("/Example").nameChildren.clear()
    layer.Export(str(path))
    manifest = json.loads((example / "manifest.json").read_text())
    manifest["result"] = record_result(example / "result")
    (example / "manifest.json").write_text(json.dumps(manifest))
    result, = check_structure(example.parents[1], only=["S28"])
    assert not result and "ResultVanillaRenderFailed" in result.detail, result.detail
