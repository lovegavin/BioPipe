"""Authoritative R checks for the 0.24 calibration/NRI/IDI operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.calibration_slope import CalibrationSlopeStep
from src.task.step.steps.integrated_discrimination_improvement import IntegratedDiscriminationImprovementStep
from src.task.step.steps.net_reclassification_improvement import NetReclassificationImprovementStep


RSCRIPT = shutil.which("Rscript")
Y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1], dtype=np.float32)
OLD = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], dtype=np.float32)
NEW = np.array([0.05, 0.15, 0.35, 0.45, 0.65, 0.55, 0.55, 0.65, 0.75, 0.85, 0.9, 0.95], dtype=np.float32)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form():
    form = Form(
        np.column_stack([Y, OLD, NEW]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(12)},
            "feature": {"outcome": 0, "old_risk": 1, "new_risk": 2},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _r_values():
    script = """
y <- c(0,0,0,0,0,0,1,1,1,1,1,1)
old <- c(0.1,0.2,0.3,0.4,0.5,0.6,0.4,0.5,0.6,0.7,0.8,0.9)
new <- c(0.05,0.15,0.35,0.45,0.65,0.55,0.55,0.65,0.75,0.85,0.9,0.95)
lp <- qlogis(new)
fit <- glm(y ~ lp, family = binomial())
off <- glm(y ~ 1, family = binomial(), offset = lp)
ci <- coef(off)
cs <- coef(fit)
se <- sqrt(diag(vcov(fit)))
cat("CAL", sprintf("%.10f", c(ci, cs, se)), "\\n")
up <- new > old
down <- new < old
cat("NRI", sprintf("%.10f", c(mean(up[y == 1]) - mean(down[y == 1]),
                              mean(down[y == 0]) - mean(up[y == 0]))), "\\n")
cat("IDI", sprintf("%.10f", (mean(new[y == 1]) - mean(new[y == 0])) -
                              (mean(old[y == 1]) - mean(old[y == 0]))), "\\n")
"""
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(f"R calibration oracle failed:\n{proc.stderr}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "CAL":
            values["CAL"] = [float(x) for x in parts[1:]]
        elif parts[0] == "NRI":
            values["NRI"] = [float(x) for x in parts[1:]]
        elif parts[0] == "IDI":
            values["IDI"] = float(parts[1])
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_calibration_nri_idi_match_r():
    values = _r_values()
    form = _form()

    ctx = Ctx({"outcome_label": "outcome", "risk_label": "new_risk"})
    cal = CalibrationSlopeStep()
    cal.run(ctx, [form])
    out = cal.export(ctx)
    expected_intercept = values["CAL"][0]
    expected_slope = values["CAL"][2]
    expected_se = values["CAL"][4]
    assert out["calibration_intercept"] == pytest.approx(expected_intercept, rel=1e-5)
    assert out["calibration_slope"] == pytest.approx(expected_slope, rel=1e-5)
    assert out["slope_se"] == pytest.approx(expected_se, rel=1e-5)

    ctx = Ctx({"outcome_label": "outcome", "old_risk_label": "old_risk", "new_risk_label": "new_risk"})
    nri = NetReclassificationImprovementStep()
    nri.run(ctx, [form])
    out = nri.export(ctx)
    assert out["nri"] == pytest.approx(sum(values["NRI"]), rel=1e-6)

    ctx = Ctx({"outcome_label": "outcome", "old_risk_label": "old_risk", "new_risk_label": "new_risk"})
    idi = IntegratedDiscriminationImprovementStep()
    idi.run(ctx, [form])
    assert idi.export(ctx)["idi"] == pytest.approx(values["IDI"], rel=1e-6)
