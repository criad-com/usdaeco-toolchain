from decimal import Decimal
import json
import numpy as np
import pytest

from conftest import ROOT
from usdaeco_check.images import pixels, write_png, image_info
from usdaeco_render import render, frame_range, contact_sheet


@pytest.mark.parametrize("spec, expected", [("1:3:1", [1,2,3]), ("3:1:-1", [3,2,1]), ("0:0.2:0.1", [Decimal("0"),Decimal(".1"),Decimal(".2")])])
def test_frame_ranges(spec, expected):
    assert frame_range(spec) == expected


@pytest.mark.parametrize("spec", ["1:3:0", "3:1:1", "NaN:3:1", "1:500:1", "bad"])
def test_frame_ranges_reject_invalid(spec):
    with pytest.raises(ValueError):
        frame_range(spec)


def test_numpy_png_roundtrip_and_uniform_rejection(tmp_path):
    array = np.zeros((20, 30, 3), dtype=np.uint8)
    array[3:10, 5:12] = [20, 180, 240]
    path = tmp_path / "image.png"
    write_png(path, array)
    np.testing.assert_array_equal(np.rint(pixels(path) * 255).astype(np.uint8), array)
    assert image_info(path)["width"] == 30
    write_png(path, np.zeros_like(array))
    with pytest.raises(ValueError, match="uniform"):
        image_info(path)


def test_embree_still_and_three_frames(tmp_path):
    template = ROOT / "template"
    stage = template / "usdAecoExample/examples/minimal.usda"
    cameras = template / "examples/datacentre/inputs/cameras.usda"
    before = cameras.read_bytes(), stage.read_bytes()
    # Use the real default size so the acceptance cap is measured.
    still = render(stage, cameras=cameras, output=tmp_path / "renders", manifest=tmp_path / "manifest.json")
    assert len(still) == 1 and still[0]["bytes"] <= 400000
    assert (still[0]["width"], still[0]["height"]) == (1280, 800)
    frames = render(stage, cameras=cameras, output=tmp_path / "frames", size=(320,200), frames="1:3:1")
    names = {entry["path"] for entry in frames}
    assert {f"frames/overview.{i}.png" for i in (1,2,3)} <= names
    assert "frames/overview.sheet.png" in names
    assert all(r["width"] <= 1600 and r["height"] <= 1600 and r["bytes"] <= 400000 for r in frames)
    try:
        import PIL
    except ImportError:
        pass
    else:
        assert "frames/overview.gif" in names
        from PIL import Image
        with Image.open(tmp_path / "frames/overview.gif") as gif:
            assert gif.format == "GIF" and gif.n_frames == 3
            print(f"GIF: {gif.width}x{gif.height}, {gif.n_frames} frames, {(tmp_path / 'frames/overview.gif').stat().st_size} bytes; Pillow {PIL.__version__}")
    assert (cameras.read_bytes(), stage.read_bytes()) == before
    assert json.loads((tmp_path / "manifest.json").read_text())["renders"] == still
    print(f"still: {still[0]['width']}x{still[0]['height']}, {still[0]['bytes']} bytes; 3 frames + sheet")


def test_render_rejects_oversize_before_invoking_recorder(tmp_path):
    with pytest.raises(ValueError, match="dimensions"):
        render("missing.usda", size=(1601,800), output=tmp_path)


def test_camera_names_are_required(tmp_path):
    with pytest.raises(ValueError, match="Camera"):
        render(ROOT / "template/usdAecoExample/examples/minimal.usda", output=tmp_path)


def test_guide_only_render_diagnostic_and_opt_in(tmp_path, capsys):
    from pxr import Usd, UsdGeom
    from usdaeco_render.cli import main
    path = tmp_path / "guides.usda"
    stage = Usd.Stage.CreateNew(str(path))
    parent = UsdGeom.Xform.Define(stage, "/Guides")
    parent.CreatePurposeAttr("guide")
    UsdGeom.Cube.Define(stage, "/Guides/Body")
    stage.GetRootLayer().Save()
    args = [str(path), "--cameras", str(ROOT / "template/examples/datacentre/inputs/cameras.usda"),
            "--size", "160x100", "--out", str(tmp_path / "renders"), "--manifest", str(tmp_path / "manifest.json")]
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 1
    message = capsys.readouterr().err
    assert "all gprims have purpose guide" in message
    assert "no proxy/render-purpose geometry; add a proxy body or pass --purposes guide,proxy,render" in message
    assert main(args + ["--purposes", "guide,proxy,render"]) == 0
    assert image_info(tmp_path / "renders/overview.png")["width"] == 160
    # An empty stage still reaches the uniform-pixel guard with a named cause.
    stage.RemovePrim("/Guides")
    stage.GetRootLayer().Save()
    with pytest.raises(SystemExit):
        main(args)
    assert "image has uniform pixels; stage has no gprims; no proxy/render-purpose geometry" in capsys.readouterr().err
