#!/usr/bin/env bash
# Build a codeless schema using the Python/OpenUSD environment selected by PYTHON.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec env -u PYTHONPATH "${PYTHON:-python3}" "$HERE/tools/build_schema.py" "$@"
