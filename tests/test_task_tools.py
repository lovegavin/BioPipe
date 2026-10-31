"""Checks for the route-authoring preflight tools."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from biopipe.inspect import inspect_source
from src.task import load_manifest
from src.task.check import check_manifest

ROOT = Path(__file__).resolve().parents[1]


def _task(tmp_path, csv_text="a,b\n1,2\n3,4\n"):
    task = tmp_path / "demo"
    (task / "input").mkdir(parents=True)
    (task / "input" / "table.csv").write_text(csv_text, encoding="utf-8")
    (task / "task.yaml").write_text("""
name: demo
sources:
  table:
    path: input/table.csv
    dims: [sample, feature]
    labels: {sample: auto, feature: builtin}
steps:
  - name: normalize
    inputs: [table]
    params: {method: cpm, dim: sample, output: norm, _input_names: [table]}
  - name: describe
    inputs: [norm]
    params: {}
""", encoding="utf-8")
    return task


def test_inspect_reports_shape_and_labels(tmp_path):
    task = _task(tmp_path)
    result = inspect_source(task / "input/table.csv")
    assert result["reader"] == "CsvReader"
    assert result["shape"] == [2, 2]
    assert result["dims"] == ["sample", "feature"]
    assert result["labels"]["feature"]["count"] == 2


def test_check_accepts_valid_task_and_strips_internal_key(tmp_path):
    task = _task(tmp_path)
    report = check_manifest(task, load_manifest(task / "task.yaml"))
    assert report["ok"], report["errors"]
    assert [step["name"] for step in report["steps"]] == ["normalize", "describe"]


def test_check_reports_missing_file(tmp_path):
    task = _task(tmp_path)
    (task / "input/table.csv").unlink()
    report = check_manifest(task, load_manifest(task / "task.yaml"))
    assert not report["ok"]
    assert any("file not found" in error["message"] for error in report["errors"])


def test_run_check_cli(tmp_path):
    task = _task(tmp_path)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run.py"), str(task), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "CHECK OK" in result.stdout
