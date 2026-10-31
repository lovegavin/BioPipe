"""Hand checks for 0.66 OLS influence diagnostics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cooks_distance import CooksDistanceStep
from src.task.step.steps.dffits import DffitsStep
from src.task.step.steps.leverage import LeverageStep


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

LEVERAGE = [
    0.34545454545454546,
    0.24848484848484845,
    0.17575757575757578,
    0.12727272727272729,
    0.10303030303030304,
    0.10303030303030303,
    0.12727272727272726,
    0.17575757575757578,
    0.24848484848484853,
    0.34545454545454546,
]
COOKS = [
    0.074610468585066189,
    0.14158186949003726,
    0.17485946926332305,
    0.15197748864105742,
    3.4622183722957693e-05,
    0.028121868728972085,
    0.027117861937215996,
    0.25179763573918529,
    0.27406395908846498,
    0.017657992565055805,
]
DFFITS = [
    0.36790202489736512,
    -0.52675565099872412,
    0.62041477016880719,
    -0.59972093542830984,
    -0.0077841754527546549,
    0.22895812359793719,
    -0.22309180205911905,
    0.7907064769401313,
    -0.77780081929838962,
    0.17652800580145919,
]


def test_leverage_matches_r_hatvalues():
    result, out = _run(LeverageStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (10, 1)
    np.testing.assert_allclose(out.data[:, 0], LEVERAGE, rtol=1e-6, atol=1e-8)
    assert result["p"] == 2 and result["n"] == 10


def test_cooks_distance_matches_r():
    result, out = _run(CooksDistanceStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (10, 1)
    np.testing.assert_allclose(out.data[:, 0], COOKS, rtol=1e-6, atol=1e-9)
    assert result["max_sample"] == "s8"


def test_dffits_matches_r():
    result, out = _run(DffitsStep(), {"response": "y"}, [DESIGN])
    assert out.data.shape == (10, 1)
    np.testing.assert_allclose(out.data[:, 0], DFFITS, rtol=1e-6, atol=1e-7)
    assert result["max_sample"] == "s7"


def test_066_invalid_inputs():
    with pytest.raises(StepError, match="response 'z'"):
        _run(LeverageStep(), {"response": "z"}, [DESIGN])
    with pytest.raises(StepError, match="at least one predictor"):
        _run(LeverageStep(), {"response": "y"}, [_design(Y.reshape(-1, 1))])
    with pytest.raises(StepError, match="rank deficient"):
        _run(CooksDistanceStep(), {"response": "y"}, [_design(np.column_stack([X, X, Y]))])
    with pytest.raises(StepError, match="at least four complete"):
        _run(DffitsStep(), {"response": "y"}, [_design(np.column_stack([X[:3], Y[:3]]))])
