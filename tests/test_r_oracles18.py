"""R oracle checks for 0.33 Passing-Bablok and Deming regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.deming_regression import DemingRegressionStep
from src.task.step.steps.passing_bablok import PassingBablokStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(columns, names):
    data = np.column_stack(columns).astype(np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, data):
    ctx = Ctx(params)
    step.run(ctx, [data])
    return step.export(ctx)


X = np.arange(1, 11, dtype=float)
Y = np.array([1.1, 2.0, 2.9, 4.2, 5.1, 5.9, 7.1, 8.0, 9.2, 10.1])


def test_passing_bablok_and_deming_match_r(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript unavailable")
    probe = subprocess.run(
        ["Rscript", "-e", "cat(requireNamespace('mcr',quietly=TRUE))"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip(f"R oracle package unavailable: {probe.stdout.strip()}")

    pd.DataFrame({"x": X, "y": Y}).to_csv(tmp_path / "methods.csv", index=False)
    pb_info = _run(PassingBablokStep(), {"method_a": "x", "method_b": "y"}, _form([X, Y], ["x", "y"]))
    deming_info = _run(DemingRegressionStep(), {"method_a": "x", "method_b": "y"}, _form([X, Y], ["x", "y"]))

    script = r"""
suppressPackageStartupMessages(library(mcr))
d <- read.csv(commandArgs(TRUE)[1])
pb <- mcreg(d$x, d$y, method.reg="PaBa", method.ci="analytical")
cat("PB", paste(sprintf("%.17g", c(pb@para[1, 1], pb@para[2, 1])), collapse=","), "\n")
dm <- mcreg(d$x, d$y, method.reg="Deming", method.ci="analytical", error.ratio=1)
cat("DM", paste(sprintf("%.17g", c(dm@para[1, 1], dm@para[2, 1])), collapse=","), "\n")
"""
    result = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path / "methods.csv")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    parsed = {}
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0]] = [float(value) for value in parts[1].split(",")]

    assert pb_info["intercept"] == pytest.approx(parsed["PB"][0], abs=1e-10)
    assert pb_info["slope"] == pytest.approx(parsed["PB"][1], abs=1e-10)
    assert deming_info["intercept"] == pytest.approx(parsed["DM"][0], abs=1e-10)
    assert deming_info["slope"] == pytest.approx(parsed["DM"][1], abs=1e-10)
