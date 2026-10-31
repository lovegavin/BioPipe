"""Authoritative R checks for the 0.27 time-series/count operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.adf_test import AdfTestStep
from src.task.step.steps.kpss_test import KpssTestStep
from src.task.step.steps.negative_binomial_regression import NegativeBinomialRegressionStep
from src.task.step.steps.poisson_regression import PoissonRegressionStep


RSCRIPT = shutil.which("Rscript")
AR1 = np.array([
    0.0000000000, 0.3047170798, -0.8571538584, 0.2361588808, 1.0822600449,
    -1.3016791617, -2.0831870039, -1.1220717992, -0.9894856718, -0.6104925606,
    -1.2193394639, 0.1477942965, 0.8664685133, 0.5859118056, 1.4787882903,
    1.3547823164, -0.0464230730, 0.3408969403, -0.7543444367, 0.4258436393,
    0.2055802726, -0.0615142000, -0.7178380644, 0.7918385000, 0.3205736180,
    -0.2359836514, -0.4937237413, 0.2360749408, 0.5070890288, 0.7169860289,
    0.8610126203, 2.6582551731, 1.1885380875, 0.2008801234, -0.6932446542,
    0.2000326301, 1.2489918708, 0.6354476648, -0.4588878781, -1.0998139425,
    -0.0092955777, 0.7376768246, 0.9857603631, -0.0740534895, 0.1877292294,
    0.2293233468, 0.3562826048, 1.0851983408, 0.8747145533, 1.2037422950,
    0.7898244465, 0.7630140666, 1.0890966658, -0.8036978204, -0.8018899086,
    -0.9515065994, -1.2097818079, -1.0010113360, 0.8943345097, -0.3292304099,
], dtype=np.float64)
COUNT_X = np.linspace(-1, 1, 40)
COUNT_Y = np.array([
    1, 0, 2, 1, 0, 0, 0, 2, 0, 0, 1, 3, 0, 1, 1, 3, 1, 5, 6, 2,
    5, 0, 0, 3, 3, 2, 4, 0, 9, 2, 10, 14, 2, 1, 4, 3, 2, 3, 6, 7,
], dtype=np.float64)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _r_values():
    x = ", ".join(f"{value:.10f}" for value in AR1)
    y = ", ".join(f"{value:.10f}" for value in COUNT_Y)
    script = f"""
suppressPackageStartupMessages({{library(tseries); library(MASS)}})
x <- c({x})
a <- suppressWarnings(adf.test(x, k = 2))
k <- suppressWarnings(kpss.test(x, null = "Level", lshort = TRUE))
cat("ADF", sprintf("%.10f", a[["statistic"]]), sprintf("%.10f", a[["p.value"]]), a[["parameter"]], "\\n")
cat("KPSS", sprintf("%.10f", k[["statistic"]]), sprintf("%.10f", k[["p.value"]]), k[["parameter"]], "\\n")
xx <- seq(-1, 1, length.out = 40)
y <- c({y})
p <- glm(y ~ xx, family = poisson)
nb <- MASS::glm.nb(y ~ xx)
cat("POIS", paste(sprintf("%.10f", coef(p)), collapse = ","), "\\n")
cat("NB", paste(sprintf("%.10f", coef(nb)), collapse = ","), sprintf("%.10f", nb[["theta"]]), "\\n")
"""
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        missing = "there is no package called" in proc.stderr
        if missing:
            pytest.skip(f"R tseries/MASS unavailable: {proc.stderr.strip()[:300]}")
        pytest.fail(f"R 0.27 oracle failed:\n{proc.stderr}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] in {"ADF", "KPSS"}:
            values[parts[0]] = [float(value) for value in parts[1:-1]] + [int(float(parts[-1]))]
        elif parts[0] in {"POIS", "NB"}:
            values[parts[0]] = [float(value) for value in parts[1].split(",")]
            if parts[0] == "NB":
                values["THETA"] = float(parts[2])
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_diagnostics_match_r():
    r = _r_values()
    series = _form(
        AR1.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(len(AR1))]), "feature": {"x": 0}},
    )
    ctx = Ctx({"value_label": "x", "lags": 2})
    adf = AdfTestStep()
    adf.run(ctx, [series])
    # R's adf.test table is coarser and caps p at 0.01 for this fixture;
    # the Dickey-Fuller statistic and lag must match exactly.
    assert adf.export(ctx)["statistic"] == pytest.approx(r["ADF"][0], abs=2e-5)
    assert adf.export(ctx)["used_lag"] == r["ADF"][2]
    assert abs(adf.export(ctx)["p"] - r["ADF"][1]) < 0.02

    ctx = Ctx({"value_label": "x", "lags": 3})
    kpss = KpssTestStep()
    kpss.run(ctx, [series])
    assert kpss.export(ctx)["statistic"] == pytest.approx(r["KPSS"][0], abs=2e-5)
    assert kpss.export(ctx)["lags"] == r["KPSS"][2]

    counts = _form(
        np.column_stack([COUNT_X, COUNT_Y]),
        ["sample", "feature"],
        {
            "sample": _labels([f"s{i}" for i in range(len(COUNT_X))]),
            "feature": {"x": 0, "y": 1},
        },
    )
    ctx = Ctx({"response_label": "y", "predictors": ["x"]})
    poisson = PoissonRegressionStep()
    poisson.run(ctx, [counts])
    assert np.allclose(poisson.export(ctx)["coef"], r["POIS"], atol=2e-6)

    ctx = Ctx({"response_label": "y", "predictors": ["x"]})
    nb = NegativeBinomialRegressionStep()
    nb.run(ctx, [counts])
    assert np.allclose(nb.export(ctx)["coef"], r["NB"], atol=2e-5)
    assert nb.export(ctx)["alpha"] == pytest.approx(1 / r["THETA"], rel=3e-4)
