#!/usr/bin/env python3
"""Generate C++/Python and a relocatable native plugin descriptor with usdGenSchema."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from usdaeco_check.plugins import check_requirements, discover, read_json
from usdaeco_check.contracts import ranges


def generate(name, source, generator, deps=()):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("name must be a USD identifier")
    source = Path(source).resolve()
    schema = source / name
    manifest = read_json(source / "library.json")
    ranges(manifest["requires"])
    if manifest["name"] != name:
        raise ValueError("library.json name must equal the requested library")
    available = discover(deps)
    metadata = {key: p.info["aeco"] for key, p in available.items() if "aeco" in p.info}
    check_requirements({**metadata, name: manifest})
    os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(str(p.descriptor) for p in available.values())
    from pxr import Plug, Sdf
    registry = Plug.Registry()
    for plugin in available.values():
        registry.RegisterPlugins(str(plugin.descriptor))
    layer = Sdf.Layer.FindOrOpen(str(schema / "schema.usda"))
    data = layer.GetPrimAtPath("/GLOBAL").customData
    if data.get("libraryName") != name or data.get("skipCodeGeneration", False):
        raise ValueError("GLOBAL must name this library and enable code generation")
    if data.get("useLiteralIdentifier") is not True:
        raise ValueError("GLOBAL must set useLiteralIdentifier = true")
    include_path = data["libraryPath"]
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*", include_path):
        raise ValueError("libraryPath must be a relative C++ include path")
    subprocess.run([sys.executable, str(generator), str(schema / "schema.usda"), str(schema)], check=True)
    subprocess.run([sys.executable, str(generator), "--validate", str(schema / "schema.usda"), str(schema)], check=True)
    document = read_json(schema / "plugInfo.json")
    plugin, = document["Plugins"]
    if plugin["Name"] != name or plugin["Type"] != "library":
        raise ValueError("generator did not produce the requested native library")
    plugin.update(Root="..", ResourcePath="resources",
                  LibraryPath="../@CMAKE_SHARED_LIBRARY_PREFIX@" + name + "@CMAKE_SHARED_LIBRARY_SUFFIX@")
    plugin["Info"]["aeco"] = {key: manifest[key] for key in ("version", "tier", "requires")}
    (schema / "plugInfo.json.in").write_text(json.dumps(document, indent=4) + "\n")
    (schema / "native-schema.cmake").write_text(f'set(AECO_SCHEMA_INCLUDE_PATH "{include_path}")\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("source", type=Path)
    parser.add_argument("--generator", required=True, type=Path)
    parser.add_argument("--dep", action="append", default=[], type=Path)
    args = parser.parse_args()
    generate(args.name, args.source, args.generator, args.dep)
