"""R oracle checks for 0.87 ARIMA and isotonic regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.arima import ArimaStep
from src.task.step.steps.isotonic import IsotonicStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(values, labels=None):
    values = np.asarray(values, dtype=float)
    if labels is None:
        labels = ("x", "y") if values.shape[1] == 2 else ("y",)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _require_r() -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")


def _arima_series() -> np.ndarray:
    rng = np.random.default_rng(20261113)
    values = np.zeros(100, dtype=np.float64)
    values[0] = rng.normal()
    for i in range(1, values.size):
        values[i] = 0.6 * values[i - 1] + rng.normal(scale=0.8)
    return values + 1.5


def test_arima_matches_r_stats_arima(tmp_path):
    _require_r()
    y = _arima_series()
    pd.DataFrame({"y": y}).to_csv(tmp_path / "series.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'series.csv'}")
    fit <- stats::arima(d$y, order=c(1,0,0), method="ML", include.mean=TRUE)
    se <- sqrt(diag(fit$var.coef))
    write.csv(data.frame(term=names(fit$coef), estimate=as.numeric(fit$coef),
                         se=as.numeric(se)),
              "{tmp_path / 'coef.csv'}", row.names=FALSE)
    write.csv(data.frame(sigma2=fit[["sigma2"]], loglik=fit[["loglik"]],
                         aic=fit[["aic"]]),
              "{tmp_path / 'fit.csv'}", row.names=FALSE)
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    export = _run(
        ArimaStep(),
        {"value_label": "y", "p": 1, "d": 0, "q": 0, "output": "fit"},
        _form(y[:, None]),
    )
    ref = pd.read_csv(tmp_path / "coef.csv")
    ref["term"] = ref["term"].replace({"intercept": "const", "ar1": "ar.L1"})
    ref = ref.set_index("term")
    for term in ("const", "ar.L1"):
        idx = export["terms"].index(term)
        assert export["coef"][idx] == pytest.approx(
            float(ref.loc[term, "estimate"]), abs=1e-4
        )
        assert export["se"][idx] == pytest.approx(
            float(ref.loc[term, "se"]), abs=1e-4
        )

    fit = pd.read_csv(tmp_path / "fit.csv").iloc[0]
    assert export["sigma2"] == pytest.approx(float(fit["sigma2"]), abs=2e-5)
    assert export["loglikelihood"] == pytest.approx(float(fit["loglik"]), abs=1e-3)
    assert export["aic"] == pytest.approx(float(fit["aic"]), abs=2e-3)


X = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=float)
Y = np.array([1.0, 2.2, 1.8, 2.7, 3.1, 2.9, 4.2, 4.0], dtype=float)


def test_isotonic_matches_r_isoreg(tmp_path):
    _require_r()
    pd.DataFrame({"x": X, "y": Y}).to_csv(tmp_path / "iso.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'iso.csv'}")
    up <- isoreg(d$x, d$y)
    down <- isoreg(d$x, -d$y)
    write.csv(data.frame(x=d$x, fitted=up$yf), "{tmp_path / 'up.csv'}",
              row.names=FALSE)
    write.csv(data.frame(x=d$x, fitted=-down$yf), "{tmp_path / 'down.csv'}",
              row.names=FALSE)
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    up = _run(
        IsotonicStep(),
        {"x_label": "x", "y_label": "y", "increasing": True, "output": "up"},
        _form(np.column_stack([X, Y])),
    )
    down = _run(
        IsotonicStep(),
        {"x_label": "x", "y_label": "y", "increasing": False, "output": "down"},
        _form(np.column_stack([X, Y])),
    )
    expected_up = pd.read_csv(tmp_path / "up.csv")["fitted"].to_numpy()
    expected_down = pd.read_csv(tmp_path / "down.csv")["fitted"].to_numpy()
    np.testing.assert_allclose(up["fitted"], expected_up, rtol=0, atol=1e-12)
    np.testing.assert_allclose(down["fitted"], expected_down, rtol=0, atol=1e-12)
