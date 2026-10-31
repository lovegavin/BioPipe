"""R oracle check for 0.90 Fine-Gray subdistribution regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.fine_gray import FineGrayStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels):
    values = np.asarray(values, dtype=float)
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


def test_fine_gray_matches_r_cmprsk(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("cmprsk", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip("R package cmprsk is not available")

    rng = np.random.default_rng(20261114)
    n = 240
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    t1 = rng.exponential(scale=1.0 / (0.22 * np.exp(0.7 * x1 - 0.35 * x2)))
    t2 = rng.exponential(scale=1.0 / (0.12 * np.exp(-0.45 * x1 + 0.5 * x2)))
    tc = rng.exponential(scale=1.0 / 0.08, size=n)
    time = np.minimum(np.minimum(t1, t2), tc)
    status = np.where(time == t1, 1, np.where(time == t2, 2, 0))
    frame = pd.DataFrame({"time": time, "status": status, "x1": x1, "x2": x2})
    frame.to_csv(tmp_path / "fg.csv", index=False)

    script = f"""
    suppressPackageStartupMessages(library(cmprsk))
    d <- read.csv("{tmp_path / 'fg.csv'}")
    fit <- cmprsk::crr(
        ftime = as.numeric(d[["time"]]),
        fstatus = as.integer(d[["status"]]),
        cov1 = as.matrix(d[, c("x1", "x2")]),
        failcode = 1,
        cencode = 0
    )
    write.csv(
        data.frame(
            term = names(fit[["coef"]]),
            coef = as.numeric(fit[["coef"]]),
            se = sqrt(diag(fit[["var"]])),
            loglik = as.numeric(fit[["loglik"]])
        ),
        "{tmp_path / 'fit.csv'}",
        row.names = FALSE
    )
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    export, out = _run(
        FineGrayStep(),
        {
            "time_label": "time",
            "event_label": "status",
            "covariates": ["x1", "x2"],
            "output": "fg",
        },
        _form(np.column_stack([time, status, x1, x2]), ("time", "status", "x1", "x2")),
    )
    reference = pd.read_csv(tmp_path / "fit.csv")
    assert reference["term"].tolist() == ["x1", "x2"]
    np.testing.assert_allclose(
        out.data[:, 0], reference["coef"].to_numpy(), rtol=0, atol=5e-5
    )
    np.testing.assert_allclose(
        out.data[:, 2], reference["se"].to_numpy(), rtol=0, atol=5e-5
    )
    assert export["loglik"] == pytest.approx(float(reference["loglik"].iloc[0]), abs=1e-5)
    assert export["n"] == 240
    assert export["n_events"] == 109
    assert export["n_competing"] == 80
