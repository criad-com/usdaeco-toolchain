"""Derive the example result in its own layer."""
import argparse
from pathlib import Path
from pxr import Sdf, Usd


def derive(stage, out_dir):
    layer = Sdf.Layer.CreateNew(str(Path(out_dir) / "derived.usda"))
    stage.GetRootLayer().subLayerPaths.insert(0, layer.identifier)
    with Usd.EditContext(stage, layer):
        for prim in stage.Traverse():
            attr = prim.GetAttribute("aeco:example:driver")
            if attr and attr.Get() is not None:
                prim.CreateAttribute("aeco:example:derived", Sdf.ValueTypeNames.Double).Set(attr.Get() * 2)
    layer.Save()
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage")
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.Open(args.stage)
    derive(stage, args.out)
    return 0
