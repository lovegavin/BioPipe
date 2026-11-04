#!/usr/bin/env python
"""Inspect the large-resource manifest and report what still has to be installed.

Usage:
    python scripts/check_resources.py                 # every resource
    python scripts/check_resources.py --resource esm2 # one resource
    python scripts/check_resources.py --root /data/models
    python scripts/check_resources.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.task.step.steps._resources_common import check_many, load_resources  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", action="append", default=[], help="resource id (repeatable)")
    parser.add_argument("--root", default=None, help="directory to probe instead of the defaults")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    manifest = load_resources()
    checks = check_many(args.resource or None, args.root)
    if args.json:
        print(json.dumps(checks, indent=2, ensure_ascii=False))
    else:
        print(f"manifest: {len(manifest)} resources")
        for identifier in sorted(checks):
            check = checks[identifier]
            mark = {"ok": "OK", "partial": "PARTIAL", "missing": "MISSING"}[check["status"]]
            root = check["root"] or "(no directory found)"
            print(f"[{mark:7}] {identifier:14} {check['size_mb']:8.1f} MB  {root}")
            if check["missing"]:
                print(f"          missing: {', '.join(check['missing'])}")
                print(f"          install: {check['install']}")
            if check["env"]:
                print(f"          env:     {check['env']}")
    return 0 if all(check["status"] == "ok" for check in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
