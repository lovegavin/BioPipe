"""Hand checks for the 0.43 block/randomness tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.mardia_test import MardiaTestStep
from src.task.step.steps.page_test import PageTestStep
from src.task.step.steps.turning_point_test import TurningPointTestStep


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


def _page_matrix():
    return _form(
        np.array([
            [1, 2, 3, 4],
            [2, 1, 3, 4],
            [1, 3, 2, 4],
            [2, 3, 1, 4],
            [1, 2, 4, 3],
            [2, 1, 3, 4],
            [1, 3, 2, 4],
            [1, 2, 3, 4],
        ], dtype=float),
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(8)},
            "treatment": {f"t{j}": j for j in range(4)},
        },
    )


def _mardia_matrix():
    idx = np.arange(1.0, 61.0)
    return _form(
        np.column_stack([idx, np.sin(idx), np.cos(idx / 3.0)]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(60)},
            "feature": {"x1": 0, "x2": 1, "x3": 2},
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


def test_page_exact_matches_r():
    result, out = _run(PageTestStep(), {}, [_page_matrix()])
    assert result["L"] == 232
    assert result["p"] == pytest.approx(8.0199816518308664e-06, rel=1e-7)
    assert result["exact"] is True
    assert out.data.shape == (6, 1)


def test_page_normal_branch_matches_r():
    data = np.outer(np.ones(5), np.arange(1.0, 17.0)) + np.arange(5).reshape(-1, 1) * 0.01
    form = _form(
        data, ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(5)},
            "treatment": {f"t{j}": j for j in range(16)},
        },
    )
    result, _ = _run(PageTestStep(), {}, [form])
    assert result["L"] == 7480
    assert result["exact"] is False
    assert result["p"] == pytest.approx(2.3535702950702129e-18, rel=1e-9)


def test_mardia_matches_psych():
    result, out = _run(MardiaTestStep(), {}, [_mardia_matrix()])
    assert result["b1p"] == pytest.approx(0.12217681576367496, rel=1e-5)
    assert result["b2p"] == pytest.approx(10.404188899192361, rel=1e-5)
    assert result["skew"] == pytest.approx(1.2217681576367496, rel=1e-5)
    assert result["small_skew"] == pytest.approx(1.3151974873383832, rel=1e-5)
    assert result["p_skew"] == pytest.approx(0.99957224997298111, rel=1e-5)
    assert result["p_small"] == pytest.approx(0.99940493624954152, rel=1e-5)
    assert result["kurtosis"] == pytest.approx(-3.2497291944334936, rel=1e-5)
    assert result["p_kurt"] == pytest.approx(0.0011551495235322395, rel=1e-5)
    assert out.data.shape == (11, 1)


def test_turning_point_matches_randtests():
    values = [1, 3, 2, 5, 4, 7, 6, 9, 8, 10]
    result, out = _run(TurningPointTestStep(), {"value_label": "x"}, [_series(values)])
    assert result["turns"] == 8
    assert result["z"] == pytest.approx(2.2103158559821505, rel=1e-9)
    assert result["p"] == pytest.approx(0.027083248944000271, rel=1e-12)
    assert out.data.shape == (6, 1)


def test_043_rejects_invalid_inputs():
    tied = _page_matrix()
    tied.data[0, 0] = tied.data[0, 1]
    with pytest.raises(StepError, match="ties"):
        _run(PageTestStep(), {}, [tied])
    with pytest.raises(StepError, match="two features"):
        _run(MardiaTestStep(), {}, [_form(
            np.arange(10.0).reshape(10, 1), ["sample", "feature"],
            {"sample": {f"s{i}": i for i in range(10)}, "feature": {"x": 0}},
        )])
    with pytest.raises(StepError, match="consecutive ties"):
        _run(TurningPointTestStep(), {"value_label": "x"}, [_series([1, 2, 2, 3, 4])])
    with pytest.raises(StepError, match="at least four"):
        _run(TurningPointTestStep(), {"value_label": "x"}, [_series([1, 2, 3])])
