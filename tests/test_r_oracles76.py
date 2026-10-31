"""R oracle check for 0.95 B-spline regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.spline_regression import SplineRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(x, y):
    data = np.column_stack([np.asarray(x, dtype=float), np.asarray(y, dtype=float)])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x": 0, "y": 1},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def test_spline_regression_matches_r_splines_bs(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    x = np.arange(1.0, 31.0)
    y = np.sin(x / 4.0) + 0.05 * x + 0.2 * np.cos(x * 1.3)
    pd.DataFrame({"x": x, "y": y}).to_csv(tmp_path / "d.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'd.csv'}")
    f <- lm(y ~ splines::bs(x, df=5, degree=3), data=d)
    out <- data.frame(fitted=fitted(f), resid=resid(f))
    write.csv(out, "{tmp_path / 'fit.csv'}", row.names=FALSE)
    write.csv(data.frame(r2=summary(f)[["r.squared"]]), "{tmp_path / 'r2.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )
    export = _run(
        SplineRegressionStep(),
        {"response_label": "y", "predictor_label": "x", "df": 5, "output": "fit"},
        _form(x, y),
    )
    ref = pd.read_csv(tmp_path / "fit.csv")
    r2 = float(pd.read_csv(tmp_path / "r2.csv").iloc[0, 0])
    np.testing.assert_allclose(
        export["fitted"], ref["fitted"].to_numpy(dtype=float), rtol=0, atol=1e-8
    )
    np.testing.assert_allclose(
        export["residual"], ref["resid"].to_numpy(dtype=float), rtol=0, atol=1e-8
    )
    assert export["r2"] == pytest.approx(r2, abs=1e-12)
