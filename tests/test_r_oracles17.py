"""R oracle checks for 0.32 intraclass and concordance correlation."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.concordance_correlation import ConcordanceCorrelationStep
from src.task.step.steps.intraclass_correlation import IntraclassCorrelationStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, names):
    form = Form(
        np.column_stack(data).astype(np.float64),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(data[0]))},
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


X = np.arange(1, 21, dtype=float)
Y = np.array([
    2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
    18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
])


def test_agreement32_matches_r(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript unavailable")
    probe = subprocess.run(
        ["Rscript", "-e", "cat(requireNamespace('irr',quietly=TRUE) && requireNamespace('DescTools',quietly=TRUE))"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip(f"R agreement packages unavailable: {probe.stdout.strip()}")

    pd.DataFrame({"x": X, "y": Y}).to_csv(tmp_path / "agreement.csv", index=False)
    icc_info = _run(IntraclassCorrelationStep(), {}, _form([X, Y], ["x", "y"]))
    ccc_info = _run(
        ConcordanceCorrelationStep(),
        {"method_a": "x", "method_b": "y"},
        _form([X, Y], ["x", "y"]),
    )

    script = r"""
suppressPackageStartupMessages({library(irr); library(DescTools)})
d <- read.csv(commandArgs(TRUE)[1])
r <- icc(d[, c("x", "y")], model="twoway", type="agreement", unit="single")
cat("ICC", paste(sprintf("%.17g", c(r$value, r$Fvalue, r$df1, r$df2, r$p.value, r$lbound, r$ubound)), collapse=","), "\n")
c <- CCC(d$x, d$y, ci="z-transform")
cat("CCC", paste(sprintf("%.17g", c(c$rho.c$est, c$rho.c$lwr.ci, c$rho.c$upr.ci, c$s.shift, c$l.shift, c$C.b)), collapse=","), "\n")
"""
    result = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path / "agreement.csv")],
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

    assert icc_info["icc"] == pytest.approx(parsed["ICC"][0], abs=1e-8)
    assert icc_info["f"] == pytest.approx(parsed["ICC"][1], abs=1e-8)
    assert icc_info["p"] == pytest.approx(parsed["ICC"][4], rel=1e-8)
    assert icc_info["ci_low"] == pytest.approx(parsed["ICC"][5], abs=1e-8)
    assert icc_info["ci_high"] == pytest.approx(parsed["ICC"][6], abs=1e-8)

    assert ccc_info["ccc"] == pytest.approx(parsed["CCC"][0], abs=1e-8)
    assert ccc_info["ci_low"] == pytest.approx(parsed["CCC"][1], abs=1e-8)
    assert ccc_info["ci_high"] == pytest.approx(parsed["CCC"][2], abs=1e-8)
    assert ccc_info["s_shift"] == pytest.approx(parsed["CCC"][3], abs=1e-8)
    assert ccc_info["l_shift"] == pytest.approx(parsed["CCC"][4], abs=1e-8)
    assert ccc_info["c_bias"] == pytest.approx(parsed["CCC"][5], abs=1e-8)
