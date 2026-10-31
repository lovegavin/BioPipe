"""Hand checks for 0.60 time-series, marginal-homogeneity, and VI operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.box_pierce import BoxPierceStep
from src.task.step.steps.stuart_maxwell_test import StuartMaxwellTestStep
from src.task.step.steps.variation_of_information import VariationOfInformationStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"value": 0},
        },
    )


def _table(rows):
    rows = np.asarray(rows, dtype=float)
    return _form(
        rows,
        ["row", "column"],
        {
            "row": {f"r{i}": i for i in range(rows.shape[0])},
            "column": {f"c{i}": i for i in range(rows.shape[1])},
        },
    )


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    return _form(
        values,
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
    )


def test_box_pierce_matches_r():
    result, out = _run(
        BoxPierceStep(),
        {"value_label": "value", "lags": 3},
        [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])],
    )
    assert out.data.shape == (6, 1)
    assert out.data[0, 0] == pytest.approx(7.5205292512163302, rel=1e-9)
    assert out.data[1, 0] == 3
    assert out.data[2, 0] == pytest.approx(0.057033307356141538, rel=1e-9)
    assert result["n"] == 12


def test_stuart_maxwell_matches_r():
    result, out = _run(
        StuartMaxwellTestStep(),
        {},
        [_table([[20, 10, 5], [8, 25, 7], [6, 9, 30]])],
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(0.53474320241691853, rel=1e-9)
    assert out.data[1, 0] == 2
    assert out.data[2, 0] == pytest.approx(0.76538859928510916, rel=1e-9)
    assert result["N"] == 120


def test_variation_of_information_matches_r_aricode():
    first = _labels([1, 1, 1, 2, 2, 2, 3, 3, 3])
    second = _labels([1, 1, 2, 2, 3, 3, 1, 2, 3])
    result, out = _run(
        VariationOfInformationStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [first, second],
    )
    assert out.data.shape == (9, 1)
    assert out.data[0, 0] == pytest.approx(1.5810937501718234, rel=1e-9)
    assert out.data[1, 0] == pytest.approx(0.83692987891500414, rel=1e-9)
    assert out.data[2, 0] == pytest.approx(0.3080654135821979, rel=1e-9)
    assert result["n_clusters_a"] == 3


def test_060_invalid_inputs():
    with pytest.raises(StepError, match="lags must be less than n"):
        _run(BoxPierceStep(), {"value_label": "value", "lags": 12}, [_series(range(12))])
    with pytest.raises(StepError, match="fitdf"):
        _run(BoxPierceStep(), {"value_label": "value", "lags": 3, "fitdf": 3}, [_series(range(12))])
    with pytest.raises(StepError, match="square"):
        _run(StuartMaxwellTestStep(), {}, [_table([[1, 2, 3], [4, 5, 6]])])
    with pytest.raises(StepError, match="joint variation"):
        _run(
            VariationOfInformationStep(),
            {"label_a": "cluster", "label_b": "cluster"},
            [_labels([0, 0, 0, 0]), _labels([0, 0, 0, 0])],
        )
