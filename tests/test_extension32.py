"""Hand checks for the 0.39 multivariate/robust tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.g_test import GTestStep
from src.task.step.steps.hotelling_t2 import HotellingT2Step
from src.task.step.steps.yuen_test import YuenTestStep


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


def _hotelling():
    data = np.asarray([
        [1.0, 2.0, 3.0], [2.0, 1.5, 2.5], [1.5, 2.5, 3.5], [2.5, 2.0, 2.0],
        [3.0, 3.5, 4.0], [3.5, 3.0, 4.5], [4.0, 4.0, 3.5], [2.8, 3.2, 4.2],
    ])
    expr = _form(
        data.T,
        ["feature", "sample"],
        {"feature": {f"f{i}": i for i in range(3)},
         "sample": {f"s{i}": i for i in range(8)}},
    )
    meta = _form(
        [[0], [0], [0], [0], [1], [1], [1], [1]],
        ["sample", "group"],
        {"sample": {f"s{i}": i for i in range(8)}, "group": {"g": 0}},
    )
    return expr, meta


def _yuen():
    a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    b = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    expr = _form(
        np.asarray([a + b], dtype=float),
        ["feature", "sample"],
        {"feature": {"x": 0}, "sample": {f"s{i}": i for i in range(20)}},
    )
    meta = _form(
        [[0]] * 10 + [[1]] * 10,
        ["sample", "group"],
        {"sample": {f"s{i}": i for i in range(20)}, "group": {"g": 0}},
    )
    return expr, meta


def _table():
    return _form(
        [[10, 20, 30], [20, 15, 25], [30, 25, 20]],
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1, "r2": 2}, "column": {"c0": 0, "c1": 1, "c2": 2}},
    )


def test_hotelling_matches_r_f_test():
    result, out = _run(
        HotellingT2Step(),
        {"group_label": "g", "group_a": "0", "group_b": "1"},
        list(_hotelling()),
    )
    assert result["F"] == pytest.approx(22.131694828469026, rel=1e-6)
    assert result["df1"] == 3
    assert result["df2"] == 4
    assert result["p"] == pytest.approx(0.0059380028788470485, rel=1e-6)
    assert result["T2"] == pytest.approx(
        result["F"] * 3 * 6 / 4, rel=1e-12
    )
    assert out.data.shape == (8, 1)


def test_yuen_matches_r_two_sample_trimmed_test():
    result, out = _run(
        YuenTestStep(),
        {"group_label": "g", "group_a": "0", "group_b": "1"},
        list(_yuen()),
    )
    assert result["group_a"] == "0" and result["group_b"] == "1"
    assert out.data.shape == (1, 10)
    row = out.data[0]
    assert row[0] == pytest.approx(-1.0)
    assert row[1] == pytest.approx(-0.566987210046772, rel=1e-6)
    assert row[2] == pytest.approx(10.0)
    assert row[3] == pytest.approx(0.5832249832837027, rel=1e-6)
    assert row[4] == pytest.approx(-4.9297867967823645, rel=1e-6)
    assert row[5] == pytest.approx(2.9297867967823645, rel=1e-6)
    assert row[6] == pytest.approx(5.5)
    assert row[7] == pytest.approx(6.5)


def test_g_test_matches_r_without_correction():
    result, out = _run(GTestStep(), {}, [_table()])
    assert result["G"] == pytest.approx(12.750352918064657, rel=1e-10)
    assert result["df"] == 4
    assert result["p"] == pytest.approx(0.012562279689834366, rel=1e-10)
    assert out.data.shape == (6, 1)


def test_039_rejects_invalid_inputs():
    expr, meta = _hotelling()
    with pytest.raises(StepError, match="must differ"):
        _run(YuenTestStep(), {"group_label": "g", "group_a": "0", "group_b": "0"}, [expr, meta])
    with pytest.raises(StepError, match="trim"):
        _run(YuenTestStep(), {"group_label": "g", "group_a": "0", "group_b": "1", "trim": 0.5}, [expr, meta])
    with pytest.raises(StepError, match="at least two rows"):
        _run(GTestStep(), {}, [_form([[1, 2]], ["row", "column"], {"row": {"r": 0}, "column": {"c0": 0, "c1": 1}})])
