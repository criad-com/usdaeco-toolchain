"""Example prim and stage rules, loaded by Plug's Python plugin mechanism."""
from pxr import Sdf, UsdValidation
from . import validatorTokens as tokens


def driver_task(prim, time_range):
    attr = prim.GetAttribute("aeco:example:driver")
    value = attr.Get() if attr else None
    if value is not None and value <= 0:
        return [UsdValidation.ValidationError(
            tokens.INVALID_DRIVER, UsdValidation.ValidationErrorType.Error,
            [UsdValidation.ValidationErrorSite(prim.GetStage(), prim.GetPath())],
            "The driving value must be positive.")]
    return []


def stage_task(stage, time_range):
    if not stage.GetDefaultPrim():
        return [UsdValidation.ValidationError(
            tokens.MISSING_DEFAULT_PRIM, UsdValidation.ValidationErrorType.Error,
            [UsdValidation.ValidationErrorSite(stage, Sdf.Path.absoluteRootPath)],
            "The example stage needs a default prim.")]
    return []


_registry = UsdValidation.ValidationRegistry()
_registry.RegisterPluginPrimValidator(tokens.DRIVER_CHECKER, driver_task)
_registry.RegisterPluginStageValidator(tokens.STAGE_CHECKER, stage_task)
