"""Hand checks for the 0.55 kurtosis and sphericity tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.anscombe_glynn import AnscombeGlynnStep
from src.task.step.steps.bonett_seier import BonettSeierStep
from src.task.step.steps.mauchly_test import MauchlyTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"value": 0}},
    )


def _matrix(values):
    n, p = values.shape
    return _form(
        values,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(n)},
            "feature": {f"f{j}": j for j in range(p)},
        },
    )


def test_anscombe_glynn_matches_r():
    values = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20]
    result, out = _run(
        AnscombeGlynnStep(), {"value_label": "value"}, [_series(values)]
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(2.1341104474559254, rel=1e-12)
    assert out.data[1, 0] == pytest.approx(-0.42227346311066044, rel=1e-12)
    assert out.data[2, 0] == pytest.approx(0.6728254253719288, rel=1e-12)
    assert out.data[3, 0] == 12
    assert result["alternative"] == "two-sided"


def test_bonett_seier_matches_r():
    values = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20]
    result, out = _run(
        BonettSeierStep(), {"value_label": "value"}, [_series(values)]
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(4.9861111111111107, rel=1e-12)
    assert out.data[1, 0] == pytest.approx(-1.0951999132137393, rel=1e-12)
    assert out.data[2, 0] == pytest.approx(0.27342906371823772, rel=1e-12)
    assert out.data[3, 0] == 12
    assert result["alternative"] == "two-sided"


def test_mauchly_matches_r():
    values = np.array(
        [
            [1.0, 2.0, 3.0],
            [2.0, 4.0, 5.0],
            [3.0, 5.0, 7.0],
            [4.0, 8.0, 8.0],
            [5.0, 9.0, 10.0],
            [6.0, 11.0, 13.0],
        ]
    )
    result, out = _run(MauchlyTestStep(), {}, [_matrix(values)])
    assert out.data.shape == (6, 1)
    assert out.data[0, 0] == pytest.approx(0.00012919496245979641, rel=1e-12)
    assert out.data[1, 0] == pytest.approx(33.329477397827006, rel=1e-12)
    assert out.data[2, 0] == 5
    assert out.data[3, 0] == pytest.approx(7.006986018929476e-06, rel=1e-12)
    assert out.data[4, 0] == 3
    assert out.data[5, 0] == 6
    assert result["n_features"] == 3


def test_invalid_inputs_rejected():
    with pytest.raises(StepError, match="zero variance"):
        _run(AnscombeGlynnStep(), {"value_label": "value"}, [_series([1.0] * 8)])
    with pytest.raises(StepError, match="zero variance"):
        _run(BonettSeierStep(), {"value_label": "value"}, [_series([1.0, 1.0, 1.0])])
    with pytest.raises(StepError, match="at least three features"):
        _run(MauchlyTestStep(), {}, [_matrix(np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]))])
    with pytest.raises(StepError, match="singular"):
        _run(
            MauchlyTestStep(),
            {},
            [_matrix(np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [3.0, 6.0, 9.0], [4.0, 8.0, 12.0]]))],
        )
