"""Hand checks for 0.32 intraclass and concordance correlation."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.concordance_correlation import ConcordanceCorrelationStep
from src.task.step.steps.intraclass_correlation import IntraclassCorrelationStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(columns, names):
    data = np.column_stack(columns).astype(np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, data):
    ctx = Ctx(params)
    step.run(ctx, [data])
    return ctx[params.get("output", step.name)], step.export(ctx)


X = np.arange(1, 21, dtype=float)
Y = np.array([
    2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
    18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
])


def test_intraclass_correlation_matches_irr():
    out, info = _run(IntraclassCorrelationStep(), {}, _form([X, Y], ["x", "y"]))
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (12, 1)
    assert info["icc"] == pytest.approx(0.6282403440, abs=1e-8)
    assert info["f"] == pytest.approx(16.0425178877, abs=1e-8)
    assert info["ci_low"] == pytest.approx(-0.0850675490, abs=1e-7)
    assert info["ci_high"] == pytest.approx(0.8923981941, abs=1e-7)
    assert info["subjects"] == 20 and info["raters"] == 2


def test_intraclass_correlation_oneway_average():
    out, info = _run(
        IntraclassCorrelationStep(),
        {"model": "oneway", "unit": "average"},
        _form([X, Y], ["x", "y"]),
    )
    assert info["type"] == "oneway"
    assert out.data.shape == (12, 1)
    assert 0.0 <= info["icc"] <= 1.0


def test_concordance_correlation_matches_desctools():
    out, info = _run(
        ConcordanceCorrelationStep(),
        {"method_a": "x", "method_b": "y"},
        _form([X, Y], ["x", "y"]),
    )
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (13, 1)
    assert info["ccc"] == pytest.approx(0.6161839, abs=1e-6)
    assert info["ci_low"] == pytest.approx(0.4425713, abs=1e-6)
    assert info["ci_high"] == pytest.approx(0.7452724, abs=1e-6)
    assert info["s_shift"] == pytest.approx(1.665079, abs=1e-5)
    assert info["l_shift"] == pytest.approx(0.9898274, abs=1e-6)
    assert info["c_bias"] == pytest.approx(0.616255, abs=1e-5)
    assert info["n"] == 20


def test_agreement_parameter_errors():
    with pytest.raises(StepError, match="rater columns not found"):
        _run(IntraclassCorrelationStep(), {"raters": ["missing"]}, _form([X, Y], ["x", "y"]))

    constant = _form([X, np.ones_like(X)], ["x", "y"])
    with pytest.raises(StepError, match="every rater must vary"):
        _run(IntraclassCorrelationStep(), {}, constant)

    with pytest.raises(StepError, match="both measurement columns must vary"):
        _run(
            ConcordanceCorrelationStep(),
            {"method_a": "x", "method_b": "y"},
            _form([X, np.ones_like(X)], ["x", "y"]),
        )
