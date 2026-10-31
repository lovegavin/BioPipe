"""Hand checks for the 0.23 survival prediction operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.brier_score import BrierScoreStep
from src.task.step.steps.integrated_brier_score import IntegratedBrierScoreStep
from src.task.step.steps.time_dependent_auc import TimeDependentAucStep


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


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [_form()])
    return ctx[params.get("output", step.name)], step.export(ctx)


def test_time_dependent_auc_matches_survivalroc_km():
    out, info = _run(
        TimeDependentAucStep(),
        {"time_label": "time", "event_label": "event", "risk_label": "risk", "predict_time": 10},
    )
    assert info["auc"] == pytest.approx(0.8091230111, rel=1e-6)
    assert info["n_cases"] == 5
    assert info["n_controls"] == 10
    assert out.data.shape == (5, 1)


def test_brier_score_matches_survival_brier():
    out, info = _run(
        BrierScoreStep(),
        {"time_label": "time", "event_label": "event", "risk_label": "risk", "times": [5, 10, 15]},
    )
    assert np.allclose(info["brier"], [0.1315698, 0.1807035, 0.2145172], atol=2e-6)
    assert info["coef"] == pytest.approx(0.2425241, rel=2e-5)
    assert out.data.shape == (3, 3)


def test_integrated_brier_score_matches_trapezoid():
    out, info = _run(
        IntegratedBrierScoreStep(),
        {"time_label": "time", "event_label": "event", "risk_label": "risk", "times": [5, 10, 15]},
    )
    assert info["integrated_brier"] == pytest.approx(1.768735, rel=1e-6)
    assert info["brier"] == pytest.approx([0.1315698, 0.1807035, 0.2145172], rel=2e-5)
    assert out.data.shape == (6, 1)


def test_rejects_unordered_times():
    with pytest.raises(StepError, match="strictly increasing"):
        _run(
            IntegratedBrierScoreStep(),
            {"time_label": "time", "event_label": "event", "risk_label": "risk", "times": [10, 5]},
        )
