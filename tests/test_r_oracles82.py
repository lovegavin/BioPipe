"""R oracle for conditional logistic regression."""
from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.conditional_logistic import (
    ConditionalLogisticStep,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _fixture():
    rng = np.random.default_rng(20261123)
    rows = []
    for stratum in range(60):
        x1 = rng.normal(0, 1, 2)
        x2 = rng.normal(0, 1, 2)
        eta = 0.8 * x1 - 0.5 * x2
        probability = 1.0 / (1.0 + np.exp(-(eta[0] - eta[1])))
        case = 0 if rng.random() < probability else 1
        for j in range(2):
            rows.append((stratum, int(j == case), x1[j], x2[j]))
    return np.asarray(rows, dtype=np.float64)


def test_conditional_logistic_matches_r_clogit(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    values = _fixture()
    data_path = tmp_path / "data.csv"
    coef_path = tmp_path / "coef.csv"
    loglik_path = tmp_path / "loglik.txt"
    script_path = tmp_path / "fit.R"
    with data_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stratum", "y", "x1", "x2"])
        writer.writerows(values.tolist())

    script = f"""
library(survival)
d <- read.csv("{data_path}", check.names=FALSE)
fit <- clogit(y ~ x1 + x2 + strata(stratum), data=d)
out <- data.frame(term=names(fit$coefficients),
                  coef=as.numeric(fit$coefficients),
                  se=sqrt(diag(fit$var)),
                  check.names=FALSE)
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
                float(row["coef"]),
                float(row["se"]),
            )
    r_loglik = float(loglik_path.read_text(encoding="utf-8").strip())

    names = ["stratum", "y", "x1", "x2"]
    frame = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    frame.validate()
    step = ConditionalLogisticStep()
    ctx = Ctx(
        {
            "stratum_label": "stratum",
            "outcome_label": "y",
            "covariates": ["x1", "x2"],
            "output": "fit",
        }
    )
    step.run(ctx, [frame])
    export = step.export(ctx)
    for name in ("x1", "x2"):
        index = export["terms"].index(name)
        ref_coef, ref_se = reference[name]
        assert export["coef"][index] == pytest.approx(ref_coef, abs=1e-6)
        assert export["se"][index] == pytest.approx(ref_se, abs=1e-6)
    assert export["loglikelihood"] == pytest.approx(r_loglik, abs=1e-8)
