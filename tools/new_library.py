#!/usr/bin/env python3
"""Instantiate the pxr-shaped skeleton from library.json-style answers."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

KINDS = ("library", "usecase", "integration", "data", "gate", "board")
TIERS = ("core", "section", "kind", "record", "sector", "organization", "project", "toolchain", "integration", "data", "gate", "board")


def new_library(name, target_dir, *, kind="usecase", tier="kind"):
    suffix = name.removeprefix("usdAeco")
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", suffix) or name.startswith("Aeco"):
        raise ValueError("name must be an UpperCamelCase suffix, optionally prefixed usdAeco")
    if kind not in KINDS or tier not in TIERS:
        raise ValueError("unknown kind or tier")
    library = "usdAeco" + suffix
    target = Path(target_dir).resolve()
    if target.exists():
        raise FileExistsError(f"target already exists: {target.name}")
    template = Path(__file__).resolve().parents[1] / "template"
    if not (template / "library.json").is_file():
        from importlib.metadata import distribution
        installed = distribution("usdaeco-toolchain")
        candidate = next(p for p in installed.files if str(p).endswith("share/usdaeco-toolchain/template/library.json"))
        template = Path(installed.locate_file(candidate)).parent
    replacements = [("UsdAecoExample", "UsdAeco" + suffix), ("usdAecoExample", library),
                    ("AecoExample", "Aeco" + suffix), ("ExampleAPI", suffix + "API"),
                    ("usdaeco_example", "usdaeco_" + suffix.lower()),
                    ("usdaeco-example", "usdaeco-" + suffix.lower()),
                    ("aeco-example", "aeco-" + suffix.lower()),
                    ("aeco:example:", "aeco:" + suffix.lower() + ":"),
                    ("example.json", suffix.lower() + ".json")]
    def replace(value):
        for before, after in replacements:
            value = value.replace(before, after)
        return value
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="new-library-", dir=target.parent) as temporary:
        staged = Path(temporary) / "library"
        def ignore(directory, names):
            transient = {"__pycache__", "pluginset", ".pytest_cache", "flake.lock"}
            if "result" not in Path(directory).relative_to(template).parts:
                transient.add("out")
            return transient.intersection(names)
        shutil.copytree(template, staged, ignore=ignore)
        for path in sorted(staged.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_file():
                if path.suffix == ".usdc":
                    from pxr import Sdf
                    layer = Sdf.Layer.OpenAsAnonymous(str(path))
                    layer.ImportFromString(replace(layer.ExportToString()))
                    layer.Export(str(path))
                else:
                    try:
                        path.write_text(replace(path.read_text()))
                    except UnicodeDecodeError:
                        pass
            renamed = replace(path.name)
            if path.name != renamed:
                path.rename(path.with_name(renamed))
        metadata = json.loads((staged / "library.json").read_text())
        metadata.update(name=library, kind=kind, tier=tier)
        descriptor = staged / library / "plugInfo.json"
        if descriptor.exists():
            # Preserve the generator formatting; update only the tier literal.
            descriptor.write_text(descriptor.read_text().replace('"tier": "kind"', f'"tier": "{tier}"'))
        if kind == "integration":
            (staged / "examples/datacentre").rename(staged / "examples/roundtrip")
            for p in staged.rglob("*"):
                if p.is_file() and p.suffix in (".md", ".py", ".nix"):
                    p.write_text(p.read_text().replace("examples/datacentre", "examples/roundtrip"))
        if kind in ("data", "gate", "board"):
            metadata.update(name="usdaeco-" + suffix.lower(), requires={})
            licence_section = (staged / "README.md").read_text().split("## Licence\n", 1)[1].strip()
            for relative in (library, library + "Validators", "testenv", "conformance", "examples", "docs/usecase.md", "build.sh"):
                p = staged / relative
                shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
            (staged / "README.md").write_text("# " + metadata["name"] + " — " + kind + " repository\n\n" +
                "\n\n".join("## " + h + "\n\nReplace with this repository's contract." for h in
                ("Use case", "The schema on an index card", "The example", "Build and check", "Family", "Layout", "Status")) +
                "\n\n## Licence\n\n" + licence_section + "\n")
            project = staged / "pyproject.toml"
            project_text = project.read_text()
            project_text = re.sub(r'packages = \[.*?\]', 'packages = ["usdaeco_' + suffix.lower() + '"]', project_text)
            project_text = re.sub(r', usdAeco[^}]+(?=})', '', project_text)
            project_text = re.sub(r'\[tool.setuptools.package-data\]\n[^\[]*', '', project_text)
            project.write_text(project_text)
            dependency_file = staged / "dependencies.json"
            dependencies = json.loads(dependency_file.read_text())
            dependencies["repos"] = {"toolchain": dependencies["repos"]["toolchain"]}
            dependency_file.write_text(json.dumps(dependencies, indent=2) + "\n")
            reduced_flake = (template / "reduced-flake.nix").read_text()
            (staged / "flake.nix").write_text(replace(reduced_flake))
            (staged / "check.py").write_text('''#!/usr/bin/env python3
"""Print N checks, M failed."""
from pathlib import Path
from usdaeco_check import Report
from usdaeco_check.structure import check_structure
report = Report()
for result in check_structure(Path(__file__).parent):
    report.add(result)
report.exit()
''')
        (staged / "reduced-flake.nix").unlink(missing_ok=True)
        (staged / "library.json").write_text(json.dumps(metadata, indent=2) + "\n")
        # Renaming changes minimal-stage bytes; keep provenance truthful.
        import hashlib
        example_dir = staged / "examples" / ("roundtrip" if kind == "integration" else "datacentre")
        manifest_path = example_dir / "manifest.json"
        if manifest_path.exists():
            example_manifest = json.loads(manifest_path.read_text())
            if example_manifest.get("source", {}).get("mode") == "minimal":
                minimal = staged / library / "examples/minimal.usda"
                example_manifest["source"]["sha256"] = hashlib.sha256(minimal.read_bytes()).hexdigest()
                example_manifest["source"]["layers"] = [{"path": minimal.name,
                    "sha256": example_manifest["source"]["sha256"], "bytes": minimal.stat().st_size}]
            from usdaeco_check.example_result import file_records
            files = file_records(example_dir / "result")
            example_manifest["result"]["files"] = files
            example_manifest["result"]["bytes"] = sum(item["bytes"] for item in files)
            manifest_path.write_text(json.dumps(example_manifest, indent=2) + "\n")
        staged.rename(target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_name", nargs="?")
    parser.add_argument("targetDir", nargs="?", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--kind", choices=KINDS, default="usecase")
    parser.add_argument("--tier", choices=TIERS, default="kind")
    args = parser.parse_args(argv)
    name = args.name or args.legacy_name
    if not name:
        parser.error("--name is required")
    target = args.targetDir or (Path(args.legacy_name) if args.name and args.legacy_name else
                                Path("usdaeco-" + name.removeprefix("usdAeco").lower()))
    try:
        directory = new_library(name, target, kind=args.kind, tier=args.tier)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"new library failed: {exc}\n")
    print(f"created {directory.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
