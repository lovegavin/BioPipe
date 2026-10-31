"""R oracle check for 0.98 additive B-spline regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.additive_spline_regression import (
    AdditiveSplineRegressionStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(x1, x2, y):
    data = np.column_stack([
        np.asarray(x1, dtype=float),
        np.asarray(x2, dtype=float),
        np.asarray(y, dtype=float),
    ])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x1": 0, "x2": 1, "y": 2},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def test_additive_spline_matches_r_splines_bs(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    rng = np.random.default_rng(20261118)
    x1 = rng.normal(size=80)
    x2 = rng.uniform(-1.0, 2.0, size=80)
    y = (
        np.sin(1.4 * x1)
        + 0.25 * x2 ** 2
        - 0.15 * np.cos(2.0 * x2)
        + rng.normal(scale=0.05, size=80)
    )
    pd.DataFrame({"x1": x1, "x2": x2, "y": y}).to_csv(
        tmp_path / "d.csv", index=False
    )
    script = f"""
    d <- read.csv("{tmp_path / 'd.csv'}")
    f <- lm(y ~ splines::bs(x1, df=5, degree=3) +
                 splines::bs(x2, df=4, degree=3), data=d)
    s <- summary(f)
    write.csv(data.frame(fitted=fitted(f), resid=resid(f)),
              "{tmp_path / 'fit.csv'}", row.names=FALSE)
    write.csv(data.frame(r2=s[["r.squared"]], adj=s[["adj.r.squared"]]),
              "{tmp_path / 'r2.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )
    export = _run(
        AdditiveSplineRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "df": {"x1": 5, "x2": 4},
            "output": "fit",
        },
        _form(x1, x2, y),
    )
    ref = pd.read_csv(tmp_path / "fit.csv")
    r2 = pd.read_csv(tmp_path / "r2.csv").iloc[0]
    np.testing.assert_allclose(
        export["fitted"], ref["fitted"].to_numpy(dtype=float),
        rtol=0, atol=1e-8,
    )
    np.testing.assert_allclose(
        export["residual"], ref["resid"].to_numpy(dtype=float),
        rtol=0, atol=1e-8,
    )
    assert export["r2"] == pytest.approx(float(r2["r2"]), abs=1e-12)
    assert export["adj_r2"] == pytest.approx(float(r2["adj"]), abs=1e-12)
