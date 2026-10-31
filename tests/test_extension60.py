"""Hand checks for 0.67 OLS residual diagnostics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.press import PressStep
from src.task.step.steps.standardized_residuals import StandardizedResidualsStep
from src.task.step.steps.studentized_residuals import StudentizedResidualsStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _design(values):
    data = np.asarray(values, dtype=np.float32)
    if data.shape[1] == 1:
        feature_labels = {"y": 0}
    elif data.shape[1] == 2:
        feature_labels = {"x": 0, "y": 1}
    else:
        feature_labels = {"x1": 0, "x2": 1, "y": 2}
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": feature_labels,
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


X = np.arange(1, 11, dtype=float)
Y = 2.0 + 0.5 * X + np.array([1, -1, 2, -2, 0, 1, -1, 2, -2, 0], dtype=float)
DESIGN = _design(np.column_stack([X, Y]))

STANDARDIZED = [
    0.531727756723047618,
    -0.925417554187445868,
    1.280648753153083019,
    -1.443697579606987080,
    -0.024552664144405371,
    0.699750928115549509,
    -0.609837770696054715,
    1.536778503783700067,
    -1.287537466695575450,
    0.258678368135536407,
]
STUDENTIZED = [
    0.506415078205768143,
    -0.916068854139824862,
    1.343546134340419584,
    -1.570438047114258939,
    -0.022967779665450629,
    0.675557709012263419,
    -0.584191468491439103,
    1.712323241759369008,
    -1.352655835647444293,
    0.242989811997891242,
]


def test_standardized_residuals_match_r():
    result, out = _run(StandardizedResidualsStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (10, 1)
    np.testing.assert_allclose(out.data[:, 0], STANDARDIZED, rtol=1e-6, atol=1e-8)
    assert result["p"] == 2 and result["n"] == 10


def test_studentized_residuals_match_r():
    result, out = _run(StudentizedResidualsStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (10, 1)
    np.testing.assert_allclose(out.data[:, 0], STUDENTIZED, rtol=1e-6, atol=1e-8)
    assert result["max_sample"] == "s7"


def test_press_matches_r():
    result, out = _run(PressStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (1, 4)
    np.testing.assert_allclose(
        out.data[0], [29.579274620026872, 1.719862628817397, 10, 2], rtol=1e-6, atol=1e-8
    )
    assert result["n"] == 10 and result["p"] == 2


def test_067_invalid_inputs():
    with pytest.raises(StepError, match="response 'z'"):
        _run(StandardizedResidualsStep(), {"response": "z"}, [DESIGN])
    with pytest.raises(StepError, match="at least one predictor"):
        _run(StudentizedResidualsStep(), {"response": "y"}, [_design(Y.reshape(-1, 1))])
    with pytest.raises(StepError, match="rank deficient"):
        _run(PressStep(), {"response": "y"}, [_design(np.column_stack([X, X, Y]))])
    with pytest.raises(StepError, match="at least four complete"):
        _run(PressStep(), {"response": "y"}, [_design(np.column_stack([X[:3], Y[:3]]))])
