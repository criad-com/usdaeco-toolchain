#!/usr/bin/env python3
"""Source entry point for the publication sweep."""
import sys
from usdaeco_check.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["publication", *sys.argv[1:]]))
