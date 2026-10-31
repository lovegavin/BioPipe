"""R oracle for interval-censored Weibull AFT regression."""
from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.interval_censored_regression import (
    IntervalCensoredRegressionStep,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _fixture():
    rng = np.random.default_rng(20261122)
    n = 160
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    w = np.log(-np.log(rng.uniform(size=n)))
    time = np.exp(1.0 + 0.3 * x1 - 0.2 * x2 + 0.5 * w)
    grid = np.arange(0, 11, dtype=float)
    lower = np.empty(n)
    upper = np.empty(n)
    for index, value in enumerate(time):
        if value <= grid[1]:
            lower[index] = 1e-6
            upper[index] = grid[1]
        elif value > grid[-1]:
            lower[index] = grid[-1]
            upper[index] = np.inf
        else:
            k = int(np.floor(value))
            lower[index] = k
            upper[index] = k + 1
    return x1, x2, lower, upper


def test_interval_censored_matches_r_survreg(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    x1, x2, lower, upper = _fixture()
    data_path = tmp_path / "data.csv"
    coef_path = tmp_path / "coef.csv"
    loglik_path = tmp_path / "loglik.txt"
    script_path = tmp_path / "fit.R"
    with data_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x1", "x2", "lower", "upper"])
        for index in range(x1.size):
            writer.writerow([x1[index], x2[index], lower[index], upper[index]])

    script = f"""
library(survival)
d <- read.csv("{data_path}", check.names=FALSE)
fit <- survreg(Surv(lower, upper, type="interval2") ~ x1 + x2,
               data=d, dist="weibull")
s <- summary(fit)
out <- data.frame(term=rownames(s$table), value=s$table[,1],
                  se=s$table[,2], check.names=FALSE)
write.csv(out, "{coef_path}", row.names=FALSE)
writeLines(sprintf("%.17g", fit[["loglik"]][2]), "{loglik_path}")
"""
    script_path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        ["Rscript", str(script_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    reference = {}
    with coef_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            reference[row["term"]] = (
                float(row["value"]),
                float(row["se"]),
            )
    r_loglik = float(loglik_path.read_text(encoding="utf-8").strip())

    names = ["x1", "x2", "lower", "upper"]
    frame = Form(
        data=np.column_stack([x1, x2, lower, upper]),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(x1.size)},
            "feature": {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    frame.validate()
    step = IntervalCensoredRegressionStep()
    ctx = Ctx(
        {
            "time_lower_label": "lower",
            "time_upper_label": "upper",
            "covariates": ["x1", "x2"],
            "output": "fit",
        }
    )
    step.run(ctx, [frame])
    export = step.export(ctx)

    mapping = {
        "Intercept": "(Intercept)",
        "x1": "x1",
        "x2": "x2",
        "log_scale": "Log(scale)",
    }
    for internal, external in mapping.items():
        ref_value, ref_se = reference[external]
        index = export["terms"].index(internal)
        assert export["coefficients"][index] == pytest.approx(
            ref_value, abs=1e-5
        )
        assert export["standard_errors"][index] == pytest.approx(
            ref_se, abs=2e-5
        )
    assert export["loglik"] == pytest.approx(r_loglik, abs=1e-5)
    assert export["scale"] == pytest.approx(
        float(np.exp(reference["Log(scale)"][0])), abs=1e-5
    )
