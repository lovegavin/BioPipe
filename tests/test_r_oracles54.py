"""Authoritative R checks for 0.70 cointegration operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.engle_granger import EngleGrangerStep
from src.task.step.steps.johansen import JohansenStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _fixture():
    rng = np.random.default_rng(20261031)
    x = np.cumsum(rng.normal(size=160))
    y = 1.5 * x + rng.normal(scale=0.6, size=160)
    return y, x


def _form(y, x):
    data = np.column_stack([y, x])
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"y": 0, "x": 1},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript is unavailable")
def test_cointegration_matches_urca(tmp_path):
    y, x = _fixture()
    data = tmp_path / "coint.csv"
    np.savetxt(data, np.column_stack([y, x]), fmt="%.17g", delimiter=",")

    oracle = tmp_path / "coint.R"
    oracle.write_text(
        "suppressPackageStartupMessages(library(urca))\n"
        "d <- read.csv('" + str(data) + "', header=FALSE)\n"
        "res <- residuals(lm(V1 ~ V2, data=d))\n"
        "u <- ur.df(res, type='none', lags=2)\n"
        "cat(sprintf('%.17g', u@teststat[1]), '\\n')\n"
        "j <- ca.jo(d[, c('V1','V2')], type='trace', ecdet='none', K=2, spec='longrun')\n"
        "cat(paste(sprintf('%.17g', rev(as.numeric(j@teststat))), collapse=' '), '\\n')\n"
        "je <- ca.jo(d[, c('V1','V2')], type='eigen', ecdet='none', K=2, spec='longrun')\n"
        "cat(paste(sprintf('%.17g', rev(as.numeric(je@teststat))), collapse=' '), '\\n')\n"
        "cat(paste(sprintf('%.17g', j@lambda[1:2]), collapse=' '), '\\n')\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["Rscript", str(oracle)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 4, proc.stdout + proc.stderr

    ctx = Ctx({"y_label": "y", "x_label": "x", "lags": 2})
    eg = EngleGrangerStep()
    eg.run(ctx, [_form(y, x)])
    eg_result = eg.export(ctx)
    assert eg_result["statistic"] == pytest.approx(float(lines[0]), rel=1e-10)

    ctx = Ctx({"det_order": 0, "k_ar_diff": 1})
    joh = JohansenStep()
    joh.run(ctx, [_form(y, x)])
    result = joh.export(ctx)
    trace = np.asarray(result["trace"])
    max_eig = np.asarray(result["max_eig"])
    eigenvalues = np.asarray(result["eigenvalues"])
    assert np.allclose(trace, np.fromstring(lines[1], sep=" "), rtol=1e-10, atol=1e-10)
    assert np.allclose(max_eig, np.fromstring(lines[2], sep=" "), rtol=1e-10, atol=1e-10)
    assert np.allclose(eigenvalues, np.fromstring(lines[3], sep=" "), rtol=1e-10, atol=1e-10)
