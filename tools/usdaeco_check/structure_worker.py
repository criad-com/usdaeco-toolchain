"""Fresh-process USD probes used by structure lint (registries cache globally)."""
import json
from pathlib import Path
import sys


def schema(root, name, deps):
    from pxr import Plug
    for dep in deps:
        Plug.Registry().RegisterPlugins(str(Path(dep).resolve()))
    from pxr import Ar, Sdf, Usd
    resources = []
    for plugin in Plug.Registry().GetAllPlugins():
        resources.extend([plugin.resourcePath, str(Path(plugin.resourcePath).parent)])
    Ar.SetPreferredResolver("ArDefaultResolver")
    Ar.DefaultResolver.SetDefaultSearchPath(resources)
    path = Path(root) / name / "schema.usda"
    layer = Sdf.Layer.FindOrOpen(str(path))
    stage = Usd.Stage.Open(layer)
    registry = Usd.SchemaRegistry()
    classes = []
    for prim in layer.rootPrims:
        if prim.name == "GLOBAL":
            continue
        composed = stage.GetPrimAtPath(prim.path)
        # USD composes apiSchemas across inherits and sublayers. Built-in API
        # fallbacks live in prim definitions, not in Sdf property stacks.
        apis = composed.GetAppliedSchemas()
        api_definition = registry.BuildComposedPrimDefinition("", apis) if apis else None
        classes.append({"name": prim.name, "data": dict(prim.customData), "doc": prim.documentation,
                        "properties": [p.name for p in prim.properties],
                        "api_properties": list(api_definition.GetPropertyNames()) if api_definition else [],
                        "inherited_properties": [p.GetName() for p in composed.GetProperties()
                                                 if any(spec.layer != layer or spec.path.GetPrimPath() != prim.path
                                                        for spec in p.GetPropertyStack())],
                        "inherits": [str(p) for p in prim.inheritPathList.GetAppliedItems()]})
    global_prim = layer.GetPrimAtPath("/GLOBAL")
    return {"global": dict(global_prim.customData) if global_prim else {},
            "sublayers": list(layer.subLayerPaths), "classes": classes}


def validators(root, name, deps):
    sys.path.insert(0, root)
    from pxr import Plug, UsdValidation
    for dep in [*deps, str(Path(root) / name), str(Path(root) / (name + "Validators"))]:
        Plug.Registry().RegisterPlugins(str(Path(dep).resolve()))
    registry = UsdValidation.ValidationRegistry()
    keyword = name[0].upper() + name[1:] + "Validators"
    metadata = registry.GetValidatorMetadataForKeyword(keyword)
    result = []
    for item in metadata:
        validator = registry.GetOrLoadValidatorByName(item.name)
        if not validator:
            raise ValueError("validator did not load")
        from pxr import Tf
        for schema_type in item.GetSchemaTypes():
            if Tf.Type.FindByName(schema_type).isUnknown:
                raise ValueError("unknown validator schema type")
        result.append({"name": item.name, "schemaTypes": list(item.GetSchemaTypes())})
    return result


def vanilla(paths):
    from pxr import Plug, Usd
    if any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins()):
        raise ValueError("vanilla worker loaded a family plugin")
    registry = Usd.SchemaRegistry()
    for path in paths:
        stage = Usd.Stage.Open(path)
        if not stage or stage.GetCompositionErrors():
            raise ValueError("stage does not compose")
        fallbacks = stage.GetMetadata("fallbackPrimTypes") or {}
        for prim in stage.TraverseAll():
            name = prim.GetTypeName()
            if name.startswith("Aeco"):
                candidates = fallbacks.get(name, [])
                if not any(not v.startswith("Aeco") and registry.FindConcretePrimDefinition(v) for v in candidates):
                    raise ValueError("missing stock fallback for " + name)
    return len(paths)


def main():
    task, args = sys.argv[1], json.loads(sys.argv[2])
    result = globals()[task](*args)
    print("STRUCTURE_JSON:" + json.dumps(result, default=list))


if __name__ == "__main__":
    main()
