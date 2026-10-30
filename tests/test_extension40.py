"""Hand checks for the 0.47 post-hoc and change-point operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.nemenyi_test import NemenyiTestStep
from src.task.step.steps.pettitt_test import PettittTestStep
from src.task.step.steps.scheffe_test import ScheffeTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _grouped():
    values = np.array([1, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13], dtype=float)
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {
            "feature": {"value": 0},
            "sample": {f"s{i}": i for i in range(18)},
        },
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(18)},
            "feature": {"group": 0},
        },
        {"feature": {"group": encoder}},
    )
    return expression, meta


def _series():
    values = np.array(
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
        dtype=float,
    )
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {"value": 0},
        },
    )


def test_scheffe_matches_descstats():
    expression, meta = _grouped()
    result, out = _run(ScheffeTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (3, 8)
    assert np.allclose(out.data[:, 0], [-3.0, -7.0, -4.0], rtol=1e-6, atol=1e-7)
    assert np.allclose(
        out.data[:, 1],
        [0.044508331150382108, 4.4835604069060167e-05, 0.0076727193384942011],
        rtol=1e-6,
        atol=1e-8,
    )
    assert np.allclose(
        out.data[:, 2:4],
        [
            [-5.9312251366799238, -0.068774863320079316],
            [-9.9312251366799220, -4.068774863320077984],
            [-6.9312251366799211, -1.068774863320077095],
        ],
        rtol=1e-6,
        atol=1e-7,
    )
    assert result["n_groups"] == 3
    assert result["n_comparisons"] == 3


def test_nemenyi_matches_descstats():
    expression, meta = _grouped()
    result, out = _run(NemenyiTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (3, 7)
    assert np.allclose(
        out.data[:, 0],
        [-4.8333333333333339, -10.9166666666666661, -6.0833333333333321],
        rtol=1e-6,
        atol=1e-7,
    )
    assert np.allclose(
        out.data[:, 1],
        [0.2595187845582884734, 0.0011563817007307353, 0.1187327830527096229],
        rtol=1e-6,
        atol=1e-8,
    )
    assert result["n_comparisons"] == 3


def test_pettitt_matches_trend():
    result, out = _run(PettittTestStep(), {"value_label": "value"}, [_series()])
    assert result["U"] == pytest.approx(98.0, rel=1e-9)
    assert result["p"] == pytest.approx(0.0020978278652555764, rel=1e-9)
    assert result["change_point"] == 9
    assert result["change_points"] == [9, 11]
    assert out.data.shape == (4, 1)


def test_047_rejects_invalid_inputs():
    expression, meta = _grouped()
    with pytest.raises(StepError, match="group"):
        _run(NemenyiTestStep(), {"group_label": "missing"}, [expression, meta])
    short = _form(
        np.array([[1.0]]),
        ["sample", "feature"],
        {"sample": {"s0": 0}, "feature": {"value": 0}},
    )
    with pytest.raises(StepError, match="two observations"):
        _run(PettittTestStep(), {"value_label": "value"}, [short])
