"""Hand tests for calibration, NRI and IDI operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.calibration_slope import CalibrationSlopeStep
from src.task.step.steps.integrated_discrimination_improvement import IntegratedDiscriminationImprovementStep
from src.task.step.steps.net_reclassification_improvement import NetReclassificationImprovementStep


Y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1], dtype=np.float32)
OLD = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], dtype=np.float32)
NEW = np.array([0.05, 0.15, 0.35, 0.45, 0.65, 0.55, 0.55, 0.65, 0.75, 0.85, 0.9, 0.95], dtype=np.float32)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form(outcome=Y):
    form = Form(
        np.column_stack([outcome, OLD, NEW]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(12)},
            "feature": {"outcome": 0, "old_risk": 1, "new_risk": 2},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _params():
    return {
        "outcome_label": "outcome",
        "old_risk_label": "old_risk",
        "new_risk_label": "new_risk",
    }


def test_calibration_slope_matches_r():
    ctx = Ctx({"outcome_label": "outcome", "risk_label": "new_risk"})
    step = CalibrationSlopeStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["calibration_intercept"] == pytest.approx(-0.4063779, rel=1e-5)
    assert out["calibration_slope"] == pytest.approx(3.621762, rel=1e-5)
    assert out["slope_se"] == pytest.approx(2.577094, rel=1e-5)
    assert out["n"] == 12


def test_nri_matches_r():
    ctx = Ctx(_params())
    step = NetReclassificationImprovementStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["nri"] == pytest.approx(1.0, rel=1e-6)
    assert out["events_up_rate"] == pytest.approx(1.0)
    assert out["events_down_rate"] == pytest.approx(0.0)
    assert out["nonevents_up_rate"] == pytest.approx(0.5)
    assert out["nonevents_down_rate"] == pytest.approx(0.5)


def test_idi_matches_r():
    ctx = Ctx(_params())
    step = IntegratedDiscriminationImprovementStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["old_discrimination"] == pytest.approx(0.3, rel=1e-6)
    assert out["new_discrimination"] == pytest.approx(0.4083333333, rel=1e-6)
    assert out["idi"] == pytest.approx(0.1083333333, rel=1e-6)


def test_non_binary_outcome_rejected():
    ctx = Ctx({"outcome_label": "outcome", "risk_label": "new_risk"})
    bad = Y.copy()
    bad[0] = 2.0
    with pytest.raises(StepError, match="binary"):
        CalibrationSlopeStep().run(ctx, [_form(bad)])
