"""R oracles for 0.74 CUSUM and EWMA control charts."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cusum_chart import CusumChartStep
from src.task.step.steps.ewma_chart import EwmaChartStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {"y": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def test_r_qcc_control_chart_oracles(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")

    values = np.asarray([10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17], dtype=float)
    np.savetxt(
        tmp_path / "series.csv",
        values.reshape(-1, 1),
        delimiter=",",
        header="y",
        comments="",
    )
    script = r"""
suppressPackageStartupMessages(library(qcc))
base <- commandArgs(TRUE)[1]
x <- read.csv(file.path(base, "series.csv"))$y
c1 <- cusum(x, sizes=1, decision.interval=5, se.shift=1, plot=FALSE)
cat("POS", paste(sprintf("%.17g", c1[["pos"]]), collapse=" "), "\n")
cat("NEG", paste(sprintf("%.17g", c1[["neg"]]), collapse=" "), "\n")
cat("CENTER", sprintf("%.17g", c1[["center"]]), "\n")
cat("SD", sprintf("%.17g", c1[["std.dev"]]), "\n")
e1 <- ewma(x, sizes=1, lambda=0.2, nsigmas=3, plot=FALSE)
cat("EWMA", paste(sprintf("%.17g", e1[["y"]]), collapse=" "), "\n")
cat("LCL", paste(sprintf("%.17g", e1[["limits"]][,1]), collapse=" "), "\n")
cat("UCL", paste(sprintf("%.17g", e1[["limits"]][,2]), collapse=" "), "\n")
"""
    proc = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R qcc not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")

    values_by_key = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"POS", "NEG", "CENTER", "SD", "EWMA", "LCL", "UCL"}:
            values_by_key[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values_by_key) == {"POS", "NEG", "CENTER", "SD", "EWMA", "LCL", "UCL"}

    cusum = _run(CusumChartStep(), {"value_label": "y"}, [_form(values)])
    ewma = _run(EwmaChartStep(), {"value_label": "y"}, [_form(values)])

    assert cusum["cusum_pos"] == pytest.approx(values_by_key["POS"], abs=1e-9)
    assert cusum["cusum_neg"] == pytest.approx(values_by_key["NEG"], abs=1e-9)
    assert cusum["center"] == pytest.approx(values_by_key["CENTER"][0], abs=1e-12)
    assert cusum["std_dev"] == pytest.approx(values_by_key["SD"][0], abs=1e-12)
    assert ewma["ewma"] == pytest.approx(values_by_key["EWMA"], abs=1e-9)
    assert ewma["lcl"] == pytest.approx(values_by_key["LCL"], abs=1e-9)
    assert ewma["ucl"] == pytest.approx(values_by_key["UCL"], abs=1e-9)
