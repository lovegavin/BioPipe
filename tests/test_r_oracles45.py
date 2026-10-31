"""Authoritative R checks for 0.61 ACF/PACF."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.acf import AcfStep
from src.task.step.steps.pacf import PacfStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _series(values):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {"value": 0}},
    )


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


R_SCRIPT = r"""
x <- c(1,2,3,4,5,4,3,2,1,2,3,4)
a <- acf(x, lag.max=5, plot=FALSE)$acf
p <- pacf(x, lag.max=5, plot=FALSE)$acf
cat("ACF")
for (v in a) cat(sprintf(" %.17g", v))
cat("\nPACF")
for (v in p) cat(sprintf(" %.17g", v))
cat("\n")
"""


def test_061_acf_pacf_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    lines = proc.stdout.splitlines()
    acf_values = [float(value) for value in lines[0].split()[1:]]
    pacf_values = [float(value) for value in lines[1].split()[1:]]
    assert len(acf_values) == 6
    assert len(pacf_values) == 5

    _, out = _run(AcfStep(), {"value_label": "value", "lags": 5}, [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])])
    assert [float(out.data[i, 0]) for i in range(6)] == pytest.approx(acf_values, rel=1e-6)

    _, out = _run(PacfStep(), {"value_label": "value", "lags": 5}, [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])])
    assert [float(out.data[i, 0]) for i in range(5)] == pytest.approx(pacf_values, rel=1e-6)
