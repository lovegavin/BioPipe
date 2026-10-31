"""R oracle check for the 0.96 VECM operator."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.vecm import VecmStep


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


def test_vecm_matches_r_urca(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    rng = np.random.default_rng(20261117)
    innovations = rng.normal(size=(200, 2))
    x = np.cumsum(innovations[:, 0])
    y = 0.8 * x + innovations[:, 1]
    pd.DataFrame({"x": x, "y": y}).to_csv(tmp_path / "d.csv", index=False)
    script = f"""
    library(urca)
    d <- read.csv("{tmp_path / 'd.csv'}")
    j <- ca.jo(d, type="trace", ecdet="none", K=2, spec="longrun")
    write.csv(data.frame(trace=rev(j@teststat), eigen=j@lambda),
              "{tmp_path / 'tests.csv'}", row.names=FALSE)
    write.csv(as.data.frame(j@V), "{tmp_path / 'beta.csv'}", row.names=FALSE)
    write.csv(as.data.frame(j@W), "{tmp_path / 'alpha.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )
    export = _run(
        VecmStep(), {"coint_rank": 1, "k_ar_diff": 1, "output": "fit"}, _form(x, y)
    )
    ref = pd.read_csv(tmp_path / "tests.csv")
    beta = pd.read_csv(tmp_path / "beta.csv").to_numpy(dtype=float)
    alpha = pd.read_csv(tmp_path / "alpha.csv").to_numpy(dtype=float)
    np.testing.assert_allclose(
        export["trace_stats"], ref["trace"].to_numpy(dtype=float), rtol=0, atol=1e-6
    )
    np.testing.assert_allclose(
        export["eigenvalues"], ref["eigen"].to_numpy(dtype=float), rtol=0, atol=1e-8
    )
    # R fixes the first cointegrating coefficient to one; statsmodels uses the
    # same normalization, but its iterative optimizer differs by ~1e-3.
    np.testing.assert_allclose(
        np.asarray(export["beta"]), beta[:, :1], rtol=0, atol=2e-3
    )
    np.testing.assert_allclose(
        np.asarray(export["alpha"]), alpha[:, :1], rtol=0, atol=2e-3
    )
