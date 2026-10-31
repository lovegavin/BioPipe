"""Hand checks for 0.94 Box-Cox transform."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.box_cox import BoxCoxStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels, dims=None):
    values = np.asarray(values, dtype=float)
    if dims is None:
        dims = ["sample", "feature"]
    sample_dim = "sample"
    feature_dim = "feature"
    form = Form(
        data=values,
        dims=list(dims),
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form, sample_dim, feature_dim


X = np.array(
    [0.5, 0.7, 0.9, 1.2, 1.5, 1.9, 2.4, 3.0, 3.8, 4.8], dtype=float
)
EXPECTED_HALF = np.array(
    [
        -0.585786437626905,
        -0.326679946931849,
        -0.10263340389897238,
        0.1908902300206644,
        0.4494897427831781,
        0.7568097504180442,
        1.0983866769659334,
        1.4641016151377548,
        1.8987177379235853,
        2.381780460041329,
    ]
)


def test_box_cox_explicit_lambda_matches_formula():
    form, sample_dim, feature_dim = _form(X.reshape(-1, 1), ("x",))
    export, out = _run(
        BoxCoxStep(),
        {"lambdas": 0.5, "output": "bc"},
        form,
    )
    assert out.data.shape == X.reshape(-1, 1).shape
    np.testing.assert_allclose(out.data[:, 0].astype(float), EXPECTED_HALF, rtol=1e-6, atol=1e-6)
    assert export["lambdas"] == {"x": 0.5}
    assert out.info["lambdas"] == {"x": 0.5}
    assert out.info["shift"] == 0.0


def test_box_cox_estimates_lambda_per_feature():
    form, _, _ = _form(X.reshape(-1, 1), ("x",))
    export, out = _run(BoxCoxStep(), {"output": "bc"}, form)
    lam = export["lambdas"]["x"]
    assert lam == pytest.approx(0.10629751945965626, abs=1e-6)
    expected = np.where(
        np.abs(lam) < 1e-12, np.log(X), (np.power(X, lam) - 1.0) / lam
    )
    np.testing.assert_allclose(out.data[:, 0].astype(float), expected, rtol=1e-6, atol=1e-6)
    assert export["n_valid"] == {"x": 10}


def test_box_cox_shift_and_missing_values():
    values = np.array([[0.0], [1.0], [2.0], [np.nan], [3.0]])
    form, _, _ = _form(values, ("x",))
    export, out = _run(
        BoxCoxStep(),
        {"lambdas": {"x": 0.0}, "shift": 1.0, "output": "bc"},
        form,
    )
    assert np.isnan(out.data[3, 0])
    np.testing.assert_allclose(
        out.data[[0, 1, 2, 4], 0].astype(float),
        [0.0, np.log(2.0), np.log(3.0), np.log(4.0)],
        rtol=0,
        atol=1e-7,
    )
    assert export["shift"] == 1.0
    assert out.info["shift"] == 1.0
    assert out.info["n_valid"]["x"] == 4


def test_box_cox_axis_order_is_preserved():
    values = X.reshape(1, -1)  # feature x sample
    form = Form(
        data=values,
        dims=["feature", "sample"],
        labels={
            "feature": {"x": 0},
            "sample": {f"s{i}": i for i in range(X.size)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    ctx = Ctx({"lambdas": 0.5, "sample_dim": "sample", "feature_dim": "feature"})
    BoxCoxStep().run(ctx, [form])
    out = ctx["box_cox"]
    assert out.dims == ["feature", "sample"]
    assert out.data.shape == (1, X.size)
    np.testing.assert_allclose(out.data[0].astype(float), EXPECTED_HALF, rtol=1e-6, atol=1e-6)


def test_box_cox_rejects_invalid_inputs():
    negative, _, _ = _form(np.array([[-1.0], [1.0], [2.0]]), ("x",))
    with pytest.raises(StepError, match="strictly positive"):
        _run(BoxCoxStep(), {"lambdas": 0.5}, negative)

    short, _, _ = _form(np.array([[1.0], [2.0]]), ("x",))
    with pytest.raises(StepError, match="at least three"):
        _run(BoxCoxStep(), {}, short)

    form, _, _ = _form(X.reshape(-1, 1), ("x",))
    with pytest.raises(StepError, match="unknown feature"):
        _run(BoxCoxStep(), {"lambdas": {"y": 0.5}}, form)
    with pytest.raises(StepError, match="number or mapping"):
        _run(BoxCoxStep(), {"lambdas": "x"}, form)
