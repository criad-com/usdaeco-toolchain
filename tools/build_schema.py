#!/usr/bin/env python3
"""Generate and install one resource-only OpenUSD schema plugin."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from usdaeco_check.plugins import check_requirements, discover, read_json


def build(name, schema_dir, out_dir=None, deps=(), bootstrap=None, *, generate_only=False, validate=False, install_root=None):
    with tempfile.TemporaryDirectory(prefix="schema-registry-") as registry_dir:
        return _build(name, schema_dir, out_dir, deps, bootstrap, Path(registry_dir), generate_only, validate, install_root)


def _build(name, schema_dir, out_dir, deps, bootstrap, registry_dir, generate_only, validate, install_root):
    source = Path(schema_dir).resolve()
    if not (source / "library.json").is_file() and (source / "schemas" / name / "library.json").is_file():
        source = source / "schemas" / name
    manifest_path = source / "library.json"
    if not manifest_path.is_file():
        manifest_path = source.parent / "library.json"
    manifest = read_json(manifest_path)
    repo = manifest_path.parent
    if (source / name / "schema.usda").is_file():
        source /= name
    destination = Path(out_dir).resolve() if out_dir else source
    if install_root:
        destination = Path(install_root).resolve() / "plugins" / name / "resources"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("libName must be a USD identifier")
    if manifest.get("name") != name:
        raise ValueError("library.json name must equal libName")
    for key in ("version", "tier"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise ValueError(f"library.json needs a nonempty {key}")
    requires = manifest.get("requires")
    if not isinstance(requires, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in requires.items()):
        raise ValueError("library.json requires must map plugin names to version constraints")
    dependencies = [Path(dep).resolve() for dep in deps]
    available = discover(dependencies)
    metadata = {key: plugin.info["aeco"] for key, plugin in available.items() if "aeco" in plugin.info}
    if generate_only or validate:
        missing = set(manifest["requires"]) - set(metadata)
        if missing:
            raise ValueError("schema generation dependencies absent: " + ", ".join(sorted(missing)))
        print("schema compiler dependencies: " + ", ".join(f"{k} {v['version']}" for k, v in metadata.items()))
    else:
        check_requirements({**metadata, name: manifest})
    dependencies = list(dict.fromkeys(plugin.descriptor.parent for plugin in available.values()))

    # Source checkouts provide the metadata-only bootstrap. Installed core
    # plugins register the same field, so they also support isolated builds.
    candidates = [source / "bootstrap"]
    for dep in dependencies:
        candidates.extend(parent / "schemas/usdAeco/bootstrap" for parent in dep.parents)
    if bootstrap:
        boot = Path(bootstrap).resolve()
        if not (boot / "plugInfo.json").is_file():
            raise ValueError(f"bootstrap has no plugInfo.json: {boot}")
    else:
        boot = next((p for p in candidates if (p / "plugInfo.json").is_file()), None)
    plugin_paths = [str(boot)] if boot else []
    for index, dep in enumerate(dependencies):
        descriptor = read_json(dep / "plugInfo.json")
        if (dep / "schema.usda").is_file():
            # usdGenSchema resets the resolver to registered resource paths.
            # Project the flat source module into an isolated install shape.
            resource = registry_dir / ("source-" + str(index))
            resource.mkdir()
            library_name = descriptor["Plugins"][0]["Name"]
            (resource / library_name).mkdir()
            shutil.copyfile(dep / "schema.usda", resource / library_name / "schema.usda")
            shutil.copyfile(dep / "generatedSchema.usda", resource / "generatedSchema.usda")
            for entry in descriptor["Plugins"]:
                entry["Root"] = str(resource)
                entry["ResourcePath"] = "."
                if boot:
                    entry.get("Info", {}).get("SdfMetadata", {}).pop("aecoDerived", None)
            (resource / "plugInfo.json").write_text(json.dumps(descriptor))
            plugin_paths.append(str(resource))
        elif boot and any("aecoDerived" in entry.get("Info", {}).get("SdfMetadata", {})
                        for entry in descriptor.get("Plugins", [])):
            # usdGenSchema resets Ar's search path from registered schema
            # types. Keep those types, but let only the bootstrap register
            # aecoDerived. This descriptor is private to the generation run.
            for entry in descriptor["Plugins"]:
                entry.get("Info", {}).get("SdfMetadata", {}).pop("aecoDerived", None)
                entry["Root"] = str((dep / entry.get("Root", ".")).resolve())
            private = registry_dir / str(index)
            private.mkdir()
            (private / "plugInfo.json").write_text(json.dumps(descriptor))
            plugin_paths.append(str(private))
        else:
            plugin_paths.append(str(dep))
    # Do not inherit undeclared plugins or resolver paths from the caller.
    os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(plugin_paths)
    from pxr import Plug
    registry = Plug.Registry()
    for path in plugin_paths:
        registry.RegisterPlugins(path)
    resources = []
    for builtin in ("usd", "usdGeom"):
        plugin = registry.GetPluginWithName(builtin)
        if not plugin:
            raise ValueError(f"OpenUSD plugin is unavailable: {builtin}")
        resources.append(plugin.resourcePath)
    for plugin in registry.GetAllPlugins():
        if "aeco" in plugin.metadata:
            resources.append(plugin.resourcePath)
    resources.extend(str(p) for p in dependencies)
    os.environ["PXR_AR_DEFAULT_SEARCH_PATH"] = os.pathsep.join(dict.fromkeys(resources))

    from pxr import Sdf, Usd
    layer = Sdf.Layer.FindOrOpen(str(source / "schema.usda"))
    if not layer:
        raise ValueError("cannot open schema.usda")
    global_prim = layer.GetPrimAtPath("/GLOBAL")
    data = global_prim.customData if global_prim else {}
    if data.get("libraryName") != name or data.get("skipCodeGeneration") is not True:
        raise ValueError("GLOBAL customData must set libraryName = libName and skipCodeGeneration = true")
    stage = Usd.Stage.Open(layer)
    if stage.GetCompositionErrors():
        raise ValueError("schema sublayers do not compose: " + str(stage.GetCompositionErrors()))

    import pxr
    pxr_root = Path(pxr.__file__).resolve().parent
    generator = pxr_root / "Usd/usdGenSchema.py"
    command = ([sys.executable, str(generator)] if generator.is_file()
               else [shutil.which("usdGenSchema") or "usdGenSchema"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="schema-build-", dir=destination.parent) as temporary:
        generated = Path(temporary)
        subprocess.run(command + [str(source / "schema.usda"), str(generated)], check=True)
        descriptor = read_json(generated / "plugInfo.json")
        plugins = descriptor["Plugins"]
        if len(plugins) != 1 or plugins[0]["Name"] != name:
            raise ValueError("usdGenSchema did not generate the requested library")
        plugin = plugins[0]
        plugin.update(Type="resource", Root=".", ResourcePath=".", LibraryPath="")
        info = plugin.setdefault("Info", {})
        info["aeco"] = {key: manifest[key] for key in ("version", "tier", "requires")}
        if name == "usdAeco":
            info.setdefault("SdfMetadata", {})["aecoDerived"] = {
                "type": "bool", "appliesTo": ["attributes", "relationships"],
                "displayGroup": "AECO"}
        encoded = json.dumps(descriptor, indent=4, sort_keys=True) + "\n"
        if "@PLUG_INFO_" in encoded:
            raise ValueError("unexpanded plugInfo placeholder")
        (generated / "plugInfo.json").write_text(encoded)
        # Re-emit using usdGenSchema's whitespace/comments so direct --validate
        # on the committed descriptor is clean as well as its semantic data.
        subprocess.run(command + [str(source / "schema.usda"), str(generated)], check=True)
        subprocess.run(command + ["--validate", str(source / "schema.usda"), str(generated)], check=True)
        if validate:
            for filename in ("plugInfo.json", "generatedSchema.usda"):
                different = ((read_json(generated / filename) != read_json(source / filename))
                             if filename.endswith("json") else
                             (generated / filename).read_bytes() != (source / filename).read_bytes())
                if different:
                    raise ValueError(f"stale generated file: {filename}")
            print("usdGenSchema --validate: clean")
            return source
        destination.mkdir(parents=True, exist_ok=True)
        for filename in ("plugInfo.json", "generatedSchema.usda"):
            shutil.copyfile(generated / filename, destination / filename)
        if destination != source:
            (destination / name).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / "schema.usda", destination / name / "schema.usda")
        if install_root:
            validator_source = repo / (name + "Validators")
            if validator_source.is_dir():
                shutil.copytree(validator_source, Path(install_root) / "python" / validator_source.name,
                                dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            includes = ["plugins/*/resources/"]
            if validator_source.is_dir():
                includes.append("python/*/")
            (Path(install_root) / "plugInfo.json").write_text(json.dumps({"Includes": includes}) + "\n")
    print(f"built {name} -> {destination}")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("libName")
    parser.add_argument("schemaDir", type=Path)
    parser.add_argument("outDir", type=Path, nargs="?")
    parser.add_argument("--generate-only", action="store_true", help="compile source only; dependency version compatibility is not asserted")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--dep", action="append", default=[], type=Path,
                        help="dependency resource directory; repeat for each dependency")
    parser.add_argument("--bootstrap", type=Path, help="explicit core metadata bootstrap directory")
    args = parser.parse_args()
    try:
        build(args.libName, args.schemaDir, args.outDir, args.dep, args.bootstrap, generate_only=args.generate_only, validate=args.validate, install_root=args.install_root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"build failed: {exc}\n")


if __name__ == "__main__":
    main()
