"""Composable usdAeco checks. Register plugins before the first registry probe."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .plugins import check_requirements
from .report import Report, Result

__all__ = ["Report", "Result", "registry_probe", "can_apply", "validate_examples",
           "link_check", "term_sweep", "plugin_requires"]


def registry_probe(applied_apis=(), concrete_types=()):
    from pxr import Usd
    registry = Usd.SchemaRegistry()
    apis, types = list(applied_apis), list(concrete_types)
    missing = [name for name in apis if registry.FindAppliedAPIPrimDefinition(name) is None]
    missing += [name for name in types if registry.FindConcretePrimDefinition(name) is None]
    return Result("schema registry", not missing,
                  "missing: " + ", ".join(missing) if missing else
                  f"{len(apis)} applied APIs, {len(types)} concrete types resolve")


def can_apply(cases):
    """Cases: (prim or type name, API name, expected bool[, instance name])."""
    from pxr import Usd
    stage = Usd.Stage.CreateInMemory()
    failures, count = [], 0
    for index, case in enumerate(cases):
        target, api, expected, *instance = case
        if len(instance) > 1 or not isinstance(expected, bool):
            raise ValueError("CanApplyAPI cases need an expected bool and at most one instance")
        if Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(api) is None:
            failures.append(f"{api}: applied schema is not registered")
            count += 1
            continue
        prim = stage.DefinePrim(f"/Probe{index}", target) if isinstance(target, str) else target
        answer = prim.CanApplyAPI(api, *instance)
        actual = answer[0] if isinstance(answer, tuple) else bool(answer)
        if actual != expected:
            failures.append(f"{prim.GetTypeName()} + {api}: expected {expected}, got {actual}")
        count += 1
    return Result("CanApplyAPI restrictions", not failures,
                  "; ".join(failures) if failures else f"{count} cases passed")


def plugin_requires(plugin_dir=()):
    """Register paths, then verify Info.aeco for every registered family plugin.

    Call before Usd.SchemaRegistry or opening a stage; USD caches definitions.
    An empty sequence validates plugins already registered by the environment.
    """
    from pxr import Plug
    paths = [plugin_dir] if isinstance(plugin_dir, (str, Path)) else list(plugin_dir)
    registry = Plug.Registry()
    try:
        from .plugins import discover
        requested = discover(paths) if paths else {}
        for descriptor in dict.fromkeys(p.descriptor for p in requested.values()):
            registry.RegisterPlugins(str(descriptor))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return Result("plugin requirements", False, str(exc))
    plugins = list(registry.GetAllPlugins())
    metadata = {p.name: dict(p.metadata["aeco"]) for p in plugins
                if "aeco" in p.metadata}
    try:
        for plugin in plugins:
            if plugin.name.startswith("usdAeco") and plugin.name not in metadata and "Validators" not in plugin.metadata:
                raise ValueError(f"{plugin.name}: missing Info.aeco metadata")
        # A typo must not yield a vacuous pass from RegisterPlugins([]).
        if paths:
            from .plugins import discover
            requested = discover(paths)
            for name, plugin in requested.items():
                if "Validators" in plugin.info:
                    continue
                if name not in metadata or not registry.GetPluginWithName(name):
                    raise ValueError(f"{name}: not registered with Info.aeco")
                loaded = registry.GetPluginWithName(name)
                if Path(loaded.resourcePath).resolve() != plugin.resource_path:
                    raise ValueError(f"{name}: another copy is already registered")
            if not requested:
                raise ValueError("no plugins found in requested paths")
        ordered = check_requirements(metadata)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return Result("plugin requirements", False, str(exc))
    return Result("plugin requirements", True, ", ".join(
        f"{name} {metadata[name]['version']}" for name in ordered) or "no family plugins registered")


def validate_examples(dir, plugin_dirs=(), expect_errors=0, *, validators=()):
    """Compose examples, check fallback coverage, and run UsdCore validators.

    Additional callbacks take a stage and return UsdValidation errors (for
    example a library's validate_stage). expect_errors is the total count;
    unreadable stages, composition errors and missing fallbacks always fail.
    """
    requirements = plugin_requires(plugin_dirs)
    if not requirements:
        return requirements
    from pxr import Usd, UsdValidation
    directory = Path(dir)
    files = sorted(p for p in directory.rglob("*") if p.suffix in (".usd", ".usda", ".usdc"))
    if not files:
        return Result("examples", False, f"no USD examples found in {directory}")
    registry = UsdValidation.ValidationRegistry()
    metadata = registry.GetValidatorMetadataForKeyword("UsdCoreValidators")
    context = UsdValidation.ValidationContext(registry.GetOrLoadValidatorsByName([m.name for m in metadata]))
    hard, soft, failures = [], [], []
    for path in files:
        try:
            stage = Usd.Stage.Open(str(path))
            if not stage:
                raise ValueError("stage did not open")
            failures.extend(f"{path.name}: {error}" for error in stage.GetCompositionErrors())
            used = {p.GetTypeName() for p in stage.TraverseAll() if p.GetTypeName().startswith("Aeco")}
            fallback = dict(stage.GetMetadata("fallbackPrimTypes") or {})
            missing = sorted(name for name in used if not fallback.get(name))
            if missing:
                failures.append(f"{path.name}: missing fallbackPrimTypes for {missing}")
            errors = list(context.Validate(stage))
            for validator in validators:
                errors.extend(validator(stage))
            for error in errors:
                target = hard if error.GetType() == UsdValidation.ValidationErrorType.Error else soft
                target.append(f"{path.name}: {error.GetName()}: {error.GetMessage()}")
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
    ok = not failures and len(hard) == expect_errors
    detail = f"{len(files)} examples, {len(hard)} errors (expected {expect_errors}), {len(soft)} warnings"
    if not ok:
        detail += "; " + "; ".join(failures + hard)
    return Result("examples compose and validate", ok, detail)


def _text_files(paths):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    ignored = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for path in map(Path, paths):
        if not path.exists():
            raise FileNotFoundError(path)
        for file in sorted(path.rglob("*")) if path.is_dir() else [path]:
            if file.is_file() and not ignored.intersection(file.parts):
                try:
                    yield file, file.read_text()
                except UnicodeDecodeError:
                    continue


def link_check(doc_dir):
    """Check local Markdown link/image files (inline and reference links).

    Remote links and heading anchors are intentionally not fetched/validated.
    """
    failures, count = [], 0
    for path, text in _text_files(doc_dir):
        if path.suffix.lower() != ".md":
            continue
        text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
        links = re.findall(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", text)
        links += re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", text)
        for link in links:
            target = urlsplit(link.strip("<>"))
            if target.scheme or target.netloc or not target.path:
                continue
            count += 1
            if not (path.parent / unquote(target.path)).exists():
                failures.append(f"{path}: {link}")
    return Result("local documentation links", not failures,
                  "; ".join(failures) if failures else f"{count} links resolve (anchors and remote URLs skipped)")


def term_sweep(paths, patterns):
    """Match caller-supplied regular expressions, case-insensitively, by line."""
    regexes = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    matches = []
    count = 0
    for path, text in _text_files(paths):
        count += 1
        for line, value in enumerate(text.splitlines(), 1):
            if any(regex.search(value) for regex in regexes):
                # Do not echo the sensitive text that the sweep is detecting.
                matches.append(f"{path}:{line}")
    return Result("term sweep", not matches,
                  "; ".join(matches) if matches else f"{count} text files, no matches")
