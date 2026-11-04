"""R oracle checks for the 1.4.0 causal operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.iptw_effect import IptwEffectStep
from src.task.step.steps.rdd import RddStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

R_CODE = """
args <- commandArgs(trailingOnly = TRUE)
d <- read.csv(args[1])
fit <- glm(t ~ c1 + c2, data = d, family = binomial())
p <- fit$fitted.values
w <- ifelse(d$t == 1, 1 / p, 1 / (1 - p))
est <- weighted.mean(d$y[d$t == 1], w[d$t == 1]) - weighted.mean(d$y[d$t == 0], w[d$t == 0])
X <- cbind(1, d$t)
WX <- X * w
bread <- solve(t(X) %*% WX)
beta <- bread %*% (t(WX) %*% d$y)
e <- as.numeric(d$y - X %*% beta)
meat <- t(X) %*% (X * (w^2 * e^2))
V <- bread %*% meat %*% bread
cat("iptw", sprintf("%.12f", est), sprintf("%.12f", sqrt(V[2, 2])), fill = TRUE)
suppressMessages(library(rdrobust))
r <- rdrobust(d$yr, d$xr, c = 0, h = 0.5, b = 0.5, p = 1, kernel = "triangular", vce = "hc0")
cat("rdd", sprintf("%.12f", r$Estimate[1, 1]), sprintf("%.12f", r$se[1]), fill = TRUE)
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _call(step, params, columns):
    names = list(columns)
    data = np.column_stack([columns[name] for name in names])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{index}": index for index in range(data.shape[0])},
            "feature": {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    ctx = Ctx(params)
    step.run(ctx, [form])
    out = ctx["output"]
    stats = [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])]
    return dict(zip(stats, out.data[:, 0]))


def _fixture(n=400):
    rng = np.random.default_rng(20261101)
    c1 = rng.normal(size=n)
    c2 = rng.normal(size=n)
    propensity = 1.0 / (1.0 + np.exp(-(0.7 * c1 - 0.5 * c2)))
    treatment = (rng.random(n) < propensity).astype(float)
    outcome = 1.0 + 1.4 * treatment + 0.9 * c1 - 0.6 * c2 + rng.normal(0, 0.5, n)
    xr = rng.uniform(-1.0, 1.0, n)
    yr = 0.3 + 0.7 * xr + 0.9 * (xr >= 0.0) + rng.normal(0, 0.4, n)
    return {"t": treatment, "y": outcome, "c1": c1, "c2": c2, "xr": xr, "yr": yr}


def test_causal_operators_match_r(tmp_path):
    data = _fixture()
    csv_path = tmp_path / "fixture.csv"
    np.savetxt(
        csv_path,
        np.column_stack([data[name] for name in ("t", "y", "c1", "c2", "xr", "yr")]),
        delimiter=",",
        header="t,y,c1,c2,xr,yr",
        comments="",
        fmt="%.17g",
    )
    script = tmp_path / "oracle.R"
    script.write_text(R_CODE)
    result = subprocess.run(
        [RSCRIPT, str(script), str(csv_path)],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    values = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            values[parts[0]] = (float(parts[1]), float(parts[2]))
    assert set(values) == {"iptw", "rdd"}, result.stdout

    iptw = _call(
        IptwEffectStep(),
        {"output": "output", "treatment_label": "t", "outcome_label": "y",
         "covariate_labels": ["c1", "c2"]},
        data,
    )
    assert abs(iptw["effect"] - values["iptw"][0]) <= 1e-5
    assert abs(iptw["se"] - values["iptw"][1]) <= 1e-5

    rdd = _call(
        RddStep(),
        {"output": "output", "running_label": "xr", "outcome_label": "yr",
         "bandwidth": 0.5},
        data,
    )
    assert abs(rdd["tau"] - values["rdd"][0]) <= 1e-8
    assert abs(rdd["se"] - values["rdd"][1]) <= 1e-8
