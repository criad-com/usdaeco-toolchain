"""Standalone plugin-free inspection of a relocated example crate."""
import json
import sys


def inspect(path):
    from pxr import Plug, Sdf, Usd, UsdUtils, Vt
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("family plugin discovered")
    layer = Sdf.Layer.FindOrOpen(path)
    if not layer or layer.GetFileFormat().formatId != "usdc":
        raise ValueError("result must be a binary usdc layer")
    if layer.subLayerPaths or any(UsdUtils.ExtractExternalReferences(path)):
        raise ValueError("result contains external asset dependencies")
    stage = Usd.Stage.Open(layer)
    if not stage or stage.GetCompositionErrors():
        raise ValueError("stage has composition errors")
    if not stage.GetDefaultPrim():
        raise ValueError("defaultPrim required")
    if stage.GetMetadata("metersPerUnit") != 1 or stage.GetMetadata("upAxis") != "Z":
        raise ValueError("metres and Z-up required")
    registry = Usd.SchemaRegistry()
    fallbacks = stage.GetMetadata("fallbackPrimTypes") or {}
    prims = list(stage.TraverseAll())
    count = len(prims)
    for prototype in stage.GetPrototypes():
        prims.extend(Usd.PrimRange(prototype, Usd.PrimAllPrimsPredicate))
    for prim in prims:
        name = prim.GetTypeName()
        if not name.startswith("Aeco"):
            continue
        candidates = fallbacks.get(name, [])
        # USD's internal prototype prim type info does not use stage fallback
        # mappings. Check their declarations here; the flattened backing specs
        # are also traversed above and must actually resolve to the stock type.
        if not isinstance(candidates, Vt.TokenArray) or not any(
                not candidate.startswith("Aeco") and registry.FindConcretePrimDefinition(candidate)
                and (prim.IsInPrototype() or prim.IsA(registry.GetTypeFromSchemaTypeName(candidate)))
                for candidate in candidates):
            raise ValueError("missing stock fallback for " + name)
    return {"prim_count": count}


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(sys.argv[1])))
    except Exception as exc:
        print(str(exc))
        raise SystemExit(1)
