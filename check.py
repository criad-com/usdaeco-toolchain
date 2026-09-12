#!/usr/bin/env python3
"""Run the shared kit gates and print N checks, M failed."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
from new_library import new_library
from usdaeco_check import Report, link_check
from usdaeco_check.structure import check_structure
from usdaeco_check.family import validate_family
from usdaeco_check.example import check_example
from native_check import native_checks
from family_readme import fresh_check
from usdaeco_check.publication import check_publication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--without-core", action="store_true", help="exclude core runtime tests; schema lint still needs compiler dependencies")
    parser.add_argument("--without-native", action="store_true", help="source-only compatibility gate; excludes the four native build/runtime rows")
    parser.add_argument("--family", help="train for an additional live family README freshness check")
    parser.add_argument("--family-repos", help="source checkouts for the selected train")
    args = parser.parse_args()
    report = Report()
    print("== stage: generated template structure", flush=True)
    with tempfile.TemporaryDirectory(prefix="aeco-kit-check-") as temporary:
        repo = new_library("Example", Path(temporary) / "example", kind="usecase", tier="kind")
        for result in check_structure(repo):
            report.add(result)
    print("== stage: toolchain structure", flush=True)
    for result in check_structure(HERE):
        report.add(result)
    print("== stage: committed template result", flush=True)
    report.add(check_example(HERE / "template/examples/datacentre"))
    print("== stage: family and documentation", flush=True)
    report.add(fresh_check(HERE / "docs/family/README.md", family=args.family, repos=args.family_repos))
    report.run("publication sweep", check_publication, HERE)
    report.add(validate_family(HERE / "tests/fixtures/family.json",
                              sibling_root=os.environ.get("AECO_FAMILY_SIBLINGS") or None, inventory=True))
    report.add(link_check(HERE / "README.md"))
    report.add(link_check(HERE / "docs"))
    if not args.without_native:
        print("== stage: native templates", flush=True)
        native_checks(report, HERE)
    print("== stage: pytest", flush=True)
    command = [sys.executable, "-m", "pytest", "-q"]
    if args.without_core:
        command += ["-m", "not core"]
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(command, cwd=HERE, env=environment)
    report.check("pytest", result.returncode == 0)
    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
