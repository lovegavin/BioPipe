"""Hand checks for 0.88 decision curve analysis and LOWESS."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.dca import DcaStep
from src.task.step.steps.lowess import LowessStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


Y = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
P = np.array([0.05, 0.15, 0.25, 0.35, 0.65, 0.75, 0.85, 0.95])


def test_dca_matches_net_benefit_formula():
    export, out = _run(
        DcaStep(),
        {
            "outcome_label": "y",
            "probability_label": "p",
            "thresholds": [0.1, 0.2, 0.5, 0.8],
            "output": "curve",
        },
        _form(np.column_stack([Y, P]), ("y", "p")),
    )
    assert out.data.shape == (4, 7)
    np.testing.assert_allclose(
        out.data[:, 1],
        [0.4583333333333333, 0.4375, 0.5, 0.25],
        rtol=0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        out.data[:, 2],
        [0.4444444444444444, 0.375, 0.0, -1.5],
        rtol=0,
        atol=1e-12,
    )
    assert np.all(out.data[:, 3] == 0.0)
    np.testing.assert_array_equal(out.data[:, 4], [4, 4, 4, 2])
    np.testing.assert_array_equal(out.data[:, 5], [3, 2, 0, 0])
    assert export["prevalence"] == pytest.approx(0.5)
    assert export["n"] == 8


def test_dca_default_threshold_grid():
    export, out = _run(
        DcaStep(),
        {
            "outcome_label": "y",
            "probability_label": "p",
            "threshold_start": 0.1,
            "threshold_stop": 0.3,
            "threshold_step": 0.1,
        },
        _form(np.column_stack([Y, P]), ("y", "p")),
    )
    assert out.data.shape[0] == 3
    np.testing.assert_allclose(export["thresholds"], [0.1, 0.2, 0.3], atol=1e-12)


def test_dca_rejects_invalid_outcomes_and_thresholds():
    with pytest.raises(StepError, match="binary"):
        _run(
            DcaStep(),
            {"outcome_label": "y", "probability_label": "p"},
            _form(np.column_stack([[0, 1, 2, 0, 1, 0, 1, 0], P]), ("y", "p")),
        )
    with pytest.raises(StepError, match="both outcome classes"):
        _run(
            DcaStep(),
            {"outcome_label": "y", "probability_label": "p"},
            _form(np.column_stack([np.zeros(8), P]), ("y", "p")),
        )
    with pytest.raises(StepError, match="at least two thresholds"):
        _run(
            DcaStep(),
            {"outcome_label": "y", "probability_label": "p", "thresholds": [0.0, 1.0]},
            _form(np.column_stack([Y, P]), ("y", "p")),
        )


X_LOW = np.arange(1.0, 21.0)
Y_LOW = np.sin(X_LOW / 3.0) + 0.1 * X_LOW
EXPECTED_LOWESS = [
    0.9224509466974299,
    0.9983287372447838,
    1.0623969431810154,
    1.1165056731245535,
    1.1633384942376521,
    1.2056375413963654,
    1.2301738090793388,
    1.1387859337011197,
    1.005657263125864,
    0.8577003385768248,
    0.7260880219277139,
    0.6390888545660668,
    0.6178754137377566,
    0.671570872688177,
    0.8725069698085898,
    1.0883072310429278,
    1.3103120381621132,
    1.5416550231921362,
    1.784044847159378,
    2.0381256961960377,
]


def test_lowess_matches_r_stats_lowess():
    export, out = _run(
        LowessStep(),
        {"x_label": "x", "y_label": "y", "frac": 2.0 / 3.0, "iterations": 3, "output": "smooth"},
        _form(np.column_stack([X_LOW, Y_LOW]), ("x", "y")),
    )
    assert out.data.shape == (20, 4)
    np.testing.assert_allclose(out.data[:, 2], EXPECTED_LOWESS, rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.data[:, 3], Y_LOW - np.asarray(EXPECTED_LOWESS), atol=1e-12)
    assert export["n"] == 20
    assert export["iterations"] == 3


def test_lowess_rejects_invalid_inputs():
    with pytest.raises(StepError, match="x must vary"):
        _run(
            LowessStep(),
            {"x_label": "x", "y_label": "y"},
            _form(np.column_stack([np.ones(10), Y_LOW[:10]]), ("x", "y")),
        )
    with pytest.raises(StepError, match="frac"):
        _run(
            LowessStep(),
            {"x_label": "x", "y_label": "y", "frac": 0.0},
            _form(np.column_stack([X_LOW, Y_LOW]), ("x", "y")),
        )
