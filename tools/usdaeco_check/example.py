"""Compose and verify the shared examples/datacentre/run.py contract."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .contracts import require
from .plugins import read_json
from .report import Result
from .example_result import write_result, compare_results, check_vanilla
from .example_paths import relocate_source, check_result_paths


def _budget_seconds(manifest):
    budget = manifest.get("budgetSeconds", 180)
    require(type(budget) in (int, float) and 0 < budget <= 900,
            "ExampleBudgetInvalid: budgetSeconds must be a positive finite number at most 900")
    return budget


def _value(value):
    return read_json(value) if isinstance(value, (str, Path)) else value


def diff_findings(out, expected, *, abs_tol=1e-6, rel_tol=1e-6):
    """Return [] for equivalent findings; unordered lists preserve multiplicity.

    A bipartite match handles overlapping float tolerances without depending on
    the original order. Booleans are distinct from numbers; NaN never matches.
    """
    if abs_tol < 0 or rel_tol < 0:
        raise ValueError("tolerances cannot be negative")
    def equal(a, b):
        if isinstance(a, bool) or isinstance(b, bool):
            return type(a) is type(b) and a == b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, abs_tol=abs_tol, rel_tol=rel_tol)
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            edges = [[j for j, other in enumerate(b) if equal(item, other)] for item in a]
            matches = {}
            def assign(i, seen):
                for j in edges[i]:
                    if j in seen:
                        continue
                    seen.add(j)
                    if j not in matches or assign(matches[j], seen):
                        matches[j] = i
                        return True
                return False
            return all(assign(i, set()) for i in range(len(a)))
        return type(a) is type(b) and a == b
    actual, wanted = _value(out), _value(expected)
    return [] if equal(actual, wanted) else ["findings differ (values, fields or multiplicity outside tolerance)"]


def _source(example, minimal, pin, variant):
    override = os.environ.get("AECO_DATACENTRE_STAGE")
    release = os.environ.get("AECO_DATACENTRE_ROOT")
    if override:
        path, mode = Path(override).resolve(), "override"
    elif release:
        root = Path(release).resolve()
        path, mode = root / "dist" / variant / "dc.usda", "pinned"
        metadata = read_json(root / "library.json")
        require("v" + metadata["version"] == pin["ref"], "data-centre checkout version does not match the example pin; use an explicit stage override for a compatibility probe")
    else:
        path, mode = Path(minimal).resolve() if minimal else None, "minimal"
    require(path is not None and path.is_file(), "example source stage is unavailable")
    info = {"mode": mode, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    source_manifest = path.with_name("dc.manifest.json")
    if mode == "pinned":
        require(source_manifest.is_file(), "pinned source dc.manifest.json required")
    if source_manifest.is_file():
        info["manifest_sha256"] = hashlib.sha256(source_manifest.read_bytes()).hexdigest()
    if mode == "pinned":
        path = relocate_source(example, root) / "dist" / variant / "dc.usda"
    return path, info


def run_example(example_dir, hook, *, minimal=None, variant="base", publish=False,
                size=(1280, 800), frames=None, keywords=None):
    """Compose inputs above a pinned stage, call hook(stage, out_dir), render.

    Refreshes inputs/source for pinned runs; writes outputs under out/ until
    explicit publish=True. Expected findings are never replaced.
    """
    from pxr import Plug, Sdf, Usd
    from usdaeco_render import render
    example = Path(example_dir).resolve()
    repo = example.parents[1]
    declared = read_json(example / "manifest.json") if (example / "manifest.json").is_file() else {}
    _budget_seconds(declared)
    metadata = read_json(repo / "library.json")
    dependencies = read_json(repo / "dependencies.json")["repos"]
    datacentre, = [p for p in dependencies.values() if p["repo"] == "usdaeco-datacentre"]
    source, source_info = _source(example, minimal, datacentre, variant)
    require(callable(hook), "library hook must be callable")
    sys.path.insert(0, str(repo))
    if os.environ.get("CORE_PLUGIN_DIR"):
        Plug.Registry().RegisterPlugins(str(Path(os.environ["CORE_PLUGIN_DIR"]).resolve()))
    name = metadata["name"]
    if (repo / name / "plugInfo.json").is_file():
        Plug.Registry().RegisterPlugins(str(repo / name))
    if (repo / (name + "Validators") / "plugInfo.json").is_file():
        Plug.Registry().RegisterPlugins(str(repo / (name + "Validators")))
        if keywords is None:
            keywords = [name[0].upper() + name[1:] + "Validators"]
    out = example / "out"
    if out.is_symlink():
        raise ValueError("example out/ must not be a symlink")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    print("== stage: compose example (" + source_info["mode"] + ")", flush=True)
    base = Usd.Stage.Open(str(source))
    require(base is not None and not base.GetCompositionErrors(), "source stage does not compose")
    source_layers = {Path(p.realPath).resolve() for p in base.GetUsedLayers() if p.realPath}
    source_info["layers"] = [
        {"path": os.path.relpath(p, source.parent.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
         "bytes": p.stat().st_size} for p in sorted(source_layers)]
    layer = Sdf.Layer.CreateNew(str(out / "example.usda"))
    layer.subLayerPaths = [os.path.relpath(p, out) for p in sorted((example / "inputs").glob("*.usda"))] + [os.path.relpath(source, out)]
    stage = Usd.Stage.Open(layer)
    require(not stage.GetCompositionErrors(), "example overlays do not compose")
    if base.GetDefaultPrim():
        stage.SetDefaultPrim(stage.GetPrimAtPath(base.GetDefaultPrim().GetPath()))
    for key in ("upAxis", "metersPerUnit", "fallbackPrimTypes", "startTimeCode", "endTimeCode", "timeCodesPerSecond"):
        value = base.GetMetadata(key)
        if value is not None:
            stage.SetMetadata(key, value)
    print("== stage: library hook", flush=True)
    findings = hook(stage, out)
    require(isinstance(findings, list), "hook must return a JSON findings list")
    if keywords:
        from .validation import run
        errors = run(stage, keywords)
        findings.extend({"name": e.GetName(), "message": e.GetMessage(), "severity": str(e.GetType()).split(".")[-1].lower(),
                         "paths": [str(site.GetPath()) for site in e.GetSites()]} for e in errors)
    layer.subLayerPaths = [os.path.relpath(p, out) if Path(p).is_absolute() else p for p in layer.subLayerPaths]
    layer.Save()
    (out / "findings.json").write_text(json.dumps(findings, indent=2, sort_keys=True, allow_nan=False) + "\n")
    differences = diff_findings(out / "findings.json", example / "expected/findings.json")
    require(not differences, "; ".join(differences))
    print("== stage: standalone example result", flush=True)
    result_record = write_result(example, stage, source_layers, source_info, datacentre, variant, size=size)
    check_result_paths(example, directory=out / "result")
    layer.Save()
    print("== stage: render example", flush=True)
    records = render(out / "example.usda", output=out / "renders", size=size, frames=frames)
    manifest = {"facility": "demo-datacentre-01", "datacentre": {"ref": datacentre["ref"], "variant": variant},
                "pins": dependencies, "source": source_info,
                "findings_sha256": hashlib.sha256((example / "expected/findings.json").read_bytes()).hexdigest(),
                "actual_findings_sha256": hashlib.sha256((out / "findings.json").read_bytes()).hexdigest(),
                "renders": records, "result": result_record}
    if "budgetSeconds" in declared:
        manifest["budgetSeconds"] = declared["budgetSeconds"]
    if "assetResolvers" in declared:
        manifest["assetResolvers"] = declared["assetResolvers"]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if publish:
        result_target = example / "result"
        require(not result_target.is_symlink(), "committed result/ must not be a symlink")
        if result_target.exists():
            shutil.rmtree(result_target)
        shutil.copytree(out / "result", result_target)
        target = example / "renders"
        require(not target.is_symlink(), "committed renders/ must not be a symlink")
        target.mkdir(exist_ok=True)
        for old in target.iterdir():
            if old.suffix in (".png", ".gif"):
                old.unlink()
        for image in (out / "renders").iterdir():
            shutil.copyfile(image, target / image.name)
        shutil.copyfile(out / "manifest.json", example / "manifest.json")
    return manifest


def check_example(example_dir, *, execute=True, abs_tol=1e-6, rel_tol=1e-6):
    """Run the repository's hook in isolation and validate findings and images."""
    from .images import image_info
    example = Path(example_dir).resolve()
    timing = ""
    try:
        if execute:
            budget = _budget_seconds(read_json(example / "manifest.json"))
            environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            environment.setdefault("TOOLCHAIN_DIR", str(Path(__file__).resolve().parents[2]))
            started = time.perf_counter()
            try:
                result = subprocess.run([sys.executable, str(example / "run.py")], cwd=example.parents[1],
                                        env=environment, text=True, capture_output=True, timeout=budget)
            except subprocess.TimeoutExpired as exc:
                raise ValueError("ExampleBudgetExceeded: example runner exceeded its budget") from exc
            finally:
                elapsed = time.perf_counter() - started
                timing = f"; elapsed {elapsed:.3f}s / budget {budget:g}s"
                print("== stage: example runner" + timing, flush=True)
            require(elapsed <= budget, "ExampleBudgetExceeded: example runner exceeded its budget")
            require(result.returncode == 0, "example runner failed: " + (result.stderr or result.stdout)[-1000:])
        differences = diff_findings(example / "out/findings.json", example / "expected/findings.json", abs_tol=abs_tol, rel_tol=rel_tol)
        require(not differences, "; ".join(differences))
        manifest = read_json(example / "out/manifest.json")
        committed = read_json(example / "manifest.json")
        check_result_paths(example)
        compare_results(example, committed.get("result", {}), manifest.get("result", {}))
        check_vanilla(example, committed["result"])
        require(committed["source"] == manifest["source"] and committed["pins"] == manifest["pins"]
                and committed["datacentre"] == manifest["datacentre"],
                "ResultSourceStale: committed source evidence differs from fresh run")
        require(bool(manifest["renders"]), "example rendered no images")
        for record in manifest["renders"]:
            relative = Path(record["path"])
            require(not relative.is_absolute() and ".." not in relative.parts and relative.parts[0] == "renders", "invalid output render path")
            require(record == {"path": record["path"], **image_info(example / "out" / relative)}, "output render differs from manifest")
        return Result("example harness", True, f"findings and committed result match; {manifest['result']['prim_count']} plugin-free prims; {len(manifest['renders'])} non-blank renders; source {manifest['source']['mode']}" + timing)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return Result("example harness", False, str(exc).replace(str(example), "<example>") + timing)
