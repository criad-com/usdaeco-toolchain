"""CPU rendering of named USD cameras with bounded, measured image artifacts."""
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from usdaeco_check.images import pixels, write_png, image_info


def frame_range(spec):
    """Inclusive start:end:step, preserving exact decimal frame names."""
    try:
        start, end, step = map(Decimal, spec.split(":"))
    except (ValueError, InvalidOperation):
        raise ValueError("frames must be start:end:step") from None
    if not all(v.is_finite() for v in (start, end, step)) or step == 0 or (end - start) * step < 0:
        raise ValueError("invalid frame range direction or step")
    count = int((end - start) / step) + 1
    if count > 240:
        raise ValueError("frame range exceeds 240 frames")
    return [start + step * i for i in range(count)]


def frame_name(frame):
    return format(frame, "f").rstrip("0").rstrip(".") if "." in format(frame, "f") else str(frame)


def _resize(array, width, height):
    rows = np.linspace(0, array.shape[0] - 1, height).astype(int)
    cols = np.linspace(0, array.shape[1] - 1, width).astype(int)
    return array[rows[:, None], cols]


def contact_sheet(paths, output, size):
    columns = math.ceil(math.sqrt(len(paths)))
    rows = math.ceil(len(paths) / columns)
    width, height = size
    cell_width, cell_height = max(1, width // columns), max(1, height // rows)
    arrays = [pixels(p) for p in paths]
    sheet = np.zeros((rows * cell_height, columns * cell_width, 3))
    for i, array in enumerate(arrays):
        # Fit without changing the camera aspect ratio; letterbox when needed.
        scale = min(cell_width / array.shape[1], cell_height / array.shape[0])
        w, h = max(1, round(array.shape[1] * scale)), max(1, round(array.shape[0] * scale))
        x = (i % columns) * cell_width + (cell_width - w) // 2
        y = (i // columns) * cell_height + (cell_height - h) // 2
        sheet[y:y + h, x:x + w] = _resize(array, w, h)
    write_png(output, sheet)
    image_info(output)


def _gif(paths, output):
    try:
        from PIL import Image
    except ImportError:
        return False
    # A bounded preview avoids exceeding the same cap as stills and sheets.
    for width in (640, 480, 320, 160):
        frames = []
        for path in paths:
            array = pixels(path)
            w = min(width, array.shape[1])
            h = max(1, round(w * array.shape[0] / array.shape[1]))
            frames.append(Image.fromarray(np.rint(_resize(array, w, h) * 255).astype(np.uint8)).quantize(colors=64))
        frames[0].save(output, save_all=True, append_images=frames[1:], duration=200, loop=0, optimize=False)
        if output.stat().st_size <= 400000:
            image_info(output)
            return True
    output.unlink(missing_ok=True)
    raise ValueError("GIF exceeds render byte cap even at preview size")


def render(stage_path, *, cameras=None, output="renders", size=(1280, 800), frames=None,
           views=None, manifest=None, executable=None, purposes="proxy,render"):
    """Render /Renders/<view> cameras; all mutations stay in output/temp layers."""
    from pxr import Sdf, Usd, UsdGeom
    width, height = size
    if any(not isinstance(v, int) or not 1 <= v <= 1600 for v in size):
        raise ValueError("render dimensions must be integers in 1..1600")
    selected_purposes = purposes.split(",")
    if not selected_purposes or any(p not in ("default", "guide", "proxy", "render") for p in selected_purposes):
        raise ValueError("purposes must be a comma-separated list of default, guide, proxy, render")
    recorder = executable or shutil.which("usdrecord")
    if not recorder:
        raise RuntimeError("usdrecord is unavailable")
    stage_path = Path(stage_path).resolve()
    if not stage_path.is_file():
        raise FileNotFoundError("render stage is missing")
    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    sequence = frame_range(frames) if isinstance(frames, str) else frames
    if sequence is not None and not sequence:
        raise ValueError("empty frame sequence")
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    environment["HDEMBREE_AMBIENT_OCCLUSION_SAMPLES"] = "0"
    environment["LC_ALL"] = "C"
    records = []
    with tempfile.TemporaryDirectory(prefix="aeco-render-") as temporary:
        root = Path(temporary)
        layer = Sdf.Layer.CreateNew(str(root / "render.usda"))
        layer.subLayerPaths = ([str(Path(cameras).resolve())] if cameras else []) + [str(stage_path)]
        layer.Save()
        stage = Usd.Stage.Open(layer)
        if stage.GetCompositionErrors():
            raise ValueError("render stage does not compose")
        scope = stage.GetPrimAtPath("/Renders")
        available = {p.GetName(): p for p in scope.GetChildren() if p.IsA(UsdGeom.Camera)} if scope else {}
        selected = sorted(views or available)
        if not selected or any(view not in available for view in selected):
            raise ValueError("named Camera prims are required under /Renders")
        geometry_purposes = {UsdGeom.Imageable(p).ComputePurpose()
                             for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies())
                             if p.IsA(UsdGeom.Gprim)}
        no_body = "no proxy/render-purpose geometry; add a proxy body or pass --purposes guide,proxy,render"
        if geometry_purposes == {"guide"} and "guide" not in selected_purposes:
            raise ValueError("all gprims have purpose guide; " + no_body)
        for view in selected:
            camera = UsdGeom.Camera(available[view])
            camera.GetVerticalApertureAttr().Set(camera.GetHorizontalApertureAttr().Get() * height / width)
        layer.Save()
        for view in selected:
            produced = []
            for frame in sequence if sequence is not None else [None]:
                filename = view + ("." + frame_name(frame) if frame is not None else "") + ".png"
                target = destination / filename
                with tempfile.TemporaryDirectory(dir=root) as shot:
                    image_pattern = Path(shot) / ("frame.###.###.png" if frame is not None else "image.png")
                    command = [str(recorder), "--disableGpu", "--renderer", "Embree", "--purposes", purposes,
                               "--colorCorrectionMode", "disabled", "--imageWidth", str(width), "--camera", "/Renders/" + view]
                    command += ["--frames", str(frame)] if frame is not None else ["--defaultTime"]
                    command += [str(root / "render.usda"), str(image_pattern)]
                    result = subprocess.run(command, env=environment, text=True, capture_output=True, timeout=120)
                    if result.returncode:
                        raise RuntimeError(f"usdrecord failed (exit {result.returncode}) for {filename}")
                    images = list(Path(shot).glob("*.png"))
                    if len(images) != 1:
                        raise RuntimeError("usdrecord did not produce exactly one image")
                    try:
                        info = image_info(images[0])
                    except ValueError as exc:
                        if str(exc) != "image has uniform pixels":
                            raise
                        if not geometry_purposes or geometry_purposes == {"guide"}:
                            cause = "stage has no gprims" if not geometry_purposes else "all gprims have purpose guide"
                            raise ValueError(f"{exc}; {cause}; {no_body}; check camera framing and visibility if guides are already enabled") from exc
                        raise ValueError(f"{exc}; check camera framing, visibility and geometry for --purposes {purposes}") from exc
                    if (info["width"], info["height"]) != size:
                        raise ValueError("usdrecord output dimensions differ from requested size")
                    shutil.copyfile(images[0], target)
                produced.append(target)
            if sequence is not None:
                sheet = destination / (view + ".sheet.png")
                contact_sheet(produced, sheet, size)
                gif = destination / (view + ".gif")
                has_gif = _gif(produced, gif)
                produced.append(sheet)
                if has_gif:
                    produced.append(gif)
            for path in produced:
                records.append({"path": destination.name + "/" + path.name, **image_info(path)})
    records.sort(key=lambda item: item["path"])
    if manifest:
        path = Path(manifest)
        data = json.loads(path.read_text()) if path.exists() else {}
        # Refresh only rendered views and retain other named views.
        old = [r for r in data.get("renders", []) if Path(r["path"]).name.split(".")[0] not in selected]
        data["renders"] = sorted(old + records, key=lambda item: item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return records
