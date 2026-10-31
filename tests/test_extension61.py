"""Hand checks for 0.68 inter-rater agreement coefficients."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.brennan_prediger import BrennanPredigerStep
from src.task.step.steps.conger_kappa import CongerKappaStep
from src.task.step.steps.gwet_ac1 import GwetAc1Step

RATINGS = np.asarray(
    [
        [1, 2, 3, 3],
        [2, 1, 1, 2],
        [2, 3, 3, 2],
        [1, 1, 2, 3],
        [3, 1, 2, 2],
    ],
    dtype=np.float32,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _ratings(matrix):
    form = Form(
        np.asarray(matrix, dtype=np.float32),
        ["subject", "rater"],
        {"subject": {f"s{i}": i for i in range(matrix.shape[0])}, "rater": {f"r{i}": i for i in range(matrix.shape[1])}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, form, params=None):
    params = params or {}
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_gwet_ac1_matches_r():
    result, out = _run(GwetAc1Step(), _ratings(RATINGS))
    assert out.data.shape == (1, 6)
    np.testing.assert_allclose(
        out.data[0],
        [-0.14427860696517408, 0.2333333333333333, 0.32999999999999996, 5, 4, 3],
        rtol=1e-10,
        atol=1e-12,
    )
    assert result["n_subjects"] == 5 and result["n_categories"] == 3


def test_brennan_prediger_matches_r():
    result, out = _run(BrennanPredigerStep(), _ratings(RATINGS))
    assert out.data.shape == (1, 6)
    np.testing.assert_allclose(
        out.data[0],
        [-0.15, 0.2333333333333333, 0.3333333333333333, 5, 4, 3],
        rtol=1e-10,
        atol=1e-12,
    )
    assert result["brennan_prediger"] == pytest.approx(-0.15)


def test_conger_kappa_and_missing_ratings():
    result, out = _run(CongerKappaStep(), _ratings(RATINGS))
    assert out.data.shape == (1, 6)
    np.testing.assert_allclose(
        out.data[0],
        [-0.11650485436893211, 0.2333333333333333, 0.31333333333333335, 5, 4, 3],
        rtol=1e-10,
        atol=1e-12,
    )
    assert result["conger_kappa"] == pytest.approx(-0.11650485436893211)

    missing = RATINGS.copy()
    missing[0, 0] = np.nan
    _, out = _run(GwetAc1Step(), _ratings(missing))
    np.testing.assert_allclose(out.data[0, :3], [-0.08865979381443291, 0.2666666666666667, 0.3263888888888889], rtol=1e-9)


def test_068_invalid_inputs():
    with pytest.raises(StepError, match="at least two subjects and two raters"):
        _run(GwetAc1Step(), _ratings(np.ones((2, 1), dtype=np.float32)))
    with pytest.raises(StepError, match="at least two distinct"):
        _run(BrennanPredigerStep(), _ratings(np.ones((3, 3), dtype=np.float32)))
    with pytest.raises(StepError, match="each subject needs at least two ratings"):
        _run(GwetAc1Step(), _ratings(np.array([[1, np.nan, np.nan], [2, 1, 2], [3, 2, 3]], dtype=np.float32)))
    with pytest.raises(StepError, match="each rater needs at least two ratings"):
        _run(
            CongerKappaStep(),
            _ratings(np.array([[1, 2, 3], [2, np.nan, 2], [3, np.nan, 1]], dtype=np.float32)),
        )
