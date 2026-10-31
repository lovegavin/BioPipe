"""Hand checks for the 0.41 marginal-homogeneity, randomness and normality tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.bhapkar_test import BhapkarTestStep
from src.task.step.steps.shapiro_francia import ShapiroFranciaStep
from src.task.step.steps.von_neumann import VonNeumannStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _bhapkar():
    return _form(
        [[10, 5, 3], [4, 12, 6], [2, 4, 14]],
        ["row", "column"],
        {
            "row": {"low": 0, "mid": 1, "high": 2},
            "column": {"low": 0, "mid": 1, "high": 2},
        },
    )


def _series(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"x": 0},
        },
    )


def _sf_values():
    return [
        2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
        18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
    ]


def test_bhapkar_matches_r():
    result, out = _run(BhapkarTestStep(), {}, [_bhapkar()])
    assert result["statistic"] == pytest.approx(0.68890103881902676, rel=1e-12)
    assert result["df"] == 2
    assert result["p"] == pytest.approx(0.70860961374150644, rel=1e-12)
    assert result["n"] == 60
    assert result["n_categories"] == 3
    assert out.data.shape == (5, 1)


def test_von_neumann_matches_r():
    result, out = _run(VonNeumannStep(), {"value_label": "x"}, [_series(np.arange(1.0, 11.0))])
    assert result["VN"] == pytest.approx(0.1212121212121212, rel=1e-12)
    assert result["z"] == pytest.approx(-3.3259311751475229, rel=1e-12)
    assert result["p"] == pytest.approx(0.00088123685283041943, rel=1e-12)
    assert result["n"] == 10
    assert out.data.shape == (4, 1)


def test_shapiro_francia_matches_r():
    result, out = _run(ShapiroFranciaStep(), {"value_label": "x"}, [_series(_sf_values())])
    assert result["W"] == pytest.approx(0.97684303482122625, rel=1e-8)
    assert result["p"] == pytest.approx(0.81248335763278823, rel=1e-7)
    assert result["n"] == 20
    assert out.data.shape == (4, 1)


def test_041_rejects_invalid_inputs():
    with pytest.raises(StepError, match="square"):
        _run(BhapkarTestStep(), {}, [_form([[1, 2, 3], [4, 5, 6]], ["r", "c"], {
            "r": {"a": 0, "b": 1},
            "c": {"a": 0, "b": 1, "c": 2},
        })])
    with pytest.raises(StepError, match="at least 3"):
        _run(VonNeumannStep(), {"value_label": "x"}, [_series([1.0, 2.0])])
    with pytest.raises(StepError, match="between 5 and 5000"):
        _run(ShapiroFranciaStep(), {"value_label": "x"}, [_series([1.0, 2.0, 3.0, 4.0])])
