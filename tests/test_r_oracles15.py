"""R oracle checks for the 0.30 regression models."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.conditional_logit import ConditionalLogitStep
from src.task.step.steps.multinomial_logit import MultinomialLogitStep
from src.task.step.steps.robust_regression import RobustRegressionStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(columns, names):
    data = np.column_stack(columns).astype(np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, data):
    ctx = Ctx(params)
    step.run(ctx, [data])
    return step.export(ctx)


def _multinomial():
    rng = np.random.default_rng(42)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    linear = np.column_stack([0.5 * x1 - 0.2 * x2, -0.3 * x1 + 0.7 * x2])
    prob = np.exp(linear)
    prob = np.column_stack([np.ones(n), prob])
    prob /= prob.sum(axis=1, keepdims=True)
    y = np.asarray([rng.choice([1, 2, 3], p=prob[i]) for i in range(n)])
    return y, x1, x2


def _conditional():
    rng = np.random.default_rng(7)
    groups = np.repeat(np.arange(1, 21), 3)
    x = rng.normal(size=(60, 2))
    eta = 0.8 * x[:, 0] - 0.4 * x[:, 1]
    choice = np.zeros(60)
    for group in range(20):
        index = np.where(groups == group + 1)[0]
        probability = np.exp(eta[index])
        probability /= probability.sum()
        choice[rng.choice(index, p=probability)] = 1
    return choice, x, groups


def _robust():
    rng = np.random.default_rng(8)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1 + 2 * x1 - 0.5 * x2 + rng.normal(scale=0.3, size=n)
    y[0] += 20
    return y, x1, x2


def test_regression30_matches_r(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript unavailable")
    probe = subprocess.run(
        [
            "Rscript",
            "-e",
            "cat(requireNamespace('nnet',quietly=TRUE),"
            "requireNamespace('survival',quietly=TRUE),"
            "requireNamespace('MASS',quietly=TRUE))",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout.strip().replace(" ", "") != "TRUETRUETRUE":
        pytest.skip(f"R oracle packages unavailable: {probe.stdout.strip()}")

    y, x1, x2 = _multinomial()
    pd.DataFrame({"y": y, "x1": x1, "x2": x2}).to_csv(
        tmp_path / "mn.csv", index=False
    )
    mn_info = _run(
        MultinomialLogitStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _form([y, x1, x2], ["y", "x1", "x2"]),
    )

    choice, x, groups = _conditional()
    pd.DataFrame(
        {"y": choice, "x1": x[:, 0], "x2": x[:, 1], "stratum": groups}
    ).to_csv(tmp_path / "cl.csv", index=False)
    cl_info = _run(
        ConditionalLogitStep(),
        {
            "stratum_label": "stratum",
            "event_label": "y",
            "predictors": ["x1", "x2"],
        },
        _form([choice, x[:, 0], x[:, 1], groups], ["y", "x1", "x2", "stratum"]),
    )

    y, x1, x2 = _robust()
    pd.DataFrame({"y": y, "x1": x1, "x2": x2}).to_csv(
        tmp_path / "rlm.csv", index=False
    )
    rlm_info = _run(
        RobustRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _form([y, x1, x2], ["y", "x1", "x2"]),
    )

    script = r"""
suppressPackageStartupMessages(library(nnet))
suppressPackageStartupMessages(library(survival))
suppressPackageStartupMessages(library(MASS))
d <- read.csv(commandArgs(TRUE)[1])
m <- multinom(factor(y) ~ x1 + x2, data=d, trace=FALSE)
cat("MN", paste(sprintf("%.10f", as.vector(coef(m))), collapse=","), "\n")
d <- read.csv(commandArgs(TRUE)[2])
c <- clogit(y ~ x1 + x2 + strata(stratum), data=d)
cat("CL", paste(sprintf("%.10f", coef(c)), collapse=","), "\n")
cat("CLSE", paste(sprintf("%.10f", sqrt(diag(vcov(c)))), collapse=","), "\n")
d <- read.csv(commandArgs(TRUE)[3])
r <- rlm(y ~ x1 + x2, data=d, psi=psi.huber)
cat("RLM", paste(sprintf("%.10f", coef(r)), collapse=","), "\n")
cat("RLMSE", paste(sprintf("%.10f", sqrt(diag(vcov(r)))), collapse=","), "\n")
cat("RLMSCALE", sprintf("%.10f", r$s), "\n")
"""
    result = subprocess.run(
        [
            "Rscript",
            "-e",
            script,
            str(tmp_path / "mn.csv"),
            str(tmp_path / "cl.csv"),
            str(tmp_path / "rlm.csv"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    parsed = {}
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0]] = [float(value) for value in parts[1].split(",")]

    assert np.allclose(
        np.asarray(mn_info["coef"]).ravel(),
        parsed["MN"],
        atol=1e-4,
    )
    assert cl_info["coef"] == pytest.approx(parsed["CL"], abs=1e-4)
    assert cl_info["se"] == pytest.approx(parsed["CLSE"], abs=1e-4)
    assert rlm_info["coef"] == pytest.approx(parsed["RLM"], abs=1e-4)
    assert rlm_info["se"] == pytest.approx(parsed["RLMSE"], abs=1e-4)
    assert rlm_info["scale"] == pytest.approx(parsed["RLMSCALE"][0], abs=1e-4)
