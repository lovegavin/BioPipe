"""Authoritative R checks for the 0.25 regression/time-series diagnostics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.chow_test import ChowTestStep
from src.task.step.steps.ljung_box import LjungBoxStep
from src.task.step.steps.white_test import WhiteTestStep


RSCRIPT = shutil.which("Rscript")
X1 = np.arange(1, 21, dtype=np.float32)
X2 = np.tile(np.array([0.0, 1.0], dtype=np.float32), 10)
RESID = np.array(
    [-1, 1, -1.5, 1.5, -2, 2, -2.5, 2.5, -3, 3, -1.2, 1.2, -1.7, 1.7, -2.2, 2.2, -2.7, 2.7, -3.2, 3.2],
    dtype=np.float32,
)
Y_WHITE = (2.0 + 1.5 * X1 + 0.5 * X2 + RESID).astype(np.float32)
Y_CHOW = np.concatenate([
    1.0 + 2.0 * X1[:10] + RESID[:10],
    5.0 + 0.5 * X1[10:] + RESID[10:],
]).astype(np.float32)
SERIES = np.array([1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 8, 7, 9, 8, 10, 9, 11], dtype=np.float32)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form() -> Form:
    form = Form(
        np.column_stack([Y_WHITE, Y_CHOW, X1, X1, X2, SERIES]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {
                "y_white": 0,
                "y_chow": 1,
                "x": 2,
                "x1": 3,
                "x2": 4,
                "series": 5,
            },
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _r_values():
    script = """
x1 <- 1:20
x2 <- rep(c(0,1),10)
resid <- c(-1,1,-1.5,1.5,-2,2,-2.5,2.5,-3,3,-1.2,1.2,-1.7,1.7,-2.2,2.2,-2.7,2.7,-3.2,3.2)
y <- 2 + 1.5*x1 + 0.5*x2 + resid
fit <- lm(y ~ x1 + x2)
e2 <- resid(fit)^2
aux <- lm(e2 ~ x1 + x2 + I(x1^2) + I(x2^2) + I(x1*x2))
r2 <- summary(aux)$r.squared
n <- length(y); k <- 5
lmstat <- n*r2
p_lm <- pchisq(lmstat, k, lower.tail=FALSE)
fstat <- (r2/k)/((1-r2)/(n-k-1))
p_f <- pf(fstat, k, n-k-1, lower.tail=FALSE)
cat("WHITE", sprintf("%.10f", c(lmstat, p_lm, fstat, p_f)), "\\n")

x <- 1:20
y2 <- c(1 + 2*x[1:10], 5 + 0.5*x[11:20]) + c(-1,1,-1.5,1.5,-2,2,-2.5,2.5,-3,3, -1.2,1.2,-1.7,1.7,-2.2,2.2,-2.7,2.7,-3.2,3.2)
fit2 <- lm(y2 ~ x)
rssp <- sum(resid(fit2)^2)
fit1 <- lm(y2[1:10] ~ x[1:10])
fit3 <- lm(y2[11:20] ~ x[11:20])
rss1 <- sum(resid(fit1)^2); rss2 <- sum(resid(fit3)^2)
k2 <- 2; df2 <- 20 - 2*k2
f2 <- ((rssp-rss1-rss2)/k2)/((rss1+rss2)/df2)
p2 <- pf(f2, k2, df2, lower.tail=FALSE)
cat("CHOW", sprintf("%.10f", c(f2, p2, rssp, rss1, rss2)), "\\n")

x3 <- c(1,2,1,3,2,4,3,5,4,6,5,7,6,8,7,9,8,10,9,11)
bt <- Box.test(x3, lag=5, type="Ljung-Box")
cat("LJUNG", sprintf("%.10f", c(bt$statistic, bt$p.value)), "\\n")
"""
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(f"R 0.25 diagnostics oracle failed:\n{proc.stderr}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "WHITE":
            values["WHITE"] = [float(x) for x in parts[1:]]
        elif parts[0] == "CHOW":
            values["CHOW"] = [float(x) for x in parts[1:]]
        elif parts[0] == "LJUNG":
            values["LJUNG"] = [float(x) for x in parts[1:]]
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_025_diagnostics_match_r():
    values = _r_values()
    form = _form()

    ctx = Ctx({"response_label": "y_white", "predictors": ["x1", "x2"]})
    white = WhiteTestStep()
    white.run(ctx, [form])
    out = white.export(ctx)
    assert out["lm_statistic"] == pytest.approx(values["WHITE"][0], rel=1e-5)
    assert out["lm_p"] == pytest.approx(values["WHITE"][1], rel=1e-5)
    assert out["f_statistic"] == pytest.approx(values["WHITE"][2], rel=1e-5)
    assert out["f_p"] == pytest.approx(values["WHITE"][3], rel=1e-5)

    ctx = Ctx({"response_label": "y_chow", "predictors": ["x"], "break_fraction": 0.5})
    chow = ChowTestStep()
    chow.run(ctx, [form])
    out = chow.export(ctx)
    assert out["F"] == pytest.approx(values["CHOW"][0], rel=1e-5)
    assert out["p"] == pytest.approx(values["CHOW"][1], rel=1e-5)
    assert out["rss_pooled"] == pytest.approx(values["CHOW"][2], rel=1e-5)
    assert out["rss1"] == pytest.approx(values["CHOW"][3], rel=1e-5)
    assert out["rss2"] == pytest.approx(values["CHOW"][4], rel=1e-5)

    ctx = Ctx({"value_label": "series", "lags": 5})
    ljung = LjungBoxStep()
    ljung.run(ctx, [form])
    out = ljung.export(ctx)
    assert out["Q"] == pytest.approx(values["LJUNG"][0], rel=1e-7)
    assert out["p"] == pytest.approx(values["LJUNG"][1], rel=1e-6, abs=1e-9)
