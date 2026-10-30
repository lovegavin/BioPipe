"""Authoritative R checks for the 0.23 survival prediction operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.brier_score import BrierScoreStep
from src.task.step.steps.integrated_brier_score import IntegratedBrierScoreStep
from src.task.step.steps.time_dependent_auc import TimeDependentAucStep


RSCRIPT = shutil.which("Rscript")
TIME = np.arange(1, 21, dtype=np.float32)
EVENT = np.tile([1, 0], 10).astype(np.float32)
RISK = np.array(
    [1.3710, -0.5647, 0.3631, 0.6329, 0.4043, -0.1061, 1.5115, -0.0947,
     2.0184, -0.0627, 1.3049, 2.2866, -1.3889, -0.2788, -0.1333, 0.6360,
     -0.2843, -2.6565, -2.4405, 1.3201],
    dtype=np.float32,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form():
    form = Form(
        np.column_stack([TIME, EVENT, RISK]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {"time": 0, "event": 1, "risk": 2},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _r_values():
    script = """
suppressPackageStartupMessages({library(survival); library(survivalROC)})
time <- 1:20
event <- rep(c(1, 0), 10)
risk <- c(1.3710, -0.5647, 0.3631, 0.6329, 0.4043, -0.1061, 1.5115, -0.0947,
          2.0184, -0.0627, 1.3049, 2.2866, -1.3889, -0.2788, -0.1333, 0.6360,
          -0.2843, -2.6565, -2.4405, 1.3201)
for (t in c(5, 10, 15)) {
  r <- survivalROC(Stime = time, status = event, marker = risk,
                   predict.time = t, method = "KM")
  cat("AUC", t, sprintf("%.10f", r$AUC), "\\n")
}
fit <- coxph(Surv(time, event) ~ risk)
b <- brier(fit, times = c(5, 10, 15))$brier
cat("BRIER", paste(sprintf("%.10f", b), collapse = ","), "\\n")
ibs <- sum(diff(c(5, 10, 15)) * (b[-length(b)] + b[-1]) / 2)
cat("IBS", sprintf("%.10f", ibs), "\\n")
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
            pytest.skip(f"R survival/survivalROC unavailable: {proc.stderr.strip()[:300]}")
        pytest.fail(f"R survival oracle failed:\n{proc.stderr}")
    values = {"AUC": {}, "BRIER": None, "IBS": None}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "AUC":
            values["AUC"][float(parts[1])] = float(parts[2])
        elif parts[0] == "BRIER":
            values["BRIER"] = [float(x) for x in parts[1].split(",")]
        elif parts[0] == "IBS":
            values["IBS"] = float(parts[1])
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_survival_prediction_matches_r():
    r = _r_values()
    form = _form()
    for t, expected in r["AUC"].items():
        ctx = Ctx({"time_label": "time", "event_label": "event", "risk_label": "risk", "predict_time": t})
        TimeDependentAucStep().run(ctx, [form])
        assert ctx["time_dependent_auc"].info["auc"] == pytest.approx(expected, rel=1e-6)

    ctx = Ctx({"time_label": "time", "event_label": "event", "risk_label": "risk", "times": [5, 10, 15]})
    brier_step = BrierScoreStep()
    brier_step.run(ctx, [form])
    assert np.allclose(brier_step.export(ctx)["brier"], r["BRIER"], atol=1e-6)

    ctx = Ctx({"time_label": "time", "event_label": "event", "risk_label": "risk", "times": [5, 10, 15]})
    ibs_step = IntegratedBrierScoreStep()
    ibs_step.run(ctx, [form])
    assert ibs_step.export(ctx)["integrated_brier"] == pytest.approx(r["IBS"], rel=1e-6)
