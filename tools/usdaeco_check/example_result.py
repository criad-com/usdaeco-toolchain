"""Committed example stages, authored layers, and reproducibility evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .contracts import require

RESULT_CAP = 10_000_000
LAYER_CAP = 2_000_000
NORMALIZATION = "sdf-usda-v1"


def normalized_layer(path, *, canonical_prototypes=True):
    """Canonical USDA serialization, with a fresh layer (no registry cache)."""
    from pxr import Sdf
    try:
        layer = Sdf.Layer.OpenAsAnonymous(str(path))
    except Exception as exc:
        raise ValueError("ResultInvalid: cannot read USD layer") from exc
    require(layer is not None, "ResultInvalid: cannot read USD layer")
    if canonical_prototypes:
        from .prototypes import canonicalize_prototypes
        canonicalize_prototypes(layer)
    return layer.ExportToString().encode("utf-8")


def result_files(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "ResultMissing: result/ required")
    paths = sorted(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "ResultInvalid: symlinks are not result files")
    files = [p for p in paths if p.is_file()]
    require(sum(p.stat().st_size for p in files) <= RESULT_CAP,
            f"ResultSizeExceeded: result/ exceeds {RESULT_CAP} bytes")
    for path in files:
        require(path.suffix != ".usda" or path.stat().st_size <= LAYER_CAP,
                f"ResultLayerSizeExceeded: {path.name} exceeds {LAYER_CAP} bytes")
    names = {p.relative_to(directory).as_posix() for p in files}
    require({"example.usdc", "README.md", "vanilla.png"} <= names and (directory / "layers").is_dir(),
            "ResultMissing: example.usdc, README.md, vanilla.png and layers/ required")
    require(all(n in ("example.usdc", "README.md", "vanilla.png") or (n.startswith("layers/") and n.endswith(".usda"))
                for n in names), "ResultInvalid: unsupported result file")
    return files


def file_records(directory):
    records = []
    for path in result_files(directory):
        raw = path.read_bytes()
        item = {"path": "result/" + path.relative_to(directory).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if path.suffix == ".usdc":
            item["normalized_sha256"] = hashlib.sha256(normalized_layer(path)).hexdigest()
        records.append(item)
    return records


def probe_result(path):
    """Open only a copied crate in an isolated interpreter and directory."""
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONPATH", "PXR_PLUGINPATH_NAME", "PXR_AR_DEFAULT_SEARCH_PATH")}
    worker = Path(__file__).with_name("result_worker.py")
    with tempfile.TemporaryDirectory(prefix="aeco-result-") as temporary:
        copied = Path(temporary) / "example.usdc"
        shutil.copyfile(path, copied)
        completed = subprocess.run([sys.executable, "-I", str(worker), str(copied)],
                                   cwd=temporary, env=environment, text=True, capture_output=True, timeout=90)
    require(completed.returncode == 0,
            "ResultVanillaFailed: isolated stage probe failed: " + completed.stdout.strip()[-500:])
    return json.loads(completed.stdout)


def record_result(directory):
    from .images import image_info
    files = file_records(directory)
    evidence = probe_result(Path(directory) / "example.usdc")
    return {"normalization": NORMALIZATION, "files": files,
            "bytes": sum(item["bytes"] for item in files), **evidence,
            "vanilla": {"path": "result/vanilla.png", **image_info(Path(directory) / "vanilla.png")}}


def render_vanilla(stage, cameras, target, size=(1280, 800)):
    """Relocate the committed entry point and render with no family plugins."""
    environment = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONPATH", "PXR_AR_DEFAULT_SEARCH_PATH", "CORE_PLUGIN_DIR")}
    environment["PXR_PLUGINPATH_NAME"] = ""
    worker = Path(__file__).with_name("vanilla_render_worker.py")
    with tempfile.TemporaryDirectory(prefix="aeco-vanilla-render-") as temporary:
        root = Path(temporary)
        shutil.copyfile(stage, root / "example.usdc")
        shutil.copyfile(cameras, root / "cameras.usda")
        completed = subprocess.run([sys.executable, "-I", str(worker), str(root), json.dumps(list(size))],
                                   cwd=root, env=environment, text=True, capture_output=True, timeout=150)
        require(completed.returncode == 0,
                "ResultVanillaRenderFailed: isolated usdrecord failed: " + completed.stdout.strip()[-500:])
        shutil.copyfile(root / "vanilla.png", target)


def check_vanilla(example, record):
    from .images import image_info
    example = Path(example)
    info = image_info(example / "result/vanilla.png")
    require(record.get("vanilla") == {"path": "result/vanilla.png", **info},
            "ResultVanillaManifestMismatch: vanilla image hash/size differs")
    with tempfile.TemporaryDirectory(prefix="aeco-vanilla-check-") as temporary:
        target = Path(temporary) / "vanilla.png"
        render_vanilla(example / "result/example.usdc", example / "inputs/cameras.usda", target,
                       (info["width"], info["height"]))
        image_info(target)
    return info


def validate_result(example, record, *, vanilla=False):
    directory = Path(example) / "result"
    files = file_records(directory)
    require(record.get("normalization") == NORMALIZATION, "ResultManifestMismatch: normalization differs")
    recorded = record.get("files")
    # Older v1 manifests stored the unrenamed Sdf serialization hash. Validate
    # that hash against the actual crate; comparisons below always use the new
    # canonical bytes. Raw hashes, sizes and the complete inventory stay exact.
    compatible = [dict(item) for item in files]
    if isinstance(recorded, list) and len(recorded) == len(files):
        for actual, old in zip(compatible, recorded):
            if (isinstance(old, dict) and actual != old
                    and actual["path"].endswith(".usdc")):
                path = Path(example) / actual["path"]
                legacy = hashlib.sha256(normalized_layer(path, canonical_prototypes=False)).hexdigest()
                if old.get("normalized_sha256") == legacy:
                    actual["normalized_sha256"] = legacy
    require(recorded == compatible and record.get("bytes") == sum(i["bytes"] for i in files),
            "ResultManifestMismatch: result files, hashes or sizes differ")
    require(type(record.get("prim_count")) is int and record["prim_count"] > 0,
            "ResultManifestMismatch: positive prim_count required")
    if vanilla:
        require(probe_result(directory / "example.usdc")["prim_count"] == record["prim_count"],
                "ResultPrimCountMismatch: plugin-free prim count differs")
    return files


def compare_results(example, committed, fresh):
    # Validate each byte inventory separately: crate byte layout can differ
    # while the documented text normalization remains exactly equivalent.
    committed_files = validate_result(example, committed, vanilla=True)
    fresh_files = validate_result(Path(example) / "out", fresh)
    def comparable(files):
        return [(i["path"], i.get("normalized_sha256", i["sha256"])) for i in files
                if i["path"] != "result/vanilla.png"]
    require(comparable(committed_files) == comparable(fresh_files)
            and committed["prim_count"] == fresh["prim_count"],
            "ResultStale: committed result differs from fresh run; run with --publish")


def write_result(example, stage, source_layers, source_info, pin, variant, *, size=(1280, 800)):
    """Flatten the composed view; retain only example-owned authored layers."""
    from pxr import Sdf, Usd
    example = Path(example)
    out = example / "out"
    directory = out / "result"
    (directory / "layers").mkdir(parents=True)
    own = []
    for base in (example / "inputs", out):
        for path in sorted(base.rglob("*")):
            if (not path.is_file() or path.suffix not in (".usd", ".usda", ".usdc")
                    or directory in path.parents or path == out / "example.usda"
                    or path.resolve() in source_layers):
                continue
            require(not path.is_symlink(), "ResultInvalid: authored layer must not be a symlink")
            relative = path.relative_to(example).with_suffix(".usda")
            target = directory / "layers" / relative
            require(not target.exists(), "ResultInvalid: authored layer names collide")
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".usda":
                shutil.copyfile(path, target)
            else:
                require(Sdf.Layer.OpenAsAnonymous(str(path)).Export(str(target)), "ResultInvalid: layer export failed")
            from .example_paths import archive_source_paths
            archive_source_paths(path, target, example)
            own.append("layers/" + relative.as_posix())

    require(not stage.GetCompositionErrors(), "ResultInvalid: composed stage has errors")
    fallbacks = dict(Usd.SchemaRegistry().GetFallbackPrimTypes())
    for layer in reversed(stage.GetLayerStack()):
        fallbacks.update(layer.pseudoRoot.GetInfo("fallbackPrimTypes") or {})
    prims = list(stage.TraverseAll())
    for prototype in stage.GetPrototypes():
        prims.extend(Usd.PrimRange(prototype, Usd.PrimAllPrimsPredicate))
    used = {p.GetTypeName() for p in prims if p.GetTypeName().startswith("Aeco")}
    require(all(name in fallbacks for name in used), "ResultFallbackMissing: declare fallbackPrimTypes for every Aeco type")
    stage.SetMetadata("fallbackPrimTypes", {name: fallbacks[name] for name in sorted(used)})
    for key, value in (("metersPerUnit", 1.0), ("upAxis", "Z")):
        require(not stage.HasAuthoredMetadata(key) or stage.GetMetadata(key) == value,
                "ResultMetricsInvalid: source must use metres and Z-up")
        stage.SetMetadata(key, value)
    if not stage.GetDefaultPrim():
        roots = [p for p in stage.GetPseudoRoot().GetChildren() if p.GetName() != "Renders"]
        require(len(roots) == 1, "ResultDefaultPrimMissing: declare an unambiguous defaultPrim")
        stage.SetDefaultPrim(roots[0])
    # FlattenLayerStack preserves external references/payloads. Stage.Flatten
    # also resolves those arcs and bakes the selected variants for a standalone
    # view, while keeping instance sharing through internal references.
    flattened = stage.Flatten(addSourceFileComment=False)
    require(flattened.Export(str(directory / "example.usdc")), "ResultInvalid: crate export failed")
    print("== stage: vanilla result render", flush=True)
    render_vanilla(directory / "example.usdc", example / "inputs/cameras.usda", directory / "vanilla.png", size)
    own_text = ", ".join("`" + p + "`" for p in sorted(own)) or "none"
    (directory / "README.md").write_text(
        "This is the flattened composed example, including its derived opinions and presentation; "
        "open it from the example directory with `usdview result/example.usdc` (no family plugins or sibling checkouts needed). "
        "The example's own authored layers are " + own_text + ". "
        f"Source pin: `usdaeco-datacentre {pin['ref']}`, variant `{variant}`; "
        f"source mode `{source_info['mode']}` (a minimal or override run does not prove the pinned release). "
        "The parent manifest records source hashes; pinned source layers are not copied here. "
        "`vanilla.png` records a stock USD render of this result.\n")
    return record_result(directory)
