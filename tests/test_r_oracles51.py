"""Authoritative R checks for 0.67 OLS residual diagnostics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.press import PressStep
from src.task.step.steps.standardized_residuals import StandardizedResidualsStep
from src.task.step.steps.studentized_residuals import StudentizedResidualsStep


class Ctx(dict):
    def __init__(self):
        super().__init__()
        self.step_params = {"response": "y"}


def _design():
    x = np.arange(1, 11, dtype=np.float64)
    y = 2.0 + 0.5 * x + np.array([1, -1, 2, -2, 0, 1, -1, 2, -2, 0], dtype=np.float64)
    data = np.column_stack([x, y]).astype(np.float32)
    form = Form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(10)}, "feature": {"x": 0, "y": 1}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step):
    ctx = Ctx()
    step.run(ctx, [_design()])
    return ctx[step.name].data


R_SCRIPT = r"""
x <- 1:10
y <- 2 + 0.5*x + c(1, -1, 2, -2, 0, 1, -1, 2, -2, 0)
fit <- lm(y ~ x)
cat(sprintf("%.17g\n", rstandard(fit)))
cat("---\n")
cat(sprintf("%.17g\n", rstudent(fit)))
cat("---\n")
e <- resid(fit)
h <- hatvalues(fit)
press <- sum((e / (1 - h))^2)
cat(sprintf("%.17g\n", press))
cat(sprintf("%.17g\n", sqrt(press / length(e))))
"""


def test_067_residuals_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "residuals.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    parts = [part.strip() for part in proc.stdout.strip().split("---")]
    standardized = np.asarray([float(value) for value in parts[0].splitlines()], dtype=np.float64)
    studentized = np.asarray([float(value) for value in parts[1].splitlines()], dtype=np.float64)
    press = [float(value) for value in parts[2].splitlines()]
    produced = [
        _run(StandardizedResidualsStep())[:, 0],
        _run(StudentizedResidualsStep())[:, 0],
        _run(PressStep())[0, :2],
    ]
    np.testing.assert_allclose(produced[0], standardized, rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(produced[1], studentized, rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(produced[2], press, rtol=1e-6, atol=1e-8)
