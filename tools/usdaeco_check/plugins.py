"""Plugin manifest discovery and version contracts, without importing pxr."""
from dataclasses import dataclass
import glob
import json
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version


def read_json(path):
    return json.loads("\n".join(line for line in Path(path).read_text().splitlines()
                                if not line.lstrip().startswith("#")))


def validate_metadata(name, metadata):
    if not isinstance(metadata, dict):
        raise ValueError(f"{name}: missing Info.aeco metadata")
    Version(metadata["version"])
    if not isinstance(metadata.get("tier"), str) or not metadata["tier"]:
        raise ValueError(f"{name}: missing tier")
    requires = metadata.get("requires")
    if not isinstance(requires, dict):
        raise ValueError(f"{name}: requires must be a dictionary")
    for dependency, constraint in requires.items():
        if not isinstance(dependency, str) or not dependency:
            raise ValueError(f"{name}: invalid dependency name")
        if not isinstance(constraint, str) or not constraint.strip():
            raise ValueError(f"{name}: empty version constraint for {dependency}")
        SpecifierSet(constraint)


def check_requirements(metadata):
    """Return dependency-first names; reject missing/old plugins and cycles."""
    ordered, active = [], []

    def visit(name):
        if name in active:
            raise ValueError("plugin dependency cycle: " + " -> ".join(active + [name]))
        if name in ordered:
            return
        info = metadata[name]
        validate_metadata(name, info)
        active.append(name)
        for dependency, constraint in sorted(info["requires"].items()):
            if dependency not in metadata:
                raise ValueError(f"{name} requires {dependency} {constraint}: plugin absent or missing Info.aeco")
            validate_metadata(dependency, metadata[dependency])
            version = metadata[dependency]["version"]
            if Version(version) not in SpecifierSet(constraint):
                raise ValueError(f"{name} requires {dependency} {constraint}: found {version}")
            visit(dependency)
        active.pop()
        ordered.append(name)

    for name in sorted(metadata):
        visit(name)
    return ordered


@dataclass(frozen=True)
class Plugin:
    name: str
    info: dict
    descriptor: Path
    resource_path: Path


def discover(paths):
    """Read descriptors and their Includes. Reject ambiguous plugin names."""
    found, visited = {}, set()

    def read(path):
        path = Path(path).resolve()
        if path.is_dir() and not (path / "plugInfo.json").is_file():
            candidates = sorted(path.glob("usdAeco*/plugInfo.json"))
            candidates += sorted(path.glob("plugins/*/resources/plugInfo.json"))
            # Native installs use one Includes descriptor at lib/plugInfo.json.
            # Read it in place so relative Root/LibraryPath entries keep meaning.
            if (path / "lib/plugInfo.json").is_file():
                candidates.append(path / "lib/plugInfo.json")
            if not candidates:
                raise ValueError(f"no plugin descriptors in {path.name}")
            for candidate in candidates:
                read(candidate)
            return
        if path.is_dir():
            path /= "plugInfo.json"
        if path in visited:
            return
        visited.add(path)
        document = read_json(path)
        for entry in document.get("Plugins", []):
            name = entry["Name"]
            if name in found and found[name].descriptor != path:
                raise ValueError(f"duplicate plugin name: {name}")
            root = path.parent / entry.get("Root", ".")
            found[name] = Plugin(name, entry.get("Info", {}), path,
                                 (root / entry.get("ResourcePath", ".")).resolve())
        for include in document.get("Includes", []):
            pattern = str(path.parent / include)
            matches = sorted(glob.glob(pattern, recursive=True))
            if not matches:
                raise ValueError(f"plugin Include does not resolve: {include}")
            for match in matches:
                read(match)

    for path in paths:
        read(path)
    return found
