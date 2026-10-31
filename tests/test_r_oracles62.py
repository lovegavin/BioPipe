"""R oracle checks for 0.78 beta regression and redundancy analysis."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.beta_regression import BetaRegressionStep
from src.task.step.steps.redundancy_analysis import RedundancyAnalysisStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _frame(values, names):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _beta_fixture():
    rng = np.random.default_rng(20261106)
    n = 80
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    eta = 0.5 + 0.8 * x1 - 0.5 * x2
    mu = 1.0 / (1.0 + np.exp(-eta))
    phi = 8.0
    y = rng.beta(mu * phi, (1.0 - mu) * phi)
    return np.column_stack([y, x1, x2])


def _rda_fixture():
    rng = np.random.default_rng(20261107)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = np.column_stack(
        [
            1.2 * x1 - 0.7 * x2 + rng.normal(scale=0.8, size=n),
            -0.8 * x1 + 0.9 * x2 + rng.normal(scale=0.7, size=n),
            0.4 * x1 + rng.normal(scale=1.0, size=n),
            rng.normal(size=n),
        ]
    )
    return y, np.column_stack([x1, x2])


def _require_r_package(package: str) -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", f'cat(requireNamespace("{package}", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip(f"R {package} is not available")


def test_beta_regression_matches_r_betareg(tmp_path):
    _require_r_package("betareg")
    data = _beta_fixture()
    pd.DataFrame(data, columns=["y", "x1", "x2"]).to_csv(
        tmp_path / "beta.csv", index=False
    )
    script = f"""
suppressPackageStartupMessages(library(betareg))
base <- "{tmp_path.as_posix()}"
d <- read.csv(file.path(base, "beta.csv"))
f <- betareg(y ~ x1 + x2, data = d)
s <- summary(f)[["coefficients"]]
out <- data.frame(
    term = c("Intercept", "x1", "x2", "phi"),
    coef = c(coef(f)[1:3], coef(f)[4]),
    se = c(s[["mean"]][, 2], s[["precision"]][, 2]),
    loglik = as.numeric(logLik(f))
)
write.csv(out, file.path(base, "beta_ref.csv"), row.names = FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "beta_ref.csv")

    export, _ = _run(
        BetaRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "beta"},
        [_frame(data, ["y", "x1", "x2"])],
    )
    terms = ["Intercept", "x1", "x2", "phi"]
    for index, term in enumerate(terms):
        expected = reference.loc[reference["term"] == term].iloc[0]
        assert export["coef"][index] == pytest.approx(
            float(expected["coef"]), abs=2e-5
        )
        assert export["se"][index] == pytest.approx(
            float(expected["se"]), abs=2e-6
        )
    assert export["llf"] == pytest.approx(
        float(reference["loglik"].iloc[0]), abs=1e-7
    )


def test_redundancy_analysis_matches_r_vegan(tmp_path):
    _require_r_package("vegan")
    y, x = _rda_fixture()
    frame = pd.DataFrame(y, columns=["y1", "y2", "y3", "y4"])
    frame[["x1", "x2"]] = x
    frame.to_csv(tmp_path / "rda.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(vegan))
base <- "{tmp_path.as_posix()}"
d <- read.csv(file.path(base, "rda.csv"))
f <- rda(d[, c("y1", "y2", "y3", "y4")] ~ x1 + x2, data = d)
out <- data.frame(
    total = f[["tot.chi"]],
    eig1 = f[["CCA"]][["eig"]][1],
    eig2 = f[["CCA"]][["eig"]][2]
)
write.csv(out, file.path(base, "rda_ref.csv"), row.names = FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "rda_ref.csv").iloc[0]

    export, _ = _run(
        RedundancyAnalysisStep(),
        {
            "response_dim": "feature",
            "predictor_dim": "feature",
            "n_components": 2,
            "output": "rda",
        },
        [_frame(y, ["y1", "y2", "y3", "y4"]), _frame(x, ["x1", "x2"])],
    )
    assert export["total_inertia"] == pytest.approx(
        float(reference["total"]), abs=1e-12
    )
    assert export["eigenvalues"][0] == pytest.approx(
        float(reference["eig1"]), abs=1e-12
    )
    assert export["eigenvalues"][1] == pytest.approx(
        float(reference["eig2"]), abs=1e-12
    )
