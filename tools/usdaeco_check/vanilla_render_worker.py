"""Fresh-process stock-USD rendering of a relocated result and camera layer."""
import json
from pathlib import Path
import shutil
import sys


def main(root, size):
    from pxr import Plug, Sdf, Usd, UsdGeom
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("family plugin discovered")
    from result_worker import inspect
    inspect(str(root / "example.usdc"))
    cameras = Sdf.Layer.FindOrOpen(str(root / "cameras.usda"))
    stage = Usd.Stage.Open(cameras)
    scope = stage.GetPrimAtPath("/Renders")
    names = sorted(p.GetName() for p in scope.GetChildren() if p.IsA(UsdGeom.Camera)) if scope else []
    if not names:
        raise ValueError("inputs/cameras.usda must declare a named Camera under /Renders")
    view = "overview" if "overview" in names else names[0]
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from usdaeco_render import render
    render(root / "example.usdc", cameras=root / "cameras.usda", output=root / "renders",
           views=[view], size=tuple(size), purposes="proxy,render")
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("family plugin discovered while rendering")
    shutil.copyfile(root / "renders" / (view + ".png"), root / "vanilla.png")


if __name__ == "__main__":
    try:
        # -I deliberately omits the script directory as an import source.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        main(Path(sys.argv[1]), json.loads(sys.argv[2]))
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1)
