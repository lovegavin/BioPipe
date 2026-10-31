"""Authoritative R checks for 0.66 influence diagnostics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cooks_distance import CooksDistanceStep
from src.task.step.steps.dffits import DffitsStep
from src.task.step.steps.leverage import LeverageStep


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
    return ctx[step.name].data[:, 0]


R_SCRIPT = r"""
x <- 1:10
y <- 2 + 0.5*x + c(1, -1, 2, -2, 0, 1, -1, 2, -2, 0)
fit <- lm(y ~ x)
cat(sprintf("%.17g\n", hatvalues(fit)))
cat("---\n")
cat(sprintf("%.17g\n", cooks.distance(fit)))
cat("---\n")
cat(sprintf("%.17g\n", dffits(fit)))
"""


def test_066_influence_matches_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "influence.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    parts = [part.strip() for part in proc.stdout.strip().split("---")]
    reference = [
        np.asarray([float(value) for value in part.splitlines()], dtype=np.float64)
        for part in parts
    ]
    produced = [_run(LeverageStep()), _run(CooksDistanceStep()), _run(DffitsStep())]
    for actual, expected in zip(produced, reference):
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-8)
