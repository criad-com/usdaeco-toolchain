"""Shared adapters for real Python UsdValidation plugins.

RegisterPlugins must precede construction of the ValidationRegistry singleton.
Plugin callbacks accept (prim_or_stage, time_range); single-argument legacy
callbacks are also accepted. schema_types uses registered Tf type names.
"""
import inspect
from pxr import Sdf, UsdValidation


def _task(fn):
    try:
        inspect.signature(fn).bind(None, None)
        return fn
    except TypeError:
        inspect.signature(fn).bind(None)
        return lambda target, time_range: fn(target)


def _register(name, fn, schema_types, scope):
    if not callable(fn) or ":" not in name:
        raise ValueError("validator needs a qualified name and callable")
    registry = UsdValidation.ValidationRegistry()
    if registry.HasValidator(name):
        raise ValueError("validator already registered: " + name)
    callback = _task(fn)
    known = {m.name for m in registry.GetAllValidatorMetadata()}
    if name in known:
        metadata = registry.GetValidatorMetadata(name)
        if scope == "Prim" and list(metadata.GetSchemaTypes()) != list(schema_types):
            raise ValueError("schema_types differ from plugin metadata")
        getattr(registry, "RegisterPlugin" + scope + "Validator")(name, callback)
    else:
        plugin = name.split(":", 1)[0]
        keyword = plugin[0].upper() + plugin[1:]
        metadata = UsdValidation.ValidatorMetadata(name=name, doc=fn.__doc__ or name,
                                                   keywords=[keyword], schemaTypes=list(schema_types))
        getattr(registry, "Register" + scope + "Validator")(metadata, callback)
    return registry.GetOrLoadValidatorByName(name)


def register_prim_validator(name, fn, schema_types):
    """Register a prim rule, using declared plugin metadata when available."""
    return _register(name, fn, schema_types, "Prim")


def register_stage_validator(name, fn):
    """Register a rule over the complete composed stage."""
    return _register(name, fn, [], "Stage")


def wrap_legacy(name, legacy_fn):
    """Adapt an error-list callback; this does not register it.

    Existing ValidationError values pass through unchanged. Dictionaries use
    name/code, message, path and severity (error/warn/info); (code, path, message)
    tuples and message strings are accepted. Legacy error spelling is retained.
    """
    def adapted(target, time_range=None):
        stage = target.GetStage() if hasattr(target, "GetStage") else target
        result = []
        for error in legacy_fn(target):
            if isinstance(error, UsdValidation.ValidationError):
                result.append(error)
                continue
            if isinstance(error, str):
                error = {"name": name.split(":")[-1], "message": error}
            elif isinstance(error, tuple) and len(error) == 3:
                error = dict(zip(("name", "path", "message"), error))
            if not isinstance(error, dict):
                raise TypeError("legacy errors must be ValidationError, dict, triple or string")
            severity = error.get("severity", "error").lower()
            levels = {"error": UsdValidation.ValidationErrorType.Error,
                      "warn": UsdValidation.ValidationErrorType.Warn,
                      "warning": UsdValidation.ValidationErrorType.Warn,
                      "info": UsdValidation.ValidationErrorType.Info}
            if severity not in levels:
                raise ValueError("unknown legacy error severity")
            path = Sdf.Path(error.get("path", str(target.GetPath()) if hasattr(target, "GetPath") else "/"))
            result.append(UsdValidation.ValidationError(
                error.get("name", error.get("code", name.split(":")[-1])), levels[severity],
                [UsdValidation.ValidationErrorSite(stage, path)], error.get("message", "")))
        return result
    return adapted


def run(stage, keywords):
    """Run deduplicated registry-selected rules through ValidationContext.

    Unknown keywords are errors, so misspelled rule selection cannot pass empty.
    """
    if isinstance(keywords, str):
        keywords = [keywords]
    # Plug knows source package locations even when embedded Python does not.
    # Add only registered validator module parents, without changing PYTHONPATH.
    from pathlib import Path
    import sys
    from pxr import Plug
    for plugin in Plug.Registry().GetAllPlugins():
        if "Validators" in plugin.metadata:
            package = Path(plugin.path)
            if (package / "__init__.py").is_file() and str(package.parent) not in sys.path:
                sys.path.insert(0, str(package.parent))
    registry = UsdValidation.ValidationRegistry()
    names = set()
    for keyword in keywords:
        metadata = registry.GetValidatorMetadataForKeyword(keyword)
        if not metadata:
            raise ValueError("no validators for keyword: " + keyword)
        names.update(m.name for m in metadata)
    validators = registry.GetOrLoadValidatorsByName(sorted(names))
    if len(validators) != len(names) or not all(validators):
        raise ValueError("a selected validator did not load")
    if not names:
        raise ValueError("at least one validator keyword is required")
    return list(UsdValidation.ValidationContext(validators).Validate(stage))
