from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = ROOT / "examples" / "route_combinations"
CASES = [
    "refseq_cds_sequence_features",
    "thousand_genomes_chr22_population",
    "leukemia_all_aml_expression",
    "pbmc3k_single_cell_atlas",
    "qiime_moving_pictures_microbiome",
]
THRESHOLDS = {
    "refseq_cds_sequence_features": 11,
    "thousand_genomes_chr22_population": 13,
    "leukemia_all_aml_expression": 11,
    "pbmc3k_single_cell_atlas": 12,
    "qiime_moving_pictures_microbiome": 13,
}


def _run(task_dir: Path, *extra: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run.py"), str(task_dir), *extra],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_route_examples_are_curated_five() -> None:
    dirs = sorted(path.name for path in EXAMPLE_ROOT.iterdir() if path.is_dir())
    assert dirs == sorted(CASES)
    for name in CASES:
        assert (EXAMPLE_ROOT / name / "ANALYSIS.md").is_file(), f"{name} lacks ANALYSIS.md"


@pytest.mark.parametrize("name", CASES)
def test_route_combination_check(name: str) -> None:
    proc = _run(EXAMPLE_ROOT / name, "--check", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK OK" in proc.stdout


@pytest.mark.parametrize("name", CASES)
def test_route_combination_executes_in_tmp(name: str, tmp_path: Path) -> None:
    dst = tmp_path / name
    shutil.copytree(
        EXAMPLE_ROOT / name,
        dst,
        ignore=shutil.ignore_patterns("output"),
    )
    proc = _run(dst)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary_path = dst / "output" / "run_summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    assert summary["n_steps"] >= THRESHOLDS[name]
