"""R oracle check for 0.92 seasonal ARIMA."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.sarima import SarimaStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(values):
    values = np.asarray(values, dtype=float)
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


def _seasonal_series() -> np.ndarray:
    rng = np.random.default_rng(20261115)
    n = 120
    e = rng.normal(size=n)
    values = np.zeros(n, dtype=np.float64)
    for t in range(n):
        values[t] = e[t]
        if t >= 1:
            values[t] += 0.5 * e[t - 1]
        if t >= 4:
            values[t] += 0.6 * values[t - 4]
    return values


def test_sarima_matches_r_stats_arima(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    y = _seasonal_series()
    pd.DataFrame({"y": y}).to_csv(tmp_path / "series.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'series.csv'}")
    fit <- stats::arima(d[["y"]], order=c(0,0,1),
                        seasonal=list(order=c(0,0,1), period=4),
                        method="ML")
    se <- sqrt(diag(fit[["var.coef"]]))
    write.csv(data.frame(term=names(fit[["coef"]]),
                         estimate=as.numeric(fit[["coef"]]),
                         se=as.numeric(se)),
              "{tmp_path / 'coef.csv'}", row.names=FALSE)
    write.csv(data.frame(sigma2=fit[["sigma2"]],
                         loglik=fit[["loglik"]], aic=fit[["aic"]]),
              "{tmp_path / 'fit.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )

    export = _run(
        SarimaStep(),
        {
            "value_label": "y", "p": 0, "d": 0, "q": 1,
            "P": 0, "D": 0, "Q": 1, "seasonal_period": 4, "output": "fit",
        },
        _form(y[:, None]),
    )
    ref = pd.read_csv(tmp_path / "coef.csv")
    ref["term"] = ref["term"].replace(
        {"intercept": "intercept", "ma1": "ma.L1", "sma1": "ma.S.L4"}
    )
    ref = ref.set_index("term")
    for term in ("intercept", "ma.L1", "ma.S.L4"):
        idx = export["terms"].index(term)
        assert export["coef"][idx] == pytest.approx(
            float(ref.loc[term, "estimate"]), abs=1e-4
        )
        assert export["se"][idx] == pytest.approx(
            float(ref.loc[term, "se"]), abs=1e-4
        )

    fit = pd.read_csv(tmp_path / "fit.csv").iloc[0]
    assert export["sigma2"] == pytest.approx(float(fit["sigma2"]), abs=2e-5)
    assert export["loglikelihood"] == pytest.approx(
        float(fit["loglik"]), abs=1e-3
    )
    assert export["aic"] == pytest.approx(float(fit["aic"]), abs=2e-3)
