#!/usr/bin/env python3
"""Run the contract checks and print N checks, M failed."""
import argparse
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(os.environ.get("TOOLCHAIN_DIR", HERE.parent / "usdaeco-toolchain")) / "tools"))
sys.path.insert(0, str(HERE))
from usdaeco_check import Report, can_apply, plugin_requires, registry_probe, validate_examples
from usdaeco_check.structure import check_structure
from usdaeco_check.example import check_example


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-plugin", default=os.environ.get("CORE_PLUGIN_DIR", str(HERE.parent / "usdaeco-core/plugins/usdAeco/resources")))
    parser.add_argument("--plugin", default=str(HERE / "usdAecoExample"))
    args = parser.parse_args()
    report = Report()
    print("== stage: structure", flush=True)
    for result in check_structure(HERE, deps=[args.core_plugin]):
        report.add(result)
    print("== stage: registry", flush=True)
    if not report.run("plugin requirements", plugin_requires, [args.core_plugin, args.plugin]):
        return report.finish()
    from pxr import Plug, Usd, UsdValidation
    Plug.Registry().RegisterPlugins(str(HERE / "usdAecoExampleValidators"))
    report.add(registry_probe(["AecoExampleAPI"], ["AecoPort"]))
    report.add(can_apply([("Xform", "AecoExampleAPI", True), ("Material", "AecoExampleAPI", False)]))
    definition = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoExampleAPI")
    report.check("derived metadata", definition.GetPropertyMetadata("aeco:example:derived", "aecoDerived") is True)
    registry = UsdValidation.ValidationRegistry()
    metadata = registry.GetValidatorMetadataForKeyword("UsdAecoExampleValidators")
    report.check("validator plugin listing", len(metadata) == 2 and all(registry.GetOrLoadValidatorByName(m.name) for m in metadata))
    from usdaeco_check.validation import run
    report.add(validate_examples(HERE / "usdAecoExample/examples", [], validators=[lambda stage: run(stage, ["UsdAecoExampleValidators"])]))
    print("== stage: example", flush=True)
    report.add(check_example(HERE / "examples/datacentre"))
    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
