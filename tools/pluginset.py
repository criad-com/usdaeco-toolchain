#!/usr/bin/env python3
"""Write a relative Includes descriptor for a plugin dependency closure."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from usdaeco_check.plugins import check_requirements, discover


def plugin_set(out_dir, plugin_dirs, search_dirs=()):
    """Roots are explicit; candidates come from --search and PXR_PLUGINPATH_NAME.

    Candidates are inspected without loading USD, so unavailable/old versions
    are diagnosed before a process-global schema registry can cache them.
    """
    roots = discover(plugin_dirs)
    if not roots:
        raise ValueError("at least one plugin is required")
    environment = [p for p in os.environ.get("PXR_PLUGINPATH_NAME", "").split(os.pathsep) if p]
    available = discover([*plugin_dirs, *search_dirs, *environment])
    selected = {}

    def include(name):
        if name in selected:
            return
        if name not in available:
            raise ValueError(f"required plugin absent: {name}; pass its directory or --search")
        plugin = available[name]
        if "aeco" not in plugin.info:
            if "Validators" not in plugin.info:
                raise ValueError(f"{name}: missing Info.aeco")
            selected[name] = {"version": "0.0.0", "tier": "toolchain", "requires": {}}
        else:
            selected[name] = plugin.info["aeco"]
        for dependency in selected[name].get("requires", {}):
            include(dependency)

    for name in roots:
        include(name)
    ordered = check_requirements(selected)
    destination = Path(out_dir).resolve()
    descriptors = list(dict.fromkeys(available[name].descriptor for name in ordered))
    output = destination / "plugInfo.json"
    if output in descriptors:
        raise ValueError("aggregate output must not replace an included plugin descriptor")
    document = {"Includes": [os.path.relpath(path, destination) for path in descriptors]}
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=destination, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(document, handle, indent=4)
        handle.write("\n")
    try:
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outDir", type=Path)
    parser.add_argument("pluginDir", nargs="+", type=Path)
    parser.add_argument("--search", action="append", default=[], type=Path,
                        help="candidate dependency directory, without making it a root")
    args = parser.parse_args(argv)
    try:
        names = plugin_set(args.outDir, args.pluginDir, args.search)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"plugin set failed: {exc}\n")
    print("plugin set: " + ", ".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
