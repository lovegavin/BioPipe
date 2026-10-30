"""Hand checks for 0.34 paired ROC and Cochran's Q tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cochran_q import CochranQStep
from src.task.step.steps.roc_comparison import RocComparisonStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, names, value_dim="feature"):
    data = np.asarray(data, dtype=np.float64)
    if data.ndim == 1:
        data = data[:, None]
    form = Form(
        data,
        ["sample", value_dim],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            value_dim: {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _roc_fixture():
    rng = np.random.default_rng(42)
    y = np.array([1] * 20 + [0] * 20, dtype=float)
    a = np.r_[rng.normal(1.2, 1.0, 20), rng.normal(0, 1.0, 20)]
    b = 0.7 * a + 0.3 * rng.normal(size=40) + 0.2 * y
    return _form(y, ["y"], "label"), _form(a, ["a"], "score"), _form(b, ["b"], "score")


def test_roc_comparison_matches_paired_delong():
    labels, score_a, score_b = _roc_fixture()
    out, info = _run(
        RocComparisonStep(),
        {"target_label": "y", "score_a": "a", "score_b": "b"},
        [labels, score_a, score_b],
    )
    assert out.dims == ["metric", "value"]
    assert out.data.shape == (10, 1)
    assert info["auc_a"] == pytest.approx(0.8025, abs=1e-7)
    assert info["auc_b"] == pytest.approx(0.8850, abs=1e-7)
    assert info["difference"] == pytest.approx(-0.0825, abs=1e-7)
    assert info["se"] == pytest.approx(0.0363734287054, abs=1e-9)
    assert info["z"] == pytest.approx(-2.268139214153, abs=1e-9)
    assert info["p"] == pytest.approx(0.02332072292964, abs=1e-10)
    assert info["ci_low"] == pytest.approx(-0.1537906102569, abs=1e-9)
    assert info["ci_high"] == pytest.approx(-0.0112093897431, abs=1e-9)
    assert info["n_pos"] == 20
    assert info["n_neg"] == 20


def test_cochran_q_matches_friedman_formula():
    rows = [
        [1, 1, 1],
        [1, 1, 0],
        [1, 1, 0],
        [1, 0, 1],
        [1, 0, 0],
        [0, 1, 1],
        [0, 1, 0],
        [0, 0, 1],
        [0, 0, 0],
        [0, 0, 0],
    ]
    out, info = _run(
        CochranQStep(),
        {},
        [_form(rows, ["c1", "c2", "c3"])],
    )
    assert out.data.shape == (5, 1)
    assert info["statistic"] == pytest.approx(2.0 / 7.0, abs=1e-12)
    assert info["df"] == 2
    assert info["p"] == pytest.approx(0.8668778997502, abs=1e-12)
    assert info["n"] == 10
    assert info["n_conditions"] == 3


def test_parameter_errors():
    labels, score_a, score_b = _roc_fixture()
    with pytest.raises(StepError, match="not in"):
        _run(
            RocComparisonStep(),
            {"target_label": "y", "score_a": "missing", "score_b": "b"},
            [labels, score_a, score_b],
        )
    with pytest.raises(StepError, match="only 0/1"):
        _run(
            CochranQStep(),
            {},
            [_form([[1, 2, 0], [0, 1, 1]], ["c1", "c2", "c3"])],
        )
    with pytest.raises(StepError, match="do not vary across subjects"):
        _run(
            CochranQStep(),
            {},
            [_form([[1, 1, 1], [1, 1, 1]], ["c1", "c2", "c3"])],
        )
