"""Hand checks for 0.72 Theil U, DFBETAS and COVRATIO."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.covratio import CovratioStep
from src.task.step.steps.dfbetas import DfbetasStep
from src.task.step.steps.theil_u import TheilUStep


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


def _reg_form():
    rows = np.asarray([
        [3, 1, 2], [5, 2, 1], [4, 3, 4], [8, 4, 3],
        [7, 5, 6], [10, 6, 5], [9, 7, 8], [12, 8, 7],
    ], dtype=np.float32)
    return _form(
        rows,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"y": 0, "x1": 1, "x2": 2}},
    )


def _table_form():
    return _form(
        np.asarray([[10, 20], [30, 40]], dtype=np.float32),
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1}, "column": {"c0": 0, "c1": 1}},
    )


def test_theil_u_matches_desc_tools_values():
    result, out = _run(TheilUStep(), {}, [_table_form()])
    assert out.data.shape == (6, 1)
    assert result["u_row_given_column"] == pytest.approx(0.006583693, rel=1e-6)
    assert result["u_column_given_row"] == pytest.approx(0.005975741, rel=1e-6)
    assert result["u_symmetric"] == pytest.approx(0.006265003, rel=1e-6)
    assert out.data[0, 0] == pytest.approx(result["u_row_given_column"], rel=1e-6)


def test_dfbetas_matches_r_fixture():
    result, out = _run(DfbetasStep(), {"response": "y"}, [_reg_form()])
    assert out.data.shape == (8, 3)
    assert result["coefficients"] == ["intercept", "x1", "x2"]
    assert out.data[0, 0] == pytest.approx(1.685224359, abs=2e-6)
    assert out.data[0, 1] == pytest.approx(-1.29852524, abs=2e-6)
    assert out.data[0, 2] == pytest.approx(0.69920590, abs=2e-6)


def test_covratio_matches_r_fixture():
    result, out = _run(CovratioStep(), {"response": "y"}, [_reg_form()])
    assert out.data.shape == (8, 1)
    expected = [0.4017102, 1.0186115, 0.2800875, 1.6334704, 2.4723222, 2.4723222, 3.6721322, 3.6721322]
    np.testing.assert_allclose(out.data[:, 0], expected, rtol=2e-6, atol=2e-6)
    assert result["min_sample"] == "s2"
    assert result["max_sample"] in {"s6", "s7"}


def test_072_rejects_invalid_inputs():
    with pytest.raises(StepError, match="positive total"):
        _run(
            TheilUStep(),
            {},
            [_form(np.asarray([[0, 0], [1, 2]]), ["row", "column"], {"row": {"a": 0, "b": 1}, "column": {"a": 0, "b": 1}})],
        )
    with pytest.raises(StepError, match="only one predictor|required"):
        _run(DfbetasStep(), {"response": "y"}, [_form(
            np.asarray([[1], [2], [3], [4]], dtype=float),
            ["sample", "feature"],
            {"sample": {f"s{i}": i for i in range(4)}, "feature": {"y": 0}},
        )])
