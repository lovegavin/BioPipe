"""Package builtin route templates as importable workflow bundles.

The Studio imports workflows as ``.operon.zip`` archives containing
``graph.json``, ``parameters.json`` and ``execution.json``.  Builtin routes are
authored as ``task.yaml`` templates; this script compiles the reviewed route
index into one bundle per route and collects them into a single release asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def route_key(record: dict, sources: dict) -> str:
    path = sources.get(record["id"], {}).get("path", "")
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "routes":
        return parts[1]
    slug = record["name"].lower().replace(" ", "_")
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in slug)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "library/seed/src/web/builtin_routes.json")
    parser.add_argument("--release", type=Path, default=ROOT / "library/release.json")
    parser.add_argument("--version", default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "build/library")
    args = parser.parse_args()

    version = args.version or json.loads(args.release.read_text(encoding="utf-8"))["version"]
    index = json.loads(args.index.read_text(encoding="utf-8"))

    from operon.application import Application
    from src.web.parameters import export_bundle
    from src.web.profile import make_settings

    args.output.mkdir(parents=True, exist_ok=True)
    routes_dir = args.output / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)
    written = []
    data_dir = ROOT / ".studio/routes-build"
    data_dir.mkdir(parents=True, exist_ok=True)
    if True:
        settings = make_settings(ROOT, ROOT / "frontend/dist", workspace=ROOT, data_dir=data_dir)
        application = Application(settings)
        for record in index.get("routes", []):
            key = route_key(record, index.get("sources", {}))
            prepared = application.prepare(record["graph"])
            target = routes_dir / f"{key}.operon.zip"
            target.write_bytes(export_bundle(prepared))
            written.append((key, record["name"], target))
        application.shutdown()

    checksums = []
    for key, name, target in sorted(written):
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        checksums.append(f"{digest}  routes/{target.name}")
    readme = [
        f"# Operon route library v{version}",
        "",
        "Import one bundle at a time in Studio: File -> Import workflow bundle or JSON,",
        "or with the CLI: operon graph open <key>.operon.zip.",
        "",
        "Each bundle keeps its source paths relative to the builtin route workspace;",
        "point the Source nodes at your own files after import.",
        "",
        "| Route | File |",
        "| --- | --- |",
    ]
    readme += [f"| {name} | routes/{key}.operon.zip |" for key, name, _ in sorted(written)]
    readme_text = "\n".join(readme) + "\n"

    archive = args.output / f"Operon-Routes-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("README.md", readme_text)
        bundle.writestr("SHA256SUMS.txt", "\n".join(checksums) + "\n")
        for _, _, target in sorted(written):
            bundle.write(target, f"routes/{target.name}")
    print(json.dumps({"version": version, "routes": len(written), "archive": str(archive),
                      "bytes": archive.stat().st_size}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
