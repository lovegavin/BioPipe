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
    "cancer_diagnosis_ml",
    "lung_regression_survival",
    "mite_community_ml",
    "diabetes_classification_regression",
]


def _run(task_dir: Path, *extra: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run.py"), str(task_dir), *extra],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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
    threshold = 13 if name == "mite_community_ml" else 7 if name == "diabetes_classification_regression" else 6
    assert summary["n_steps"] >= threshold
