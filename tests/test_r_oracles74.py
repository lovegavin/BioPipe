"""R oracle check for 0.93 probit regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.core import Form
from src.task.step.steps.probit_regression import ProbitRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(frame: pd.DataFrame):
    data = frame.to_numpy(dtype=float)
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(frame.columns)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture() -> pd.DataFrame:
    rng = np.random.default_rng(20261116)
    n = 180
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    eta = -0.3 + 0.8 * x1 - 0.5 * x2
    y = rng.binomial(1, norm.cdf(eta))
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def test_probit_matches_r_glm(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    frame = _fixture()
    frame.to_csv(tmp_path / "probit.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'probit.csv'}")
    fit <- glm(y ~ x1 + x2, data=d, family=binomial(link="probit"))
    write.csv(data.frame(term=names(coef(fit)),
                         estimate=as.numeric(coef(fit)),
                         se=as.numeric(sqrt(diag(vcov(fit))))),
              "{tmp_path / 'coef.csv'}", row.names=FALSE)
    write.csv(data.frame(loglik=as.numeric(logLik(fit)), aic=AIC(fit)),
              "{tmp_path / 'fit.csv'}", row.names=FALSE)
    """
    subprocess.run(
        ["Rscript", "-e", script], check=True, capture_output=True, text=True
    )

    export = _run(
        ProbitRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "fit"},
        _form(frame),
    )
    ref = pd.read_csv(tmp_path / "coef.csv").set_index("term")
    for term in ("(Intercept)", "x1", "x2"):
        py_term = "Intercept" if term == "(Intercept)" else term
        idx = export["terms"].index(py_term)
        assert export["coef"][idx] == pytest.approx(
            float(ref.loc[term, "estimate"]), abs=3e-5
        )
        assert export["se"][idx] == pytest.approx(
            float(ref.loc[term, "se"]), abs=3e-5
        )
    fit = pd.read_csv(tmp_path / "fit.csv").iloc[0]
    assert export["loglikelihood"] == pytest.approx(float(fit["loglik"]), abs=1e-4)
    assert export["aic"] == pytest.approx(float(fit["aic"]), abs=2e-4)
