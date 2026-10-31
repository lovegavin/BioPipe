"""End-to-end smoke tests for the five extension routes."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROUTES = [
    "rnaseq_de_enrichment",
    "single_cell_loom",
    "gwas_meta_prs",
    "proteomics_limma",
    "microbiome_diff",
]


@pytest.mark.parametrize("route", ROUTES)
def test_extension_route_runs(route, tmp_path):
    source = ROOT / "routes" / route
    target = tmp_path / route
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("output"))
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run.py"), str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=180, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((target / "output" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
