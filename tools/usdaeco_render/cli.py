"""Render named USD cameras with Embree and deterministic artifact names."""
import argparse
from . import render


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage")
    parser.add_argument("--cameras")
    parser.add_argument("--out", default="renders")
    parser.add_argument("--size", default="1280x800")
    parser.add_argument("--frames")
    parser.add_argument("--view", action="append")
    parser.add_argument("--manifest", default="manifest.json")
    parser.add_argument("--purposes", default="proxy,render", help="comma-separated purposes; use guide,proxy,render to include guides")
    args = parser.parse_args(argv)
    try:
        size = tuple(int(v) for v in args.size.lower().split("x"))
        if len(size) != 2:
            raise ValueError("size must be WIDTHxHEIGHT")
        print("== stage: render", flush=True)
        records = render(args.stage, cameras=args.cameras, output=args.out, size=size,
                         frames=args.frames, views=args.view, manifest=args.manifest, purposes=args.purposes)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"render failed: {exc}\n")
    for entry in records:
        print(f"{entry['path']}: {entry['width']}x{entry['height']}, {entry['bytes']} bytes, {entry['sha256']}")
    return 0
