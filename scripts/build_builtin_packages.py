"""Refresh the builtin index, or build an independently installable builtin wheel.

python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_packages.py --package biopipe-core --output .tmp/packages
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def refresh():
    from biopipe.registry import maintain
    previous = os.environ.get("BIOPIPE_REGISTRY_MAINTENANCE")
    os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
    try:
        report = maintain("build", scope="packages")
    finally:
        if previous is None:
            os.environ.pop("BIOPIPE_REGISTRY_MAINTENANCE", None)
        else:
            os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = previous
    if report["errors"]:
        raise ValueError(json.dumps(report["errors"], ensure_ascii=False))
    from biopipe.packages import bundled_manifest, bundled_state
    return json.loads((ROOT / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))


def build_package(name, output):
    from biopipe.packages import bundled_manifest
    from biopipe.source_library import provider_wheel
    package = next((p for p in bundled_manifest()['packages'] if p['name'] == name), None)
    if package is None:
        raise ValueError(f'Unknown bundled package: {name}')
    return {'wheels': [str(provider_wheel(package, ROOT, Path(output).resolve()))]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--package")
    parser.add_argument("--library-version", help="Build a separate complete .biopipe-library.zip")
    parser.add_argument("--output", type=Path, default=Path("build/packages"))
    args = parser.parse_args()
    if args.refresh:
        refresh()
        print("Builtin package index refreshed")
    if args.package:
        print(json.dumps(build_package(args.package, args.output), indent=2))
    if args.library_version:
        from biopipe.library_bundle import build_bundle
        print(json.dumps(build_bundle(ROOT, args.output, args.library_version), indent=2))
