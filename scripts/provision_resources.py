"""Provision Operon large resources (weights and databases)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.resources.provision import ProvisionError, load_manifest, provision


def _pairs(values: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--rewrite expects OLD=NEW, got {value!r}")
        old, new = value.split("=", 1)
        pairs.append((old, new))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision Operon large resources")
    parser.add_argument("--root", required=True, help="resource root directory")
    parser.add_argument("--only", action="append", default=[], help="resource id (repeatable)")
    parser.add_argument("--file", action="append", default=[], dest="files", help="file name (repeatable)")
    parser.add_argument("--offline", action="store_true", help="verify only, never download or copy")
    parser.add_argument("--plan", action="store_true", help="report what would be fetched without fetching")
    parser.add_argument("--manifest", default="", help="manifest path override")
    parser.add_argument("--from-dir", default="", help="copy validated files from a local staging directory")
    parser.add_argument("--mirror", action="append", default=[], help="HF mirror prefix, e.g. https://hf-mirror.com")
    parser.add_argument("--rewrite", action="append", default=[], help="URL rewrite OLD=NEW (repeatable)")
    parser.add_argument("--jobs", type=int, default=1, help="parallel downloads (default 1)")
    parser.add_argument("--retries", type=int, default=3, help="download attempts per file")
    parser.add_argument("--timeout", type=int, default=60, help="per-request read timeout in seconds")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    manifest = load_manifest(args.manifest or None)
    try:
        summary = provision(
            manifest,
            args.root,
            only=args.only or None,
            files=args.files or None,
            offline=args.offline,
            plan=args.plan,
            timeout=args.timeout,
            retries=max(args.retries, 1),
            source_dir=args.from_dir or None,
            mirrors=args.mirror,
            rewrites=_pairs(args.rewrite),
            jobs=max(args.jobs, 1),
        )
    except ProvisionError as exc:
        print(f"provision: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for item in summary["results"]:
            print(f"[{item['status']:>10}] {item['resource']} -> {Path(item['root']) / item['resource']}")
            for name in item["downloaded"]:
                print(f"  downloaded {name}")
            for name in item["copied"]:
                print(f"  copied     {name}")
            for name in item["skipped"]:
                print(f"  present    {name}")
            for name in item["missing"]:
                print(f"  missing    {name}")
            for name in item["failed"]:
                print(f"  failed     {name}")
    return 0 if summary["status"] in ("ok", "planned") else 1


if __name__ == "__main__":
    raise SystemExit(main())
