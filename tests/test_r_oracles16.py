"""R oracle checks for 0.31 gamma and zero-inflated regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.gamma_regression import GammaRegressionStep
from src.task.step.steps.zero_inflated_poisson import ZeroInflatedPoissonStep


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


def _zero_data():
    rng = np.random.default_rng(42)
    n = 300
    x = rng.normal(size=n)
    z = rng.normal(size=n)
    probability = 1.0 / (1.0 + np.exp(-(-1.0 + 1.2 * z)))
    y = rng.poisson(np.exp(1.0 + 0.4 * x))
    y[rng.random(n) < probability] = 0
    return y, x, z


def _gamma_data():
    rng = np.random.default_rng(13)
    n = 120
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.5 + 0.3 * x1 - 0.2 * x2)
    y = rng.gamma(shape=2.0, scale=mu / 2.0)
    return y, x1, x2


def test_regression31_matches_r(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript unavailable")
    probe = subprocess.run(
        ["Rscript", "-e", "cat(requireNamespace('pscl',quietly=TRUE))"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip(f"R oracle package unavailable: {probe.stdout.strip()}")

    y, x, z = _zero_data()
    pd.DataFrame({"y": y, "x": x, "z": z}).to_csv(
        tmp_path / "zero.csv", index=False
    )
    z_info = _run(
        ZeroInflatedPoissonStep(),
        {
            "response_label": "y",
            "count_predictors": ["x"],
            "zero_predictors": ["z"],
        },
        _form([y, x, z], ["y", "x", "z"]),
    )

    y, x1, x2 = _gamma_data()
    pd.DataFrame({"y": y, "x1": x1, "x2": x2}).to_csv(
        tmp_path / "gamma.csv", index=False
    )
    g_info = _run(
        GammaRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _form([y, x1, x2], ["y", "x1", "x2"]),
    )

    script = r"""
suppressPackageStartupMessages(library(pscl))
z <- read.csv(commandArgs(TRUE)[1])
m <- zeroinfl(y ~ x | z, data=z, dist="poisson")
cat("Z", paste(sprintf("%.10f", coef(m)), collapse=","), "\n")
d <- read.csv(commandArgs(TRUE)[2])
g <- glm(y ~ x1 + x2, data=d, family=Gamma(link="log"))
cat("G", paste(sprintf("%.10f", coef(g)), collapse=","), "\n")
cat("GSE", paste(sprintf("%.10f", sqrt(diag(vcov(g)))), collapse=","), "\n")
"""
    result = subprocess.run(
        [
            "Rscript",
            "-e",
            script,
            str(tmp_path / "zero.csv"),
            str(tmp_path / "gamma.csv"),
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

    assert z_info["count_coef"] == pytest.approx(parsed["Z"][:2], abs=1e-4)
    assert z_info["zero_coef"] == pytest.approx(parsed["Z"][2:], abs=1e-4)
    assert g_info["coef"] == pytest.approx(parsed["G"], abs=1e-4)
    assert g_info["se"] == pytest.approx(parsed["GSE"], abs=1e-4)
