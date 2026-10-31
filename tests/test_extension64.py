"""Hand checks for 0.71 Zivot-Andrews and exact Poisson rate tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.poisson_means_test import PoissonMeansTestStep
from src.task.step.steps.zivot_andrews import ZivotAndrewsStep


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


def _za_form():
    rng = np.random.default_rng(20261101)
    values = np.cumsum(rng.normal(size=80)) + np.r_[np.zeros(40), np.full(40, 3.0)]
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(80)}, "feature": {"x": 0}},
    )


def _poisson_forms():
    counts = np.asarray([
        [10], [20], [30], [40], [5], [10], [15], [20],
    ], dtype=float)
    groups = np.asarray([[0]] * 4 + [[1]] * 4, dtype=float)
    expr = _form(
        counts,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"counts": 0}},
    )
    meta = _form(
        groups,
        ["sample", "group"],
        {"sample": {f"s{i}": i for i in range(8)}, "group": {"g": 0}},
    )
    return expr, meta


def test_zivot_andrews_matches_shared_break_fixture():
    result, out = _run(
        ZivotAndrewsStep(),
        {"value_label": "x", "regression": "c", "lags": 2},
        [_za_form()],
    )
    assert result["statistic"] == pytest.approx(-3.7254940402358883, abs=1e-6)
    assert result["p"] == pytest.approx(0.5295691048518368, rel=1e-6)
    assert result["break_index"] == 57
    assert result["lag"] == 2
    assert result["n"] == 80
    assert out.data.shape == (8, 1)


def test_poisson_means_matches_r_exact_test():
    expr, meta = _poisson_forms()
    result, out = _run(
        PoissonMeansTestStep(),
        {"group_label": "g", "group_a": "0", "group_b": "1"},
        [expr, meta],
    )
    assert result["group_a"] == "0" and result["group_b"] == "1"
    assert out.data.shape == (1, 10)
    row = out.data[0]
    assert row[0] == pytest.approx(100.0)
    assert row[1] == pytest.approx(50.0)
    assert row[2] == pytest.approx(4.0) and row[3] == pytest.approx(4.0)
    assert row[4] == pytest.approx(25.0) and row[5] == pytest.approx(12.5)
    assert row[6] == pytest.approx(2.0)
    assert row[7] == pytest.approx(5.4475331033925765e-05, rel=1e-9)
    assert row[8] == pytest.approx(1.4105504610094759, rel=1e-9)
    assert row[9] == pytest.approx(2.8676286550257819, rel=1e-9)


def test_ci_uses_exact_conditional_binomial():
    expr, meta = _poisson_forms()
    _result, out = _run(
        PoissonMeansTestStep(),
        {"group_label": "g", "group_a": "0", "group_b": "1", "confidence": 0.9},
        [expr, meta],
    )
    row = out.data[0]
    assert row[7] == pytest.approx(5.4475331033925765e-05, rel=1e-9)
    assert row[8] > 1.4105504610094759
    assert row[9] < 2.8676286550257819


def test_071_rejects_invalid_inputs():
    expr, meta = _poisson_forms()
    bad = _form(
        np.asarray([[10], [-1], [30], [40], [5], [10], [15], [20]], dtype=float),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"counts": 0}},
    )
    with pytest.raises(StepError, match="non-negative"):
        _run(PoissonMeansTestStep(), {"group_label": "g", "group_a": "0", "group_b": "1"}, [bad, meta])
    nonint = _form(
        np.asarray([[10.5], [20], [30], [40], [5], [10], [15], [20]], dtype=float),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"counts": 0}},
    )
    with pytest.raises(StepError, match="integer"):
        _run(PoissonMeansTestStep(), {"group_label": "g", "group_a": "0", "group_b": "1"}, [nonint, meta])
    const = _form(
        np.ones((20, 1)),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(20)}, "feature": {"x": 0}},
    )
    with pytest.raises(StepError, match="computation failed"):
        _run(ZivotAndrewsStep(), {"value_label": "x"}, [const])
