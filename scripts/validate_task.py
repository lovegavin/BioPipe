# scripts/validate_task.py
"""Validate a manifest without executing the pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipelines import PIPELINES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate a BioPipe manifest without running it."
    )
    ap.add_argument("--task", required=True, help="Task directory.")
    args = ap.parse_args()

    task_dir = Path(args.task).resolve()
    manifest_path = task_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    name = manifest.get("pipeline")
    if name not in PIPELINES:
        raise SystemExit(f"Unknown pipeline: '{name}'")

    plugin = PIPELINES[name]
    plugin.manifest.validate_manifest(manifest)

    for key in ("genotype", "phenotype", "covariates"):
        rel = manifest["input"].get(key)
        if rel and not (task_dir / rel).exists():
            raise SystemExit(
                f"Input path declared but missing: {rel}"
            )

    print(f"Manifest OK: {manifest_path}")


if __name__ == "__main__":
    main()