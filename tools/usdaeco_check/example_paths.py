"""Example-local source aliases and portable archived asset paths (S29)."""
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from .contracts import require
from .plugins import read_json


def relocate_source(example, root):
    """Refresh the uncommitted inputs/source link without replacing real data."""
    link = Path(example) / "inputs/source"
    root = Path(root).resolve()
    require(root.is_dir(), "ExampleSourceInvalid: source root is unavailable")
    require(not link.exists() or link.is_symlink(),
            "ExampleSourceInvalid: inputs/source must be a runtime symlink")
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        if link.resolve() == root:
            return link
        link.unlink()
    link.symlink_to(root, target_is_directory=True)
    return link


def asset_paths(layer):
    """Visit sublayers, references, payloads and asset values, including samples."""
    from pxr import UsdUtils
    paths = set()
    UsdUtils.ModifyAssetPaths(layer, lambda path: paths.add(path) or path)
    return paths


def archive_source_paths(path, destination, example):
    """Rebase source assets for result/layers; retain all other authored bytes."""
    from pxr import Sdf
    alias = Path(example) / "inputs/source"
    if not alias.is_symlink():
        return
    source_root = alias.resolve()
    layer = Sdf.Layer.OpenAsAnonymous(str(destination))
    replacements = {}
    for asset in asset_paths(layer):
        if not asset or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", asset):
            continue
        resolved = (path.parent / asset).resolve()
        if resolved.is_relative_to(source_root):
            # out/result is a staging directory; paths are authored for the
            # committed result location, which also travels with the example.
            final = Path(example) / "result" / destination.relative_to(Path(example) / "out/result")
            replacements[asset] = os.path.relpath(alias / resolved.relative_to(source_root), final.parent)
    if replacements:
        text = destination.read_text()
        # USD's single/triple @ quoting is preserved, as is every non-asset byte.
        pattern = r'""".*?"""|"(?:\\.|[^"\\])*"|\#[^\n]*|@@@(.*?)@@@|@([^@\n]*)@'
        def replace(match):
            if match.group(1) is None and match.group(2) is None:
                return match.group()
            triple = match.group(1) is not None
            value = match.group(1) if triple else match.group(2)
            quote = "@@@" if triple else "@"
            return quote + replacements.get(value, value) + quote
        destination.write_text(re.sub(pattern, replace, text, flags=re.DOTALL))


def check_result_paths(example, *, directory=None):
    """Check authored paths lexically, even when the runtime link is absent."""
    from pxr import Sdf
    example = Path(example)
    directory = Path(directory) if directory else example / "result"
    declarations = read_json(example / "manifest.json").get("assetResolvers", {})
    require(isinstance(declarations, dict), "ResultSourcePathInvalid: assetResolvers must be an object")
    for token, explanation in declarations.items():
        require(bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]+:", token))
                and token.lower() != "file:" and isinstance(explanation, str) and bool(explanation.strip()),
                "ResultSourcePathInvalid: resolver tokens require a scheme and documentation")
    count = 0
    for path in sorted((directory / "layers").rglob("*")):
        if path.suffix not in (".usd", ".usda", ".usdc") or not path.is_file():
            continue
        layer = Sdf.Layer.OpenAsAnonymous(str(path))
        require(layer is not None, "ResultSourcePathInvalid: cannot open result layer")
        relative = PurePosixPath("result") / path.relative_to(directory).as_posix()
        for asset in sorted(asset_paths(layer)):
            if not asset:
                continue
            count += 1
            error = f"ResultSourcePathInvalid: {relative}: source assets must use example inputs/ or a documented resolver token"
            require(not PureWindowsPath(asset).drive and "\\" not in asset, error)
            scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", asset)
            if scheme:
                require(scheme.group() in declarations, error)
                continue
            require(not asset.startswith("/"), error)
            parts = list(relative.parent.parts)
            for part in PurePosixPath(asset).parts:
                if part == "..":
                    require(bool(parts), error + "; path escapes above example")
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            target = PurePosixPath(*parts)
            internal = (target.is_relative_to("result/layers") or target == PurePosixPath("result/example.usdc")) \
                and (directory / target.relative_to("result")).is_file()
            require(internal or target.is_relative_to("inputs"), error)
    return f"{count} asset paths use example inputs/, archived layers or documented resolver tokens"
