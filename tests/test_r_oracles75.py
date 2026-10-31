"""R oracle check for 0.94 Box-Cox transform."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.box_cox import BoxCoxStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(x: np.ndarray):
    data = np.asarray(x, dtype=float).reshape(-1, 1)
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


X = np.array([0.5, 0.7, 0.9, 1.2, 1.5, 1.9, 2.4, 3.0, 3.8, 4.8], dtype=float)


def test_box_cox_matches_r_mass_boxcox(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    pd.DataFrame({"x": X}).to_csv(tmp_path / "x.csv", index=False)
    script = f"""
    library(MASS)
    d <- read.csv("{tmp_path / 'x.csv'}")
    x <- d[["x"]]
    bc <- boxcox(x ~ 1, plotit=FALSE, lambda=seq(-2, 2, length=4001))
    lam <- bc[["x"]][which.max(bc[["y"]])]
    y <- if (abs(lam) < 1e-12) log(x) else (x^lam - 1) / lam
    yhalf <- (x^0.5 - 1) / 0.5
    write.csv(data.frame(lambda=lam), "{tmp_path / 'lambda.csv'}", row.names=FALSE)
    write.csv(data.frame(y=y, yhalf=yhalf), "{tmp_path / 'y.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )

    form = _form(X)
    export = _run(BoxCoxStep(), {"output": "bc"}, form)
    ref_lambda = float(pd.read_csv(tmp_path / "lambda.csv").iloc[0, 0])
    assert export["lambdas"]["x"] == pytest.approx(ref_lambda, abs=2e-3)

    export_half = _run(BoxCoxStep(), {"lambdas": 0.5, "output": "bc"}, form)
    ref_y = pd.read_csv(tmp_path / "y.csv")
    # The fitted-lambda output uses the Python estimate; compare the explicit
    # half-power transform to R's exact formula at lambda=0.5.
    expected_half = ref_y["yhalf"].to_numpy(dtype=float)
    # Re-run to get the transformed form.
    ctx = Ctx({"lambdas": 0.5, "output": "bc"})
    BoxCoxStep().run(ctx, [form])
    # Operator output is float32; compare at float32 resolution.
    np.testing.assert_allclose(
        ctx["bc"].data[:, 0].astype(float), expected_half, rtol=0, atol=2e-7
    )
    assert export_half["lambdas"] == {"x": 0.5}
