#!/usr/bin/env python3
"""Compose, derive, validate and render the example."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(os.environ.get("TOOLCHAIN_DIR", ROOT.parent / "usdaeco-toolchain")) / "tools"))
sys.path.insert(0, str(ROOT / "tools"))
from usdaeco_check.example import run_example
from usdaeco_example.cli import derive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    run_example(Path(__file__).parent, derive,
                minimal=ROOT / "usdAecoExample/examples/minimal.usda", publish=args.publish)


if __name__ == "__main__":
    main()
