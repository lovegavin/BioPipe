"""Authoritative R checks for 0.63 cross-correlation and difference-sign."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cross_correlation import CrossCorrelationStep
from src.task.step.steps.difference_sign import DifferenceSignStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _series(values, name):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {name: 0}},
    )


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


R_SCRIPT = r"""
library(randtests)
x <- c(1,2,3,4,5,4,3,2,1)
y <- c(2,1,2,4,5,6,5,8,7)
cc <- ccf(x, y, lag.max=3, plot=FALSE)$acf
cat("CCF")
for (v in as.numeric(cc)) cat(sprintf(" %.17g", v))
cat("\nDS")
d <- c(1,2,3,4,5,4,3,2,1,2,3,4)
ds <- difference.sign.test(d)
cat(sprintf(" %.17g %.17g\n", as.numeric(ds$statistic), ds$p.value))
"""


def test_063_cross_correlation_and_sign_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    lines = proc.stdout.splitlines()
    ccf_values = [float(value) for value in lines[0].split()[1:]]
    sign_parts = lines[1].split()
    sign_statistic, sign_pvalue = float(sign_parts[1]), float(sign_parts[2])
    assert len(ccf_values) == 7

    _, out = _run(
        CrossCorrelationStep(),
        {"first_label": "x", "second_label": "y", "lags": 3},
        [_series([1, 2, 3, 4, 5, 4, 3, 2, 1], "x"), _series([2, 1, 2, 4, 5, 6, 5, 8, 7], "y")],
    )
    assert [float(out.data[i, 0]) for i in range(7)] == pytest.approx(ccf_values, rel=1e-6)

    _, out = _run(DifferenceSignStep(), {"value_label": "value"}, [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4], "value")])
    assert float(out.data[0, 0]) == pytest.approx(sign_statistic, rel=1e-6)
    assert float(out.data[1, 0]) == pytest.approx(sign_pvalue, rel=1e-6)
